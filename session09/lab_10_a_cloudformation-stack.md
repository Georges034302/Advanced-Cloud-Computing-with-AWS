# Lab 10.A: Deploy an automated EC2 and S3 stack using CloudFormation

## Overview
Use an AWS CloudFormation template to provision a simple, repeatable stack that includes:
- An S3 bucket (versioning + server-side encryption)
- An EC2 instance (with SSM support) behind a security group
- IAM role for the EC2 instance to allow SSM and CloudWatch Logs
This lab demonstrates authoring a CloudFormation template, deploying it with the AWS CLI, validating resources, and cleaning up.

## Objectives
- Create a CloudFormation template to deploy S3 and EC2 resources
- Deploy the stack via aws cloudformation deploy
- Validate S3 bucket, EC2 instance, security group, and SSM connectivity
- Clean up resources using CloudFormation delete-stack

## Prerequisites
- AWS CLI v2 configured
- An existing VPC and subnet ID to launch the EC2 instance in
- Key pair name for SSH (optional if using SSM)
- IAM permissions for CloudFormation, EC2, S3, IAM, and SSM

---

## CloudFormation template (example)
Save as session10/ec2-s3-stack.yaml.

```yaml
AWSTemplateFormatVersion: '2010-09-09'
Description: CloudFormation stack that creates an encrypted S3 bucket and an EC2 instance with SSM access.

Parameters:
  KeyName:
    Type: AWS::EC2::KeyPair::KeyName
    Description: EC2 KeyPair for SSH (optional if using SSM)
  VpcId:
    Type: AWS::EC2::VPC::Id
  SubnetId:
    Type: AWS::EC2::Subnet::Id
  AllowedCidr:
    Type: String
    Default: 0.0.0.0/0
    Description: CIDR to allow SSH (restrict in production)

Resources:
  AppBucket:
    Type: AWS::S3::Bucket
    Properties:
      BucketEncryption:
        ServerSideEncryptionConfiguration:
          - ServerSideEncryptionByDefault:
              SSEAlgorithm: AES256
      VersioningConfiguration:
        Status: Enabled
    DeletionPolicy: Retain

  InstanceRole:
    Type: AWS::IAM::Role
    Properties:
      AssumeRolePolicyDocument:
        Version: "2012-10-17"
        Statement:
          - Effect: Allow
            Principal:
              Service: ec2.amazonaws.com
            Action: sts:AssumeRole
      ManagedPolicyArns:
        - arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore
        - arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy

  InstanceProfile:
    Type: AWS::IAM::InstanceProfile
    Properties:
      Roles: [ !Ref InstanceRole ]

  AppSecurityGroup:
    Type: AWS::EC2::SecurityGroup
    Properties:
      GroupDescription: Allow SSH and HTTP to EC2
      VpcId: !Ref VpcId
      SecurityGroupIngress:
        - IpProtocol: tcp
          FromPort: 22
          ToPort: 22
          CidrIp: !Ref AllowedCidr
        - IpProtocol: tcp
          FromPort: 80
          ToPort: 80
          CidrIp: 0.0.0.0/0

  WebInstance:
    Type: AWS::EC2::Instance
    Properties:
      InstanceType: t3.micro
      KeyName: !Ref KeyName
      ImageId: ami-0abcdef1234567890 # replace with a region-appropriate AMI
      NetworkInterfaces:
        - AssociatePublicIpAddress: true
          DeviceIndex: 0
          SubnetId: !Ref SubnetId
          GroupSet: [ !Ref AppSecurityGroup ]
      IamInstanceProfile: !Ref InstanceProfile
      UserData:
        Fn::Base64: !Sub |
          #!/bin/bash -xe
          yum update -y
          yum install -y httpd aws-cli
          systemctl enable --now httpd
          echo "Hello from CloudFormation EC2 instance" > /var/www/html/index.html
          # put a sample object into the bucket (uses instance role)
          aws s3 cp /var/www/html/index.html s3://${AppBucket}/index.html || true

Outputs:
  BucketName:
    Description: S3 bucket created by the stack
    Value: !Ref AppBucket
  InstanceId:
    Description: EC2 instance id
    Value: !Ref WebInstance
  PublicIP:
    Description: Public IP of EC2 instance
    Value: !GetAtt WebInstance.PublicIp
```

---

## Deploy the stack (CLI)
Replace parameters before running.

```bash
STACK_NAME=lab-ec2-s3-stack
TEMPLATE_FILE=session10/ec2-s3-stack.yaml
aws cloudformation deploy \
  --stack-name $STACK_NAME \
  --template-file $TEMPLATE_FILE \
  --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM \
  --parameter-overrides KeyName=your-key VpcId=vpc-xxxxxxxx SubnetId=subnet-xxxxxxxx AllowedCidr=203.0.113.0/32 \
  --region us-east-1
```

Validate outputs:
```bash
aws cloudformation describe-stacks --stack-name $STACK_NAME --query 'Stacks[0].Outputs'
```

Validate resources:
- S3: aws s3 ls s3://<BucketName> and check versioning & encryption in console/CLI
- EC2: aws ec2 describe-instances --instance-ids <InstanceId>
- SSM: use aws ssm start-session --target <InstanceId> if SSM agent connected

---

## Validation checklist
- [ ] CloudFormation stack created without errors
- [ ] S3 bucket exists, encrypted, and versioning enabled
- [ ] EC2 instance running and reachable via SSM (or SSH if key allowed)
- [ ] Web server serving index page (http://<PublicIP>/)
- [ ] CloudFormation outputs present and correct

---

## Cleanup
Delete the stack (this removes EC2, SG, IAM resources). S3 bucket was created with DeletionPolicy: Retain to avoid accidental data loss — delete bucket contents first then delete bucket if desired.

```bash
aws cloudformation delete-stack --stack-name $STACK_NAME --region us-east-1
# if you want to remove the retained bucket:
# aws s3 rm s3://<BucketName> --recursive
# aws s3api delete-bucket --bucket <BucketName> --region us-east-1
```

## Notes & best practices
- Replace the placeholder AMI with a current regional AMI (Amazon Linux 2).
- Restrict AllowedCidr to your office/home IP for SSH.
- Use DeletionPolicy carefully (Retain for data buckets).
- Use CloudFormation Parameter Store or Secrets Manager for secrets rather than plaintext parameters.
- Consider using Launch Templates / Auto Scaling for production workloads.

## Summary
This lab demonstrates authoring and deploying a CloudFormation template that provisions an S3 bucket and an EC2 instance with the necessary IAM, security, and bootstrapping. Use this pattern to create repeatable, auditable infrastructure stacks.
