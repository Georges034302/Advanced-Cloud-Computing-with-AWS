# Lab 3.B: EBS Volumes, Snapshots, and Lifecycle Management

## Overview
Learn to create EC2 instances, attach and manage EBS volumes, create snapshots, restore from backups, and automate snapshot lifecycle with AWS Data Lifecycle Manager (DLM).

## Objectives
- Create EC2 instance with security configuration
- Attach and format EBS volumes
- Resize volumes online without downtime
- Create and restore from snapshots
- Automate backups with DLM

## Prerequisites
- AWS CLI configured and authenticated
- jq installed for JSON parsing

---

## Steps

### 1. Set Variables
```bash
# Get AWS account ID
export ACCOUNT_ID=$(aws sts get-caller-identity \
  --query Account \
  --output text)
echo "ACCOUNT_ID=$ACCOUNT_ID"

# Set region
export REGION="ap-southeast-2"
echo "REGION=$REGION"

# Get default VPC
export VPC_ID=$(aws ec2 describe-vpcs \
  --region "$REGION" \
  --filters "Name=is-default,Values=true" \
  --query 'Vpcs[0].VpcId' \
  --output text)
echo "VPC_ID=$VPC_ID"

# If no default VPC, create one
if [ "$VPC_ID" = "None" ] || [ -z "$VPC_ID" ]; then
  export VPC_ID=$(aws ec2 create-default-vpc \
    --region "$REGION" \
    --query 'Vpc.VpcId' \
    --output text)
  echo "Created default VPC: $VPC_ID"
fi

# Get subnet and availability zone
export SUBNET_ID=$(aws ec2 describe-subnets \
  --region "$REGION" \
  --filters "Name=vpc-id,Values=$VPC_ID" \
  --query 'Subnets[0].SubnetId' \
  --output text)
echo "SUBNET_ID=$SUBNET_ID"

export AVAILABILITY_ZONE=$(aws ec2 describe-subnets \
  --region "$REGION" \
  --subnet-ids "$SUBNET_ID" \
  --query 'Subnets[0].AvailabilityZone' \
  --output text)
echo "AVAILABILITY_ZONE=$AVAILABILITY_ZONE"
```

### 2. Create Security Group
```bash
# Create security group for SSH access
export SG_NAME="ebs-lab-sg"

export SECURITY_GROUP_ID=$(aws ec2 create-security-group \
  --region "$REGION" \
  --group-name "$SG_NAME" \
  --description "Security group for EBS lab" \
  --vpc-id "$VPC_ID" \
  --tag-specifications 'ResourceType=security-group,Tags=[{Key=Name,Value=ebs-lab-sg}]' \
  --query 'GroupId' \
  --output text)
echo "SECURITY_GROUP_ID=$SECURITY_GROUP_ID"

# Get your public IP
export MY_IP=$(curl -s https://checkip.amazonaws.com)
echo "MY_IP=$MY_IP"

# Allow SSH from your IP
aws ec2 authorize-security-group-ingress \
  --region "$REGION" \
  --group-id "$SECURITY_GROUP_ID" \
  --protocol tcp \
  --port 22 \
  --cidr "${MY_IP}/32"

echo "SSH access allowed from $MY_IP"
```

### 3. Create Key Pair
```bash
# Set key pair name
export KEY_NAME="ebs-lab-key"
echo "KEY_NAME=$KEY_NAME"

# Check if key exists
KEY_EXISTS=$(aws ec2 describe-key-pairs \
  --region "$REGION" \
  --key-names "$KEY_NAME" \
  --query 'KeyPairs[0].KeyName' \
  --output text 2>/dev/null || echo "")

if [ -z "$KEY_EXISTS" ]; then
  # Create new key pair
  aws ec2 create-key-pair \
    --region "$REGION" \
    --key-name "$KEY_NAME" \
    --query 'KeyMaterial' \
    --output text > "${KEY_NAME}.pem"
  
  chmod 400 "${KEY_NAME}.pem"
  echo "Key pair created: ${KEY_NAME}.pem"
else
  echo "Using existing key pair: $KEY_NAME"
fi
```

### 4. Launch EC2 Instance
```bash
# Get latest Amazon Linux 2023 AMI
export AMI_ID=$(aws ec2 describe-images \
  --region "$REGION" \
  --owners amazon \
  --filters "Name=name,Values=al2023-ami-2023*-x86_64" \
            "Name=state,Values=available" \
  --query 'sort_by(Images, &CreationDate)[-1].ImageId' \
  --output text)
echo "AMI_ID=$AMI_ID"

# Launch instance
export INSTANCE_ID=$(aws ec2 run-instances \
  --region "$REGION" \
  --image-id "$AMI_ID" \
  --instance-type t3.micro \
  --key-name "$KEY_NAME" \
  --security-group-ids "$SECURITY_GROUP_ID" \
  --subnet-id "$SUBNET_ID" \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=ebs-lab-instance}]' \
  --query 'Instances[0].InstanceId' \
  --output text)
echo "INSTANCE_ID=$INSTANCE_ID"

# Wait for instance to run
echo "Waiting for instance to start..."
aws ec2 wait instance-running \
  --region "$REGION" \
  --instance-ids "$INSTANCE_ID"

# Get public IP
export INSTANCE_IP=$(aws ec2 describe-instances \
  --region "$REGION" \
  --instance-ids "$INSTANCE_ID" \
  --query 'Reservations[0].Instances[0].PublicIpAddress' \
  --output text)
echo "INSTANCE_IP=$INSTANCE_IP"
echo "SSH: ssh -i ${KEY_NAME}.pem ec2-user@${INSTANCE_IP}"
```

### 5. Create and Attach EBS Volume
```bash
# Create 10 GiB EBS volume
export VOLUME_ID=$(aws ec2 create-volume \
  --region "$REGION" \
  --availability-zone "$AVAILABILITY_ZONE" \
  --size 10 \
  --volume-type gp3 \
  --tag-specifications 'ResourceType=volume,Tags=[{Key=Name,Value=lab-ebs-volume},{Key=Backup,Value=daily}]' \
  --query 'VolumeId' \
  --output text)
echo "VOLUME_ID=$VOLUME_ID"

# Wait for volume to be available
aws ec2 wait volume-available \
  --region "$REGION" \
  --volume-ids "$VOLUME_ID"

# Attach volume to instance
export DEVICE_NAME="/dev/sdf"
aws ec2 attach-volume \
  --region "$REGION" \
  --volume-id "$VOLUME_ID" \
  --instance-id "$INSTANCE_ID" \
  --device "$DEVICE_NAME"

# Wait for attachment
aws ec2 wait volume-in-use \
  --region "$REGION" \
  --volume-ids "$VOLUME_ID"

echo "Volume attached as $DEVICE_NAME (may appear as /dev/xvdf on instance)"
```

### 6. Format and Mount Volume (On EC2 Instance)
```bash
# Display commands to run on EC2 instance
echo "Connect: ssh -i ${KEY_NAME}.pem ec2-user@${INSTANCE_IP}"
echo ""
echo "Run these commands on the instance:"
echo ""

cat << 'EOF'
# Find device name
sudo lsblk

# Format volume (device typically appears as /dev/xvdf)
DEVICE="/dev/xvdf"
sudo mkfs -t ext4 "$DEVICE"

# Create mount point and mount
sudo mkdir -p /mnt/ebs-data
sudo mount "$DEVICE" /mnt/ebs-data

# Create test file
echo "EBS test data" | sudo tee /mnt/ebs-data/test.txt

# Add to fstab for persistent mounting
UUID=$(sudo blkid -s UUID -o value "$DEVICE")
echo "UUID=$UUID /mnt/ebs-data ext4 defaults,nofail 0 2" | sudo tee -a /etc/fstab

# Verify
df -h /mnt/ebs-data
cat /mnt/ebs-data/test.txt
EOF
```

### 7. Expand Volume
```bash
# Increase volume size to 20 GiB
aws ec2 modify-volume \
  --region "$REGION" \
  --volume-id "$VOLUME_ID" \
  --size 20

echo "Volume resize initiated"
echo ""
echo "On instance, run: sudo resize2fs /dev/xvdf"
echo "Then verify: df -h /mnt/ebs-data"
```

### 8. Create Snapshot
```bash
# Create snapshot
export SNAPSHOT_ID=$(aws ec2 create-snapshot \
  --region "$REGION" \
  --volume-id "$VOLUME_ID" \
  --description "EBS lab snapshot $(date +%Y-%m-%d)" \
  --tag-specifications 'ResourceType=snapshot,Tags=[{Key=Name,Value=lab-snapshot}]' \
  --query 'SnapshotId' \
  --output text)
echo "SNAPSHOT_ID=$SNAPSHOT_ID"

# Wait for snapshot to complete
echo "Creating snapshot (may take a few minutes)..."
aws ec2 wait snapshot-completed \
  --region "$REGION" \
  --snapshot-ids "$SNAPSHOT_ID"

echo "Snapshot created successfully"
```

### 9. Restore Volume from Snapshot
```bash
# Create volume from snapshot
export RESTORED_VOLUME_ID=$(aws ec2 create-volume \
  --region "$REGION" \
  --availability-zone "$AVAILABILITY_ZONE" \
  --snapshot-id "$SNAPSHOT_ID" \
  --volume-type gp3 \
  --tag-specifications 'ResourceType=volume,Tags=[{Key=Name,Value=restored-volume}]' \
  --query 'VolumeId' \
  --output text)
echo "RESTORED_VOLUME_ID=$RESTORED_VOLUME_ID"

# Wait for volume
aws ec2 wait volume-available \
  --region "$REGION" \
  --volume-ids "$RESTORED_VOLUME_ID"

# Attach restored volume
export RESTORED_DEVICE="/dev/sdg"
aws ec2 attach-volume \
  --region "$REGION" \
  --volume-id "$RESTORED_VOLUME_ID" \
  --instance-id "$INSTANCE_ID" \
  --device "$RESTORED_DEVICE"

aws ec2 wait volume-in-use \
  --region "$REGION" \
  --volume-ids "$RESTORED_VOLUME_ID"

echo "Restored volume attached"
echo ""
echo "On instance, run:"
echo "  sudo mkdir -p /mnt/restored-data"
echo "  sudo mount /dev/xvdg /mnt/restored-data"
echo "  cat /mnt/restored-data/test.txt"
```

### 10. Automate Snapshots with DLM
```bash
# Create DLM IAM role if needed
export DLM_ROLE_NAME="AWSDataLifecycleManagerDefaultRole"

ROLE_EXISTS=$(aws iam get-role \
  --role-name "$DLM_ROLE_NAME" \
  --query 'Role.RoleName' \
  --output text 2>/dev/null || echo "")

if [ -z "$ROLE_EXISTS" ]; then
  # Create trust policy
  cat > dlm-trust-policy.json <<'TRUST'
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {"Service": "dlm.amazonaws.com"},
    "Action": "sts:AssumeRole"
  }]
}
TRUST

  # Create role
  aws iam create-role \
    --role-name "$DLM_ROLE_NAME" \
    --assume-role-policy-document file://dlm-trust-policy.json

  # Attach policy
  aws iam attach-role-policy \
    --role-name "$DLM_ROLE_NAME" \
    --policy-arn "arn:aws:iam::aws:policy/service-role/AWSDataLifecycleManagerServiceRole"
fi

# Get role ARN
export DLM_ROLE_ARN=$(aws iam get-role \
  --role-name "$DLM_ROLE_NAME" \
  --query 'Role.Arn' \
  --output text)
echo "DLM_ROLE_ARN=$DLM_ROLE_ARN"

# Create DLM policy
cat > dlm-policy.json <<POLICY
{
  "ExecutionRoleArn": "${DLM_ROLE_ARN}",
  "Description": "Daily snapshots for volumes tagged Backup=daily",
  "State": "ENABLED",
  "PolicyDetails": {
    "PolicyType": "EBS_SNAPSHOT_MANAGEMENT",
    "ResourceTypes": ["VOLUME"],
    "TargetTags": [{"Key": "Backup", "Value": "daily"}],
    "Schedules": [{
      "Name": "daily-snapshot",
      "CreateRule": {
        "Interval": 24,
        "IntervalUnit": "HOURS",
        "Times": ["03:00"]
      },
      "RetainRule": {"Count": 7},
      "TagsToAdd": [{"Key": "ManagedBy", "Value": "DLM"}],
      "CopyTags": true
    }]
  }
}
POLICY

# Create lifecycle policy
export POLICY_ID=$(aws dlm create-lifecycle-policy \
  --region "$REGION" \
  --cli-input-json file://dlm-policy.json \
  --query 'PolicyId' \
  --output text)
echo "POLICY_ID=$POLICY_ID"
echo "DLM policy created - volumes with tag 'Backup=daily' will be backed up daily"
```

---

## Cleanup
```bash
echo "Starting cleanup..."

# Unmount on instance first (manual step)
echo "On instance, run:"
echo "  sudo umount /mnt/ebs-data /mnt/restored-data"
echo "  sudo sed -i '/\/mnt\/ebs-data/d' /etc/fstab"
echo ""
echo "Press Enter after unmounting..."
read

# Detach volumes
aws ec2 detach-volume --region "$REGION" --volume-id "$VOLUME_ID" 2>/dev/null || true
aws ec2 detach-volume --region "$REGION" --volume-id "$RESTORED_VOLUME_ID" 2>/dev/null || true

sleep 10

# Delete volumes
aws ec2 delete-volume --region "$REGION" --volume-id "$VOLUME_ID" 2>/dev/null || true
aws ec2 delete-volume --region "$REGION" --volume-id "$RESTORED_VOLUME_ID" 2>/dev/null || true

# Delete snapshot
aws ec2 delete-snapshot --region "$REGION" --snapshot-id "$SNAPSHOT_ID" 2>/dev/null || true

# Delete DLM policy
aws dlm delete-lifecycle-policy --region "$REGION" --policy-id "$POLICY_ID" 2>/dev/null || true

# Terminate instance
aws ec2 terminate-instances --region "$REGION" --instance-ids "$INSTANCE_ID"
aws ec2 wait instance-terminated --region "$REGION" --instance-ids "$INSTANCE_ID"

# Delete security group
aws ec2 delete-security-group --region "$REGION" --group-id "$SECURITY_GROUP_ID" 2>/dev/null || true

# Delete key pair
aws ec2 delete-key-pair --region "$REGION" --key-name "$KEY_NAME" 2>/dev/null || true
rm -f "${KEY_NAME}.pem"

# Clean up files
rm -f dlm-policy.json dlm-trust-policy.json

echo "✅ Cleanup complete"
```

---

## Summary
This lab demonstrates complete EBS lifecycle management: creating instances, attaching volumes, formatting filesystems, online resizing, snapshots, restore, and automated backups with DLM.

**Key Points:**
- EBS volumes are AZ-specific
- Snapshots are incremental backups
- Online resize with no downtime
- DLM automates snapshot lifecycle
- Always unmount before detaching volumes
