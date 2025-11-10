# Lab 3.B: Attach and manage EBS volumes and snapshots for EC2 instances

## Overview
This lab demonstrates how to create, attach, format, resize, snapshot, restore, and share Amazon EBS volumes for EC2 instances. You will practice safe snapshot workflows and automate snapshot lifecycle using AWS Data Lifecycle Manager (DLM).

## Objectives
- Create and attach EBS volumes to an EC2 instance
- Format and mount volumes on Linux
- Resize volumes and grow the filesystem
- Create point-in-time EBS snapshots and restore volumes from snapshots
- Share snapshots (encrypted vs unencrypted considerations)
- Automate snapshots with DLM and perform cleanup

## Prerequisites
- AWS CLI configured and authenticated
- An EC2 instance running in the target AZ (INSTANCE_ID)
- jq (optional) for parsing JSON
- sudo access on the EC2 instance

---

## Quick notes
- EBS volumes exist in a single AZ; create/restore in the same AZ.
- Snapshots are incremental and stored in S3 (transparent).
- Encrypted snapshots can only be shared with AWS accounts when permissions and CMK allow it.

---

## Steps (CLI examples)

Replace placeholders: INSTANCE_ID, AVAILABILITY_ZONE (e.g., us-east-1a), DEVICE_NAME (e.g., /dev/sdf or /dev/xvdf), VOLUME_SIZE (GiB), VOLUME_TYPE (gp3|gp2|io2), SNAPSHOT_ID, KMS_KEY_ID, TARGET_ACCOUNT_ID.

### 1. Create a new EBS volume
```bash
aws ec2 create-volume \
  --availability-zone $AVAILABILITY_ZONE \
  --size 10 \
  --volume-type gp3 \
  --tag-specifications 'ResourceType=volume,Tags=[{Key=Name,Value=lab-ebs-volume}]' \
  --query 'VolumeId' --output text
# save to VOLUME_ID
```

Wait until available:
```bash
aws ec2 wait volume-available --volume-ids $VOLUME_ID
```

### 2. Attach the volume to an instance
```bash
aws ec2 attach-volume --volume-id $VOLUME_ID --instance-id $INSTANCE_ID --device $DEVICE_NAME
aws ec2 wait volume-in-use --volume-ids $VOLUME_ID
```

### 3. Format and mount the volume (on the EC2 instance)
SSH to the instance and run (example uses ext4):
```bash
sudo mkfs -t ext4 $DEVICE_NAME
sudo mkdir -p /mnt/ebs-data
sudo mount $DEVICE_NAME /mnt/ebs-data
# verify
df -h /mnt/ebs-data
```
To mount persistently, add to /etc/fstab using UUID:
```bash
sudo blkid $DEVICE_NAME
# copy UUID and add line to /etc/fstab: UUID=... /mnt/ebs-data ext4 defaults,nofail 0 2
```

### 4. Expand an EBS volume (online)
Increase size:
```bash
aws ec2 modify-volume --volume-id $VOLUME_ID --size 20
# wait for modification to complete
aws ec2 wait volume-available --volume-ids $VOLUME_ID
```
On the instance:
```bash
# for NVMe devices (modern Nitro instances) device path may differ, e.g., /dev/nvme1n1
sudo lsblk
# grow partition if partitioned (example using growpart)
sudo growpart /dev/xvdf 1   # if partition 1 exists
sudo resize2fs /dev/xvdf1   # ext4 example
# or for unpartitioned devices:
sudo resize2fs $DEVICE_NAME
```

### 5. Create an EBS snapshot (point-in-time)
```bash
aws ec2 create-snapshot --volume-id $VOLUME_ID --description "lab snapshot" --tag-specifications 'ResourceType=snapshot,Tags=[{Key=Name,Value=lab-snapshot}]' --query 'SnapshotId' --output text
# wait
aws ec2 wait snapshot-completed --snapshot-ids $SNAPSHOT_ID
```
For consistent filesystem snapshots, stop the instance or freeze the filesystem (fsfreeze) before snapshot, or use application-level quiescing.

### 6. Restore a volume from snapshot
```bash
aws ec2 create-volume --availability-zone $AVAILABILITY_ZONE --snapshot-id $SNAPSHOT_ID --volume-type gp3 --query 'VolumeId' --output text
aws ec2 wait volume-available --volume-ids $RESTORED_VOLUME_ID
aws ec2 attach-volume --volume-id $RESTORED_VOLUME_ID --instance-id $INSTANCE_ID --device /dev/sdg
```

### 7. Share snapshots (unencrypted) and share encrypted snapshots with CMK setup
- Unencrypted snapshot: modify snapshot attribute to add createVolumePermission for TARGET_ACCOUNT_ID.
```bash
aws ec2 modify-snapshot-attribute --snapshot-id $SNAPSHOT_ID --attribute createVolumePermission --operation-type add --user-ids $TARGET_ACCOUNT_ID
```
- Encrypted snapshot: share the CMK with the target account and copy snapshot into target account (recommended) — follow KMS sharing docs.

### 8. Automate snapshots with Data Lifecycle Manager (DLM)
Create a basic daily snapshot policy (simplified example):
```bash
cat > dlm-policy.json <<'EOF'
{
  "Description": "Daily EBS snapshot for lab volumes",
  "State": "ENABLED",
  "PolicyDetails": {
    "ResourceTypes": ["VOLUME"],
    "TargetTags": [{"Key":"Backup","Value":"daily"}],
    "Schedules": [
      {
        "Name":"daily-snapshot",
        "CreateRule":{"Interval":24,"IntervalUnit":"HOURS"},
        "RetainRule":{"Count":7}
      }
    ]
  }
}
EOF

aws dlm create-lifecycle-policy --cli-input-json file://dlm-policy.json --query 'PolicyId' --output text
```
Tag volumes with Key=Backup,Value=daily to include them.

---

## Validation Checklist
- [ ] Volume created and attached
- [ ] Filesystem formatted and mounted
- [ ] Data persists across reboots
- [ ] Volume expanded and filesystem grown
- [ ] Snapshot created and completed
- [ ] Volume restored from snapshot and data verified
- [ ] Snapshot sharing workflow tested (if applicable)
- [ ] DLM policy in place and volumes tagged

---

## Cleanup
```bash
# detach volumes
aws ec2 detach-volume --volume-id $VOLUME_ID || true
aws ec2 wait volume-available --volume-ids $VOLUME_ID || true

# delete restored volumes (if any)
aws ec2 delete-volume --volume-id $RESTORED_VOLUME_ID || true

# delete snapshot(s)
aws ec2 delete-snapshot --snapshot-id $SNAPSHOT_ID || true

# remove DLM policy
aws dlm delete-lifecycle-policy --policy-id $POLICY_ID || true
```
Also unmount and remove fstab entries on the EC2 instance before deleting volumes.

## Summary
This lab covers practical EBS operations: provisioning, attaching, formatting, resizing, snapshotting, restoring, sharing, and automating backups. Follow AWS best practices for consistent snapshots, encryption, and lifecycle policies to protect data and control costs.
