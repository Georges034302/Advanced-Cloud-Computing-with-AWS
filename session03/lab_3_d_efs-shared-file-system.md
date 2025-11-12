# Lab 3.D: Amazon EFS Shared File System

## Overview
This lab demonstrates how to deploy Amazon Elastic File System (EFS) as a shared network file system accessible by multiple EC2 instances across different availability zones. You will configure mount targets, security groups, implement encryption, and test concurrent access patterns for distributed applications.

---

## Objectives
- Create Amazon EFS file system with encryption
- Configure mount targets across multiple availability zones
- Set up security groups for NFS access
- Launch EC2 instances in different availability zones
- Mount EFS on multiple EC2 instances simultaneously
- Test concurrent read/write operations
- Implement EFS lifecycle policies for cost optimization
- Configure EFS access points for application isolation
- Monitor file system performance metrics
- Clean up all resources

---

## Prerequisites
- AWS CLI configured (`aws configure`)
- Default VPC with multiple availability zones
- IAM permissions to manage EFS, EC2, and VPC resources
- Basic understanding of Linux file systems and NFS protocol
- SSH key pair for EC2 access

---

## Step 1 – Set Variables and Verify Prerequisites

```bash
# Get AWS account ID dynamically
ACCOUNT_ID=$(aws sts get-caller-identity \
  --query Account \
  --output text)
echo "ACCOUNT_ID=$ACCOUNT_ID"

# Set region
REGION="ap-southeast-2"
echo "REGION=$REGION"

# Set EFS file system name
EFS_NAME="shared-efs-lab-3d"
echo "EFS_NAME=$EFS_NAME"

# Get default VPC ID
VPC_ID=$(aws ec2 describe-vpcs \
  --filters "Name=is-default,Values=true" \
  --query 'Vpcs[0].VpcId' \
  --output text)
echo "VPC_ID=$VPC_ID"

# Get VPC CIDR block for security group
VPC_CIDR=$(aws ec2 describe-vpcs \
  --vpc-ids "$VPC_ID" \
  --query 'Vpcs[0].CidrBlock' \
  --output text)
echo "VPC_CIDR=$VPC_CIDR"

# Get availability zones for the region
AVAILABILITY_ZONES=$(aws ec2 describe-availability-zones \
  --region "$REGION" \
  --query 'AvailabilityZones[?State==`available`].ZoneName' \
  --output text)
echo "AVAILABILITY_ZONES=$AVAILABILITY_ZONES"

# Get subnet IDs for each availability zone
SUBNET_IDS=$(aws ec2 describe-subnets \
  --filters "Name=vpc-id,Values=$VPC_ID" \
  --query 'Subnets[*].{AZ:AvailabilityZone,SubnetId:SubnetId}' \
  --output json)
echo "SUBNET_IDS=$SUBNET_IDS"

# Select first two subnet IDs
SUBNET_ID_1=$(echo "$SUBNET_IDS" | jq -r '.[0].SubnetId')
echo "SUBNET_ID_1=$SUBNET_ID_1"

SUBNET_ID_2=$(echo "$SUBNET_IDS" | jq -r '.[1].SubnetId')
echo "SUBNET_ID_2=$SUBNET_ID_2"

# Get availability zone names
AZ_1=$(echo "$SUBNET_IDS" | jq -r '.[0].AZ')
echo "AZ_1=$AZ_1"

AZ_2=$(echo "$SUBNET_IDS" | jq -r '.[1].AZ')
echo "AZ_2=$AZ_2"

# Verify AWS CLI is configured
aws sts get-caller-identity
```

---

## Step 2 – Create Security Group for EFS

```bash
# Create security group for EFS mount targets
SG_ID=$(aws ec2 create-security-group \
  --group-name "efs-mount-target-sg" \
  --description "Security group for EFS mount targets - NFS access" \
  --vpc-id "$VPC_ID" \
  --query 'GroupId' \
  --output text)
echo "SG_ID=$SG_ID"

# Add inbound rule for NFS (port 2049) from VPC CIDR
aws ec2 authorize-security-group-ingress \
  --group-id "$SG_ID" \
  --protocol tcp \
  --port 2049 \
  --cidr "$VPC_CIDR"

echo "Security group created with NFS access from VPC"

# Describe security group
aws ec2 describe-security-groups \
  --group-ids "$SG_ID" \
  --query 'SecurityGroups[0].{GroupId:GroupId,GroupName:GroupName,IpPermissions:IpPermissions}' \
  --output json | jq '.'
```

---

## Step 3 – Create EFS File System with Encryption

```bash
# Create EFS file system with encryption at rest
EFS_OUTPUT=$(aws efs create-file-system \
  --creation-token "${EFS_NAME}-$(date +%s)" \
  --performance-mode generalPurpose \
  --throughput-mode bursting \
  --encrypted \
  --tags "Key=Name,Value=${EFS_NAME}" "Key=Lab,Value=3D")

# Extract file system ID
FILE_SYSTEM_ID=$(echo "$EFS_OUTPUT" | jq -r '.FileSystemId')
echo "FILE_SYSTEM_ID=$FILE_SYSTEM_ID"

# Display EFS details
echo "$EFS_OUTPUT" | jq '.'

echo ""
echo "EFS file system created with encryption enabled"
echo "Performance Mode: generalPurpose"
echo "Throughput Mode: bursting"

# Wait for file system to become available
echo ""
echo "Waiting for EFS file system to become available..."
aws efs describe-file-systems \
  --file-system-id "$FILE_SYSTEM_ID" \
  --query 'FileSystems[0].LifeCycleState' \
  --output text

# Check status periodically
for i in {1..10}; do
  STATUS=$(aws efs describe-file-systems \
    --file-system-id "$FILE_SYSTEM_ID" \
    --query 'FileSystems[0].LifeCycleState' \
    --output text)
  echo "Status: $STATUS"
  if [ "$STATUS" = "available" ]; then
    echo "EFS file system is now available!"
    break
  fi
  sleep 5
done
```

---

## Step 4 – Create Mount Targets in Multiple Availability Zones

```bash
# Create mount target in first availability zone
echo "Creating mount target in $AZ_1..."
MOUNT_TARGET_1=$(aws efs create-mount-target \
  --file-system-id "$FILE_SYSTEM_ID" \
  --subnet-id "$SUBNET_ID_1" \
  --security-groups "$SG_ID")

MOUNT_TARGET_ID_1=$(echo "$MOUNT_TARGET_1" | jq -r '.MountTargetId')
echo "MOUNT_TARGET_ID_1=$MOUNT_TARGET_ID_1"

# Create mount target in second availability zone
echo "Creating mount target in $AZ_2..."
MOUNT_TARGET_2=$(aws efs create-mount-target \
  --file-system-id "$FILE_SYSTEM_ID" \
  --subnet-id "$SUBNET_ID_2" \
  --security-groups "$SG_ID")

MOUNT_TARGET_ID_2=$(echo "$MOUNT_TARGET_2" | jq -r '.MountTargetId')
echo "MOUNT_TARGET_ID_2=$MOUNT_TARGET_ID_2"

echo ""
echo "Mount targets created in both availability zones"

# Wait for mount targets to become available
echo "Waiting for mount targets to become available..."
sleep 30

# Verify mount targets
aws efs describe-mount-targets \
  --file-system-id "$FILE_SYSTEM_ID" \
  --query 'MountTargets[*].{MountTargetId:MountTargetId,SubnetId:SubnetId,LifeCycleState:LifeCycleState,IpAddress:IpAddress}' \
  --output table
```

---

## Step 5 – Create Security Group for EC2 Instances

```bash
# Create security group for EC2 instances
EC2_SG_ID=$(aws ec2 create-security-group \
  --group-name "efs-client-sg" \
  --description "Security group for EC2 instances accessing EFS" \
  --vpc-id "$VPC_ID" \
  --query 'GroupId' \
  --output text)
echo "EC2_SG_ID=$EC2_SG_ID"

# Allow SSH access from anywhere (restrict in production)
aws ec2 authorize-security-group-ingress \
  --group-id "$EC2_SG_ID" \
  --protocol tcp \
  --port 22 \
  --cidr 0.0.0.0/0

# Allow NFS access to EFS security group
aws ec2 authorize-security-group-ingress \
  --group-id "$SG_ID" \
  --protocol tcp \
  --port 2049 \
  --source-group "$EC2_SG_ID"

echo "EC2 security group created with SSH and EFS access"

# Describe EC2 security group
aws ec2 describe-security-groups \
  --group-ids "$EC2_SG_ID" \
  --query 'SecurityGroups[0].{GroupId:GroupId,GroupName:GroupName,IpPermissions:IpPermissions}' \
  --output json | jq '.'
```

---

## Step 6 – Get Latest Amazon Linux 2023 AMI

```bash
# Get latest Amazon Linux 2023 AMI ID
AMI_ID=$(aws ec2 describe-images \
  --owners amazon \
  --filters "Name=name,Values=al2023-ami-2023.*-x86_64" \
    "Name=state,Values=available" \
  --query 'sort_by(Images, &CreationDate)[-1].ImageId' \
  --output text)
echo "AMI_ID=$AMI_ID"

# Display AMI details
aws ec2 describe-images \
  --image-ids "$AMI_ID" \
  --query 'Images[0].{ImageId:ImageId,Name:Name,Description:Description,CreationDate:CreationDate}' \
  --output table
```

---

## Step 7 – Create User Data Script for EFS Mount

```bash
# Create user data script for automatic EFS mounting
cat > efs-userdata.sh <<EOF
#!/bin/bash
# Update system packages
dnf update -y

# Install EFS utilities (includes amazon-efs-utils for EFS mounting)
dnf install -y amazon-efs-utils

# Create mount point directory
mkdir -p /mnt/efs

# Mount EFS using EFS helper (automatic encryption in transit)
echo "${FILE_SYSTEM_ID}:/ /mnt/efs efs _netdev,tls,iam 0 0" >> /etc/fstab

# Mount all filesystems in fstab
mount -a

# Verify mount
df -h /mnt/efs

# Create test directory
mkdir -p /mnt/efs/shared-data

# Set permissions
chmod 777 /mnt/efs/shared-data

# Create hostname file for identification
hostname > /mnt/efs/shared-data/\$(hostname).txt

echo "EFS mounted successfully on \$(hostname)" > /var/log/efs-mount.log
EOF

# Display user data script
cat efs-userdata.sh

echo ""
echo "User data script created for automatic EFS mounting"
```

---

## Step 8 – Launch EC2 Instances in Multiple Availability Zones

```bash
# Launch EC2 instance in first availability zone
echo "Launching EC2 instance in $AZ_1..."
INSTANCE_1_OUTPUT=$(aws ec2 run-instances \
  --image-id "$AMI_ID" \
  --instance-type t2.micro \
  --subnet-id "$SUBNET_ID_1" \
  --security-group-ids "$EC2_SG_ID" \
  --user-data file://efs-userdata.sh \
  --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=efs-client-1-${AZ_1}},{Key=Lab,Value=3D}]" \
  --iam-instance-profile "Name=LabInstanceProfile" \
  --count 1)

INSTANCE_ID_1=$(echo "$INSTANCE_1_OUTPUT" | jq -r '.Instances[0].InstanceId')
echo "INSTANCE_ID_1=$INSTANCE_ID_1"

# Launch EC2 instance in second availability zone
echo "Launching EC2 instance in $AZ_2..."
INSTANCE_2_OUTPUT=$(aws ec2 run-instances \
  --image-id "$AMI_ID" \
  --instance-type t2.micro \
  --subnet-id "$SUBNET_ID_2" \
  --security-group-ids "$EC2_SG_ID" \
  --user-data file://efs-userdata.sh \
  --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=efs-client-2-${AZ_2}},{Key=Lab,Value=3D}]" \
  --iam-instance-profile "Name=LabInstanceProfile" \
  --count 1)

INSTANCE_ID_2=$(echo "$INSTANCE_2_OUTPUT" | jq -r '.Instances[0].InstanceId')
echo "INSTANCE_ID_2=$INSTANCE_ID_2"

echo ""
echo "Two EC2 instances launched in different availability zones"

# Wait for instances to be running
echo "Waiting for instances to be running..."
aws ec2 wait instance-running \
  --instance-ids "$INSTANCE_ID_1" "$INSTANCE_ID_2"

echo "Instances are now running"

# Get public IP addresses
PUBLIC_IP_1=$(aws ec2 describe-instances \
  --instance-ids "$INSTANCE_ID_1" \
  --query 'Reservations[0].Instances[0].PublicIpAddress' \
  --output text)
echo "PUBLIC_IP_1=$PUBLIC_IP_1"

PUBLIC_IP_2=$(aws ec2 describe-instances \
  --instance-ids "$INSTANCE_ID_2" \
  --query 'Reservations[0].Instances[0].PublicIpAddress' \
  --output text)
echo "PUBLIC_IP_2=$PUBLIC_IP_2"

# Display instance details
aws ec2 describe-instances \
  --instance-ids "$INSTANCE_ID_1" "$INSTANCE_ID_2" \
  --query 'Reservations[*].Instances[*].{InstanceId:InstanceId,PublicIP:PublicIpAddress,PrivateIP:PrivateIpAddress,AZ:Placement.AvailabilityZone,State:State.Name}' \
  --output table
```

---

## Step 9 – Verify EFS Mount on EC2 Instances

```bash
# Wait for user data script to complete
echo "Waiting 2 minutes for user data script to complete..."
sleep 120

# Note: The following commands demonstrate what to run via SSH
# You'll need to SSH into the instances to verify the mount

echo ""
echo "Connect to instances and verify EFS mount:"
echo ""
echo "Instance 1 ($AZ_1):"
echo "  SSH command: ssh -i <your-key.pem> ec2-user@${PUBLIC_IP_1}"
echo ""
echo "Instance 2 ($AZ_2):"
echo "  SSH command: ssh -i <your-key.pem> ec2-user@${PUBLIC_IP_2}"
echo ""
echo "On each instance, run:"
echo "  df -h /mnt/efs                 # Verify mount"
echo "  ls -la /mnt/efs/shared-data/   # List shared files"
echo "  cat /var/log/efs-mount.log     # Check mount log"
echo ""

# Alternative: Use Systems Manager Session Manager if IAM role configured
echo "Alternative: Use Systems Manager Session Manager (no SSH key needed):"
echo "  aws ssm start-session --target $INSTANCE_ID_1"
echo "  aws ssm start-session --target $INSTANCE_ID_2"
```

---

## Step 10 – Test Concurrent File Operations

```bash
# Create test script for concurrent writes
cat > test-concurrent-writes.sh <<'EOF'
#!/bin/bash
# This script should be run on each EC2 instance

HOSTNAME=$(hostname)
TEST_DIR="/mnt/efs/shared-data"

echo "Starting concurrent write test on $HOSTNAME"

# Write 100 files with timestamp
for i in {1..100}; do
  echo "Write $i from $HOSTNAME at $(date)" >> "$TEST_DIR/${HOSTNAME}-test.log"
  sleep 0.1
done

echo "Completed 100 writes on $HOSTNAME"

# Count total files in shared directory
FILE_COUNT=$(ls -1 "$TEST_DIR" | wc -l)
echo "Total files in shared directory: $FILE_COUNT"

# Display all files
ls -lh "$TEST_DIR"
EOF

# Display test script
cat test-concurrent-writes.sh

echo ""
echo "Concurrent write test script created"
echo ""
echo "To test concurrent operations:"
echo "1. Copy script to both instances:"
echo "   scp -i <key.pem> test-concurrent-writes.sh ec2-user@${PUBLIC_IP_1}:~/"
echo "   scp -i <key.pem> test-concurrent-writes.sh ec2-user@${PUBLIC_IP_2}:~/"
echo ""
echo "2. SSH to both instances and run simultaneously:"
echo "   chmod +x test-concurrent-writes.sh"
echo "   ./test-concurrent-writes.sh"
echo ""
echo "3. Verify both instances see the same files:"
echo "   ls -l /mnt/efs/shared-data/"
echo "   cat /mnt/efs/shared-data/*.log"
```

---

## Step 11 – Configure EFS Lifecycle Policy

```bash
# Configure lifecycle management to transition files to Infrequent Access (IA)
echo "Configuring EFS lifecycle policy..."

# Create lifecycle policy (transition after 30 days of inactivity)
aws efs put-lifecycle-configuration \
  --file-system-id "$FILE_SYSTEM_ID" \
  --lifecycle-policies "TransitionToIA=AFTER_30_DAYS"

# Verify lifecycle policy
aws efs describe-lifecycle-configuration \
  --file-system-id "$FILE_SYSTEM_ID" \
  --query 'LifecyclePolicies' \
  --output table

echo ""
echo "Lifecycle policy configured: Files inactive for 30 days will move to IA storage class"
echo "IA storage class costs 85% less than standard storage"
```

---

## Step 12 – Create EFS Access Point

```bash
# Create EFS access point for application-specific access
echo "Creating EFS access point..."

ACCESS_POINT_OUTPUT=$(aws efs create-access-point \
  --file-system-id "$FILE_SYSTEM_ID" \
  --posix-user "Uid=1000,Gid=1000" \
  --root-directory "Path=/applications/app1,CreationInfo={OwnerUid=1000,OwnerGid=1000,Permissions=755}" \
  --tags "Key=Name,Value=${EFS_NAME}-access-point" "Key=Lab,Value=3D")

# Extract access point ID
ACCESS_POINT_ID=$(echo "$ACCESS_POINT_OUTPUT" | jq -r '.AccessPointId')
echo "ACCESS_POINT_ID=$ACCESS_POINT_ID"

# Display access point details
echo "$ACCESS_POINT_OUTPUT" | jq '.'

echo ""
echo "EFS access point created with dedicated application path"
echo "Access point provides simplified mounting and enforces user/permissions"

# Describe access point
aws efs describe-access-points \
  --access-point-id "$ACCESS_POINT_ID" \
  --query 'AccessPoints[0]' \
  --output json | jq '.'
```

---

## Step 13 – Monitor EFS Metrics

```bash
# Get EFS file system metrics
echo "Retrieving EFS file system metrics..."

# Describe file system
aws efs describe-file-systems \
  --file-system-id "$FILE_SYSTEM_ID" \
  --query 'FileSystems[0].{FileSystemId:FileSystemId,SizeInBytes:SizeInBytes,NumberOfMountTargets:NumberOfMountTargets,LifeCycleState:LifeCycleState,PerformanceMode:PerformanceMode,Encrypted:Encrypted}' \
  --output table

# Get current size
SIZE_BYTES=$(aws efs describe-file-systems \
  --file-system-id "$FILE_SYSTEM_ID" \
  --query 'FileSystems[0].SizeInBytes.Value' \
  --output text)
echo "SIZE_BYTES=$SIZE_BYTES"

# Convert to human-readable format
SIZE_MB=$(echo "scale=2; $SIZE_BYTES / 1024 / 1024" | bc)
echo "Current EFS size: ${SIZE_MB} MB"

# List mount targets
echo ""
echo "Mount targets:"
aws efs describe-mount-targets \
  --file-system-id "$FILE_SYSTEM_ID" \
  --query 'MountTargets[*].{MountTargetId:MountTargetId,SubnetId:SubnetId,LifeCycleState:LifeCycleState,IpAddress:IpAddress}' \
  --output table

# CloudWatch metrics (note: may take time to populate)
echo ""
echo "CloudWatch metrics available for:"
echo "- DataReadIOBytes"
echo "- DataWriteIOBytes"
echo "- MetadataIOBytes"
echo "- TotalIOBytes"
echo "- PermittedThroughput"
echo "- ClientConnections"
echo ""
echo "View metrics:"
echo "aws cloudwatch get-metric-statistics \\"
echo "  --namespace AWS/EFS \\"
echo "  --metric-name DataWriteIOBytes \\"
echo "  --dimensions Name=FileSystemId,Value=$FILE_SYSTEM_ID \\"
echo "  --start-time \$(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \\"
echo "  --end-time \$(date -u +%Y-%m-%dT%H:%M:%S) \\"
echo "  --period 300 \\"
echo "  --statistics Sum"
```

---

## Step 14 – Test EFS Performance

```bash
# Create performance test script
cat > test-efs-performance.sh <<'EOF'
#!/bin/bash
# This script should be run on EC2 instances to test EFS performance

TEST_DIR="/mnt/efs/performance-test"
mkdir -p "$TEST_DIR"

echo "EFS Performance Test - $(hostname)"
echo "=================================="

# Test 1: Sequential write performance
echo ""
echo "Test 1: Sequential write (100 MB file)..."
dd if=/dev/zero of="$TEST_DIR/test-write.dat" bs=1M count=100 conv=fdatasync 2>&1 | grep -E "copied|MB/s"

# Test 2: Sequential read performance
echo ""
echo "Test 2: Sequential read (100 MB file)..."
dd if="$TEST_DIR/test-write.dat" of=/dev/null bs=1M 2>&1 | grep -E "copied|MB/s"

# Test 3: Create many small files
echo ""
echo "Test 3: Creating 1000 small files..."
time for i in {1..1000}; do
  echo "test data" > "$TEST_DIR/small-file-$i.txt"
done

# Test 4: List directory
echo ""
echo "Test 4: Listing directory with 1000 files..."
time ls "$TEST_DIR" > /dev/null

# Test 5: Delete files
echo ""
echo "Test 5: Deleting 1000 files..."
time rm -f "$TEST_DIR"/small-file-*.txt

# Cleanup
rm -f "$TEST_DIR/test-write.dat"

echo ""
echo "Performance test completed on $(hostname)"
EOF

# Display performance test script
cat test-efs-performance.sh

echo ""
echo "Performance test script created"
echo ""
echo "To run performance tests:"
echo "1. Copy script to instances:"
echo "   scp -i <key.pem> test-efs-performance.sh ec2-user@${PUBLIC_IP_1}:~/"
echo ""
echo "2. SSH and run test:"
echo "   chmod +x test-efs-performance.sh"
echo "   ./test-efs-performance.sh"
echo ""
echo "Note: EFS performance scales with storage size (baseline + burst)"
echo "- Baseline: 50 KB/s per GB stored"
echo "- Burst: Up to 100 MB/s"
echo "- Credit system for bursting above baseline"
```

---

## Step 15 – Cleanup Resources

```bash
# Terminate EC2 instances
echo "Terminating EC2 instances..."

aws ec2 terminate-instances \
  --instance-ids "$INSTANCE_ID_1" "$INSTANCE_ID_2"

# Wait for instances to terminate
echo "Waiting for instances to terminate..."
aws ec2 wait instance-terminated \
  --instance-ids "$INSTANCE_ID_1" "$INSTANCE_ID_2"

echo "Instances terminated successfully"

# Delete mount targets
echo "Deleting EFS mount targets..."

aws efs delete-mount-target \
  --mount-target-id "$MOUNT_TARGET_ID_1"

aws efs delete-mount-target \
  --mount-target-id "$MOUNT_TARGET_ID_2"

# Wait for mount targets to be deleted
echo "Waiting for mount targets to be deleted..."
sleep 60

# Verify mount targets deleted
MOUNT_TARGET_COUNT=$(aws efs describe-mount-targets \
  --file-system-id "$FILE_SYSTEM_ID" \
  --query 'length(MountTargets)' \
  --output text)

if [ "$MOUNT_TARGET_COUNT" -gt 0 ]; then
  echo "Waiting additional time for mount targets..."
  sleep 60
fi

# Delete access point
echo "Deleting EFS access point..."
aws efs delete-access-point \
  --access-point-id "$ACCESS_POINT_ID"

# Delete EFS file system
echo "Deleting EFS file system..."
aws efs delete-file-system \
  --file-system-id "$FILE_SYSTEM_ID"

# Verify file system deletion
aws efs describe-file-systems \
  --file-system-id "$FILE_SYSTEM_ID" 2>&1 || echo "EFS file system deleted successfully"

# Delete security groups
echo "Deleting security groups..."

# Wait a moment for dependencies to clear
sleep 10

aws ec2 delete-security-group \
  --group-id "$EC2_SG_ID"

aws ec2 delete-security-group \
  --group-id "$SG_ID"

# Verify security group deletion
aws ec2 describe-security-groups \
  --group-ids "$SG_ID" 2>&1 || echo "EFS security group deleted"

aws ec2 describe-security-groups \
  --group-ids "$EC2_SG_ID" 2>&1 || echo "EC2 security group deleted"

# Delete local files
echo "Cleaning up local files..."
rm -f efs-userdata.sh \
  test-concurrent-writes.sh \
  test-efs-performance.sh

echo ""
echo "✅ Cleanup completed successfully!"
echo ""
echo "All resources deleted:"
echo "- EC2 instances (2)"
echo "- EFS mount targets (2)"
echo "- EFS access point"
echo "- EFS file system"
echo "- Security groups (2)"
echo "- Local test scripts"
```

---

## Summary

In this lab, you have:
- Created Amazon EFS file system with encryption at rest
- Configured mount targets in multiple availability zones
- Set up security groups for NFS access (port 2049)
- Launched EC2 instances across different AZs
- Mounted EFS on multiple instances simultaneously
- Tested concurrent read/write operations
- Implemented EFS lifecycle policies for cost optimization
- Created EFS access points for application isolation
- Monitored file system size and metrics
- Performed performance testing on shared file system

**Key Takeaways:**
- **Shared Storage**: EFS provides true shared file system accessible by multiple instances
- **Multi-AZ**: Mount targets in each AZ enable high availability
- **Automatic Scaling**: File system grows and shrinks automatically
- **Encryption**: Supports encryption at rest and in transit
- **POSIX Compliance**: Full POSIX file system semantics
- **Lifecycle Management**: IA storage class reduces costs by 85%
- **Access Points**: Application-specific mount points with enforced permissions
- **Performance Modes**: General Purpose (default) or Max I/O for high scale

**EFS vs Other Storage:**
| Feature | EFS | EBS | S3 |
|---------|-----|-----|-----|
| **Type** | Network File System | Block Storage | Object Storage |
| **Access** | Multiple EC2 instances | Single EC2 instance | API/HTTP |
| **Use Case** | Shared data, content management | Database, boot volumes | Backups, static content |
| **Performance** | Scales with size | Fixed IOPS | High throughput |
| **Cost** | $0.30/GB/month | $0.10/GB/month | $0.023/GB/month |

**Performance Characteristics:**
- **Baseline Throughput**: 50 KB/s per GB stored
- **Burst Throughput**: Up to 100 MB/s
- **Max I/O Mode**: For >7,000 file operations per second
- **Provisioned Throughput**: Fixed throughput regardless of size
- **Latency**: Single-digit milliseconds

**Cost Optimization:**
- **Standard Storage**: $0.30/GB/month
- **Infrequent Access (IA)**: $0.045/GB/month (85% savings)
- **Lifecycle Policies**: Automatic transition after 7, 14, 30, 60, or 90 days
- **Pay Per Use**: No minimum fees, pay only for storage used

**Real-World Use Cases:**
- **Web Serving**: Shared content for multiple web servers
- **Content Management**: WordPress, Drupal multi-server deployments
- **Development**: Shared code repositories and build artifacts
- **Big Data**: Hadoop, Spark data lakes
- **Media Processing**: Video rendering farms
- **Machine Learning**: Shared training datasets
- **Container Storage**: Persistent volumes for Kubernetes/ECS
- **Home Directories**: Shared user home directories

**Security Best Practices:**
- Enable encryption at rest and in transit (TLS)
- Use VPC security groups to restrict NFS access
- Implement IAM policies for EFS API access
- Use access points for application-specific isolation
- Configure POSIX permissions appropriately
- Enable AWS Backup for EFS

**Monitoring and Troubleshooting:**
- CloudWatch metrics: Data transfer, throughput, client connections
- EFS console: File system size, mount target status
- VPC Flow Logs: Network traffic analysis
- CloudTrail: API call logging
- Mount helper logs: `/var/log/amazon-efs-mount.log`

---

## Additional Resources
- [Amazon EFS User Guide](https://docs.aws.amazon.com/efs/latest/ug/whatisefs.html)
- [EFS Performance](https://docs.aws.amazon.com/efs/latest/ug/performance.html)
- [EFS Lifecycle Management](https://docs.aws.amazon.com/efs/latest/ug/lifecycle-management-efs.html)
- [EFS Access Points](https://docs.aws.amazon.com/efs/latest/ug/efs-access-points.html)
- [Mounting EFS on EC2](https://docs.aws.amazon.com/efs/latest/ug/mounting-fs.html)
- [EFS Security](https://docs.aws.amazon.com/efs/latest/ug/security-considerations.html)

---
