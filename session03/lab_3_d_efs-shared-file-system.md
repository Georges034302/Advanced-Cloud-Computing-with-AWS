# Lab 3.D: Amazon EFS Shared File System

## Overview
Deploy Amazon EFS as a shared network file system accessible by multiple EC2 instances across availability zones.

---

## Objectives
- Create EFS file system with encryption
- Configure mount targets in multiple AZs
- Launch EC2 instances and mount shared EFS
- Test concurrent file operations
- Clean up all resources

---

## Step 1 – Set Variables

```bash
# Set variables
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REGION="ap-southeast-2"
EFS_NAME="shared-efs-lab-3d"
KEY_NAME="efs-lab-key"

# Get VPC details
VPC_ID=$(aws ec2 describe-vpcs --filters "Name=is-default,Values=true" --query 'Vpcs[0].VpcId' --output text)
VPC_CIDR=$(aws ec2 describe-vpcs --vpc-ids "$VPC_ID" --query 'Vpcs[0].CidrBlock' --output text)
echo "VPC_ID=$VPC_ID"
echo "VPC_CIDR=$VPC_CIDR"

# Get subnet IDs
SUBNET_IDS=$(aws ec2 describe-subnets --filters "Name=vpc-id,Values=$VPC_ID" --query 'Subnets[*].{AZ:AvailabilityZone,SubnetId:SubnetId}' --output json)
SUBNET_ID_1=$(echo "$SUBNET_IDS" | jq -r '.[0].SubnetId')
SUBNET_ID_2=$(echo "$SUBNET_IDS" | jq -r '.[1].SubnetId')
AZ_1=$(echo "$SUBNET_IDS" | jq -r '.[0].AZ')
AZ_2=$(echo "$SUBNET_IDS" | jq -r '.[1].AZ')

echo "VPC_ID=$VPC_ID"
echo "SUBNET_ID_1=$SUBNET_ID_1 ($AZ_1)"
echo "SUBNET_ID_2=$SUBNET_ID_2 ($AZ_2)"
```

---

## Step 2 – Create SSH Key Pair

```bash
# Create SSH key pair and save private key to local file
aws ec2 create-key-pair \
  --key-name "$KEY_NAME" \
  --query 'KeyMaterial' \
  --output text > "${KEY_NAME}.pem"

# Set secure permissions on private key file
chmod 400 "${KEY_NAME}.pem"
```

---

## Step 3 – Create Security Groups

```bash
# Create EFS security group - controls access to EFS mount targets (NFS port 2049)
EFS_SG_ID=$(aws ec2 create-security-group --group-name "efs-mount-sg" --description "EFS mount targets" --vpc-id "$VPC_ID" --query 'GroupId' --output text)
# Allow NFS traffic from entire VPC CIDR range
aws ec2 authorize-security-group-ingress --group-id "$EFS_SG_ID" --protocol tcp --port 2049 --cidr "$VPC_CIDR"

# Create EC2 security group - controls access to EC2 instances
EC2_SG_ID=$(aws ec2 create-security-group --group-name "efs-client-sg" --description "EC2 instances accessing EFS" --vpc-id "$VPC_ID" --query 'GroupId' --output text)
# Allow SSH access from anywhere (restrict to specific IP in production)
aws ec2 authorize-security-group-ingress --group-id "$EC2_SG_ID" --protocol tcp --port 22 --cidr 0.0.0.0/0
# Allow EC2 instances to access EFS mount targets via NFS
aws ec2 authorize-security-group-ingress --group-id "$EFS_SG_ID" --protocol tcp --port 2049 --source-group "$EC2_SG_ID"

echo "EFS_SG_ID=$EFS_SG_ID"
echo "EC2_SG_ID=$EC2_SG_ID"
```

---

## Step 4 – Create EFS File System

```bash
# Create encrypted EFS file system with generalPurpose performance mode
FILE_SYSTEM_ID=$(aws efs create-file-system \
  --creation-token "${EFS_NAME}-$(date +%s)" \
  --performance-mode generalPurpose \
  --encrypted \
  --tags "Key=Name,Value=${EFS_NAME}" \
  --query 'FileSystemId' \
  --output text)
echo "FILE_SYSTEM_ID=$FILE_SYSTEM_ID"

# Wait for EFS to become available
for i in {1..10}; do
  STATUS=$(aws efs describe-file-systems --file-system-id "$FILE_SYSTEM_ID" --query 'FileSystems[0].LifeCycleState' --output text)
  [ "$STATUS" = "available" ] && break
  sleep 5
done
```

---

## Step 5 – Create Mount Targets

```bash
# Create mount target in first AZ - allows EC2 instances in AZ1 to access EFS
MOUNT_TARGET_ID_1=$(aws efs create-mount-target --file-system-id "$FILE_SYSTEM_ID" --subnet-id "$SUBNET_ID_1" --security-groups "$EFS_SG_ID" --query 'MountTargetId' --output text)

# Create mount target in second AZ - allows EC2 instances in AZ2 to access EFS
MOUNT_TARGET_ID_2=$(aws efs create-mount-target --file-system-id "$FILE_SYSTEM_ID" --subnet-id "$SUBNET_ID_2" --security-groups "$EFS_SG_ID" --query 'MountTargetId' --output text)

echo "MOUNT_TARGET_ID_1=$MOUNT_TARGET_ID_1"
echo "MOUNT_TARGET_ID_2=$MOUNT_TARGET_ID_2"
sleep 30
```

---

## Step 6 – Get Amazon Linux 2023 AMI

```bash
# Get latest Amazon Linux 2023 AMI ID
AMI_ID=$(aws ec2 describe-images \
  --owners amazon \
  --filters "Name=name,Values=al2023-ami-2023.*-x86_64" "Name=state,Values=available" \
  --query 'Images | sort_by(@, &CreationDate) | [-1].ImageId' \
  --output text)
echo "AMI_ID=$AMI_ID"
```

---

## Step 7 – Create User Data Script

```bash
# Create user data script to automatically mount EFS on instance boot
cat > user-data.sh << 'EOF'
#!/bin/bash
yum install -y amazon-efs-utils
mkdir -p /mnt/efs
mount -t efs FILE_SYSTEM_ID:/ /mnt/efs
echo "FILE_SYSTEM_ID:/ /mnt/efs efs defaults,_netdev 0 0" >> /etc/fstab
EOF

# Replace placeholder with actual EFS file system ID
sed -i "s/FILE_SYSTEM_ID/${FILE_SYSTEM_ID}/g" user-data.sh
```

---

## Step 8 – Launch EC2 Instances

```bash
# Run instance 1 and get Instance 1 ID
INSTANCE_ID_1=$(aws ec2 run-instances --image-id "$AMI_ID" --instance-type t3.micro --key-name "$KEY_NAME" --subnet-id "$SUBNET_ID_1" --security-group-ids "$EC2_SG_ID" --user-data file://user-data.sh --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=${INSTANCE_NAME}-1}]" --query 'Instances[0].InstanceId' --output text)
echo "INSTANCE_ID_1=$INSTANCE_ID_1"

# Run instance 2 and get Instance 2 ID
INSTANCE_ID_2=$(aws ec2 run-instances --image-id "$AMI_ID" --instance-type t3.micro --key-name "$KEY_NAME" --subnet-id "$SUBNET_ID_2" --security-group-ids "$EC2_SG_ID" --user-data file://user-data.sh --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=${INSTANCE_NAME}-2}]" --query 'Instances[0].InstanceId' --output text)
echo "INSTANCE_ID_2=$INSTANCE_ID_2"

# Wait for the EC2 instances to become ready
sleep 120

PUBLIC_IP_1=$(aws ec2 describe-instances --instance-ids "$INSTANCE_ID_1" --query 'Reservations[0].Instances[0].PublicIpAddress' --output text)
PUBLIC_IP_2=$(aws ec2 describe-instances --instance-ids "$INSTANCE_ID_2" --query 'Reservations[0].Instances[0].PublicIpAddress' --output text)

echo "PUBLIC_IP_1=$PUBLIC_IP_1"
echo "PUBLIC_IP_2=$PUBLIC_IP_2"
```

---

## Step 9 – Verify EFS Mount

```bash
# Verify EFS mount using SSH
ssh -i "${KEY_NAME}.pem" -o StrictHostKeyChecking=no ec2-user@"$PUBLIC_IP_1" 'df -h /mnt/efs && ls -la /mnt/efs'
ssh -i "${KEY_NAME}.pem" -o StrictHostKeyChecking=no ec2-user@"$PUBLIC_IP_2" 'df -h /mnt/efs && ls -la /mnt/efs'

# Alternative: Verify using SSM (Session Manager)
aws ssm send-command \
  --instance-ids "$INSTANCE_ID_1" \
  --document-name "AWS-RunShellScript" \
  --parameters 'commands=["df -h /mnt/efs","ls -la /mnt/efs"]' \
  --output text

aws ssm send-command \
  --instance-ids "$INSTANCE_ID_2" \
  --document-name "AWS-RunShellScript" \
  --parameters 'commands=["df -h /mnt/efs","ls -la /mnt/efs"]' \
  --output text
```

---

## Step 10 – Test Concurrent File Operations

```bash
# Copy and run concurrent write test on both instances via SSH
echo "Running concurrent write tests on both instances..."

# Run test on Instance 1 in background
ssh -i "${KEY_NAME}.pem" -o StrictHostKeyChecking=no ec2-user@${PUBLIC_IP_1} << 'ENDSSH' &
HOSTNAME=$(hostname)
TEST_DIR="/mnt/efs/shared-data"
echo "Starting concurrent write test on $HOSTNAME"
for i in {1..100}; do
  echo "Write $i from $HOSTNAME at $(date)" >> "$TEST_DIR/${HOSTNAME}-test.log"
  sleep 0.1
done
echo "Completed 100 writes on $HOSTNAME"
ls -lh "$TEST_DIR"
ENDSSH
```

```bash
# Run test on Instance 2 in background
ssh -i "${KEY_NAME}.pem" -o StrictHostKeyChecking=no ec2-user@${PUBLIC_IP_2} << 'ENDSSH' &
HOSTNAME=$(hostname)
TEST_DIR="/mnt/efs/shared-data"
echo "Starting concurrent write test on $HOSTNAME"
for i in {1..100}; do
  echo "Write $i from $HOSTNAME at $(date)" >> "$TEST_DIR/${HOSTNAME}-test.log"
  sleep 0.1
done
echo "Completed 100 writes on $HOSTNAME"
ls -lh "$TEST_DIR"
ENDSSH

# Wait for both background jobs to complete
```

---

## Step 10 – Configure Lifecycle Policy

```bash
# Configure lifecycle policy to move inactive files to IA storage after 30 days
aws efs put-lifecycle-configuration \
  --file-system-id "$FILE_SYSTEM_ID" \
  --lifecycle-policies "TransitionToIA=AFTER_30_DAYS"

echo "Lifecycle policy configured: Files inactive for 30 days will move to IA storage class"
```

---

## Step 12 – Create EFS Access Point

```bash
# Create EFS access point for application-specific access
ACCESS_POINT_ID=$(aws efs create-access-point \
  --file-system-id "$FILE_SYSTEM_ID" \
  --posix-user "Uid=1000,Gid=1000" \
  --root-directory "Path=/applications/app1,CreationInfo={OwnerUid=1000,OwnerGid=1000,Permissions=755}" \
  --tags "Key=Name,Value=${EFS_NAME}-access-point" "Key=Lab,Value=3D" \
  --query 'AccessPointId' \
  --output text)
echo "ACCESS_POINT_ID=$ACCESS_POINT_ID"
```

---

## Step 13 – Monitor Metrics

```bash
# View EFS file system size and lifecycle state
aws efs describe-file-systems \
  --file-system-id "$FILE_SYSTEM_ID" \
  --query 'FileSystems[0].{SizeInBytes:SizeInBytes.Value,State:LifeCycleState}' \
  --output table
```

---

## Step 14 – Test Performance

```bash
# Test performance on Instance 1
ssh -i "${KEY_NAME}.pem" -o StrictHostKeyChecking=no ec2-user@${PUBLIC_IP_1} << 'EOF'
dd if=/dev/zero of=/mnt/efs/testfile bs=1M count=100
dd if=/mnt/efs/testfile of=/dev/null bs=1M
rm /mnt/efs/testfile
EOF

# Test performance on Instance 2
ssh -i "${KEY_NAME}.pem" -o StrictHostKeyChecking=no ec2-user@${PUBLIC_IP_2} << 'EOF'
dd if=/dev/zero of=/mnt/efs/testfile bs=1M count=100
dd if=/mnt/efs/testfile of=/dev/null bs=1M
rm /mnt/efs/testfile
EOF
```

---

## Step 15 – Cleanup

```bash
aws ec2 terminate-instances --instance-ids "$INSTANCE_ID_1" "$INSTANCE_ID_2"
aws ec2 wait instance-terminated --instance-ids "$INSTANCE_ID_1" "$INSTANCE_ID_2"

aws efs delete-mount-target --mount-target-id "$MOUNT_TARGET_ID_1"
aws efs delete-mount-target --mount-target-id "$MOUNT_TARGET_ID_2"
sleep 60

aws efs delete-access-point --access-point-id "$ACCESS_POINT_ID"
aws efs delete-file-system --file-system-id "$FILE_SYSTEM_ID"

sleep 10
aws ec2 delete-security-group --group-id "$EC2_SG_ID"
aws ec2 delete-security-group --group-id "$EFS_SG_ID"

aws ec2 delete-key-pair --key-name "$KEY_NAME"
rm -f user-data.sh "${KEY_NAME}.pem"
```

---

## Summary

Completed tasks: Created encrypted EFS file system with multi-AZ mount targets, launched EC2 instances with SSH access, tested concurrent operations, configured lifecycle policy and access point, performed performance testing.

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
