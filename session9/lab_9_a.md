# Lab 9.A: AWS CloudFormation Fundamentals and Infrastructure as Code

## Overview
This lab introduces AWS CloudFormation, a service that enables Infrastructure as Code (IaC) for AWS resources. You'll learn how to create templates, deploy stacks, manage stack updates, and use CloudFormation to automate infrastructure provisioning. This approach ensures consistent, repeatable deployments across environments.

## Objectives
- Understand CloudFormation concepts and template structure
- Create CloudFormation templates in YAML and JSON
- Deploy and manage CloudFormation stacks
- Use parameters, mappings, and outputs
- Implement intrinsic functions and pseudo parameters
- Handle stack updates and drift detection
- Use CloudFormation StackSets for multi-account deployment
- Implement cross-stack references
- Debug CloudFormation deployment issues

## Requirements
- AWS account with CloudFormation permissions
- Text editor or IDE with YAML support
- AWS CLI installed
- Understanding of AWS services (VPC, EC2, S3, RDS)
- Basic programming concepts

## Steps

### Step 1: Create Your First CloudFormation Template
1. Create a simple S3 bucket template:
   ```yaml
   # simple-s3.yaml
   AWSTemplateFormatVersion: '2010-09-09'
   Description: 'Simple S3 bucket template'
   
   Resources:
     MyS3Bucket:
       Type: AWS::S3::Bucket
       Properties:
         BucketName: !Sub 'my-cf-bucket-${AWS::AccountId}'
         VersioningConfiguration:
           Status: Enabled
         PublicAccessBlockConfiguration:
           BlockPublicAcls: true
           BlockPublicPolicy: true
           IgnorePublicAcls: true
           RestrictPublicBuckets: true
         Tags:
           - Key: Environment
             Value: Lab
           - Key: ManagedBy
             Value: CloudFormation
   
   Outputs:
     BucketName:
       Description: 'Name of the S3 bucket'
       Value: !Ref MyS3Bucket
     BucketArn:
       Description: 'ARN of the S3 bucket'
       Value: !GetAtt MyS3Bucket.Arn
   ```

2. Deploy via AWS Console:
   - Navigate to CloudFormation
   - Create stack → With new resources
   - Upload template file
   - Stack name: `simple-s3-stack`
   - Create stack

3. Deploy via AWS CLI:
   ```bash
   aws cloudformation create-stack \
     --stack-name simple-s3-stack \
     --template-body file://simple-s3.yaml
   
   # Check status
   aws cloudformation describe-stacks \
     --stack-name simple-s3-stack
   
   # Wait for completion
   aws cloudformation wait stack-create-complete \
     --stack-name simple-s3-stack
   ```

### Step 2: Use Parameters for Flexibility
1. Create template with parameters:
   ```yaml
   # parameterized-ec2.yaml
   AWSTemplateFormatVersion: '2010-09-09'
   Description: 'EC2 instance with parameters'
   
   Parameters:
     InstanceType:
       Description: 'EC2 instance type'
       Type: String
       Default: t2.micro
       AllowedValues:
         - t2.micro
         - t2.small
         - t2.medium
       ConstraintDescription: 'Must be a valid EC2 instance type'
     
     KeyName:
       Description: 'EC2 Key Pair for SSH access'
       Type: AWS::EC2::KeyPair::KeyName
     
     SSHLocation:
       Description: 'IP address range for SSH access'
       Type: String
       Default: '0.0.0.0/0'
       AllowedPattern: '^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})/(\d{1,2})$'
   
   Resources:
     EC2Instance:
       Type: AWS::EC2::Instance
       Properties:
         InstanceType: !Ref InstanceType
         KeyName: !Ref KeyName
         ImageId: !Sub '{{resolve:ssm:/aws/service/ami-amazon-linux-latest/amzn2-ami-hvm-x86_64-gp2}}'
         SecurityGroups:
           - !Ref InstanceSecurityGroup
         Tags:
           - Key: Name
             Value: !Sub '${AWS::StackName}-instance'
     
     InstanceSecurityGroup:
       Type: AWS::EC2::SecurityGroup
       Properties:
         GroupDescription: 'Enable SSH access'
         SecurityGroupIngress:
           - IpProtocol: tcp
             FromPort: 22
             ToPort: 22
             CidrIp: !Ref SSHLocation
   
   Outputs:
     InstanceId:
       Description: 'Instance ID'
       Value: !Ref EC2Instance
     PublicIP:
       Description: 'Public IP address'
       Value: !GetAtt EC2Instance.PublicIp
     PublicDNS:
       Description: 'Public DNS name'
       Value: !GetAtt EC2Instance.PublicDnsName
   ```

2. Deploy with parameters:
   ```bash
   aws cloudformation create-stack \
     --stack-name ec2-stack \
     --template-body file://parameterized-ec2.yaml \
     --parameters \
       ParameterKey=InstanceType,ParameterValue=t2.micro \
       ParameterKey=KeyName,ParameterValue=my-key-pair \
       ParameterKey=SSHLocation,ParameterValue=10.0.0.0/16
   ```

### Step 3: Use Mappings for Region-Specific Values
1. Create template with mappings:
   ```yaml
   Mappings:
     RegionMap:
       us-east-1:
         AMI: ami-0c55b159cbfafe1f0
       us-west-2:
         AMI: ami-0d1cd67c26f5fca19
       eu-west-1:
         AMI: ami-09ead922c1dad67e4
     
     EnvironmentMap:
       dev:
         InstanceType: t2.micro
       prod:
         InstanceType: t2.medium
   
   Parameters:
     Environment:
       Type: String
       Default: dev
       AllowedValues: [dev, prod]
   
   Resources:
     EC2Instance:
       Type: AWS::EC2::Instance
       Properties:
         InstanceType: !FindInMap [EnvironmentMap, !Ref Environment, InstanceType]
         ImageId: !FindInMap [RegionMap, !Ref 'AWS::Region', AMI]
   ```

### Step 4: Create VPC Infrastructure Template
1. Create comprehensive VPC template:
   ```yaml
   # vpc-infrastructure.yaml
   AWSTemplateFormatVersion: '2010-09-09'
   Description: 'VPC with public and private subnets'
   
   Parameters:
     VpcCIDR:
       Type: String
       Default: '10.0.0.0/16'
     
     PublicSubnet1CIDR:
       Type: String
       Default: '10.0.1.0/24'
     
     PublicSubnet2CIDR:
       Type: String
       Default: '10.0.2.0/24'
     
     PrivateSubnet1CIDR:
       Type: String
       Default: '10.0.10.0/24'
     
     PrivateSubnet2CIDR:
       Type: String
       Default: '10.0.11.0/24'
   
   Resources:
     VPC:
       Type: AWS::EC2::VPC
       Properties:
         CidrBlock: !Ref VpcCIDR
         EnableDnsHostnames: true
         EnableDnsSupport: true
         Tags:
           - Key: Name
             Value: !Sub '${AWS::StackName}-VPC'
     
     InternetGateway:
       Type: AWS::EC2::InternetGateway
       Properties:
         Tags:
           - Key: Name
             Value: !Sub '${AWS::StackName}-IGW'
     
     AttachGateway:
       Type: AWS::EC2::VPCGatewayAttachment
       Properties:
         VpcId: !Ref VPC
         InternetGatewayId: !Ref InternetGateway
     
     PublicSubnet1:
       Type: AWS::EC2::Subnet
       Properties:
         VpcId: !Ref VPC
         CidrBlock: !Ref PublicSubnet1CIDR
         AvailabilityZone: !Select [0, !GetAZs '']
         MapPublicIpOnLaunch: true
         Tags:
           - Key: Name
             Value: !Sub '${AWS::StackName}-Public-1'
     
     PublicSubnet2:
       Type: AWS::EC2::Subnet
       Properties:
         VpcId: !Ref VPC
         CidrBlock: !Ref PublicSubnet2CIDR
         AvailabilityZone: !Select [1, !GetAZs '']
         MapPublicIpOnLaunch: true
         Tags:
           - Key: Name
             Value: !Sub '${AWS::StackName}-Public-2'
     
     PrivateSubnet1:
       Type: AWS::EC2::Subnet
       Properties:
         VpcId: !Ref VPC
         CidrBlock: !Ref PrivateSubnet1CIDR
         AvailabilityZone: !Select [0, !GetAZs '']
         Tags:
           - Key: Name
             Value: !Sub '${AWS::StackName}-Private-1'
     
     PrivateSubnet2:
       Type: AWS::EC2::Subnet
       Properties:
         VpcId: !Ref VPC
         CidrBlock: !Ref PrivateSubnet2CIDR
         AvailabilityZone: !Select [1, !GetAZs '']
         Tags:
           - Key: Name
             Value: !Sub '${AWS::StackName}-Private-2'
     
     PublicRouteTable:
       Type: AWS::EC2::RouteTable
       Properties:
         VpcId: !Ref VPC
         Tags:
           - Key: Name
             Value: !Sub '${AWS::StackName}-Public-RT'
     
     PublicRoute:
       Type: AWS::EC2::Route
       DependsOn: AttachGateway
       Properties:
         RouteTableId: !Ref PublicRouteTable
         DestinationCidrBlock: '0.0.0.0/0'
         GatewayId: !Ref InternetGateway
     
     PublicSubnet1RouteTableAssociation:
       Type: AWS::EC2::SubnetRouteTableAssociation
       Properties:
         SubnetId: !Ref PublicSubnet1
         RouteTableId: !Ref PublicRouteTable
     
     PublicSubnet2RouteTableAssociation:
       Type: AWS::EC2::SubnetRouteTableAssociation
       Properties:
         SubnetId: !Ref PublicSubnet2
         RouteTableId: !Ref PublicRouteTable
   
   Outputs:
     VPCId:
       Description: 'VPC ID'
       Value: !Ref VPC
       Export:
         Name: !Sub '${AWS::StackName}-VPC-ID'
     
     PublicSubnets:
       Description: 'Public subnets'
       Value: !Join [',', [!Ref PublicSubnet1, !Ref PublicSubnet2]]
       Export:
         Name: !Sub '${AWS::StackName}-Public-Subnets'
     
     PrivateSubnets:
       Description: 'Private subnets'
       Value: !Join [',', [!Ref PrivateSubnet1, !Ref PrivateSubnet2]]
       Export:
         Name: !Sub '${AWS::StackName}-Private-Subnets'
   ```

2. Deploy VPC stack:
   ```bash
   aws cloudformation create-stack \
     --stack-name vpc-infrastructure \
     --template-body file://vpc-infrastructure.yaml
   ```

### Step 5: Use Cross-Stack References
1. Create application stack referencing VPC stack:
   ```yaml
   # app-stack.yaml
   Resources:
     AppLoadBalancer:
       Type: AWS::ElasticLoadBalancingV2::LoadBalancer
       Properties:
         Subnets: !Split
           - ','
           - !ImportValue vpc-infrastructure-Public-Subnets
         SecurityGroups:
           - !Ref ALBSecurityGroup
     
     ALBSecurityGroup:
       Type: AWS::EC2::SecurityGroup
       Properties:
         GroupDescription: 'ALB Security Group'
         VpcId: !ImportValue vpc-infrastructure-VPC-ID
         SecurityGroupIngress:
           - IpProtocol: tcp
             FromPort: 80
             ToPort: 80
             CidrIp: '0.0.0.0/0'
   ```

### Step 6: Implement Stack Updates
1. Modify existing template:
   ```yaml
   # Add to simple-s3.yaml
   Resources:
     MyS3Bucket:
       Properties:
         LifecycleConfiguration:
           Rules:
             - Id: DeleteOldVersions
               Status: Enabled
               NoncurrentVersionExpirationInDays: 30
   ```

2. Update stack:
   ```bash
   aws cloudformation update-stack \
     --stack-name simple-s3-stack \
     --template-body file://simple-s3.yaml
   
   # View change set before applying
   aws cloudformation create-change-set \
     --stack-name simple-s3-stack \
     --change-set-name my-changes \
     --template-body file://simple-s3.yaml
   
   aws cloudformation describe-change-set \
     --change-set-name my-changes \
     --stack-name simple-s3-stack
   
   # Execute change set
   aws cloudformation execute-change-set \
     --change-set-name my-changes \
     --stack-name simple-s3-stack
   ```

### Step 7: Use Conditions for Conditional Resource Creation
1. Template with conditions:
   ```yaml
   Parameters:
     CreateProdResources:
       Type: String
       Default: 'false'
       AllowedValues: ['true', 'false']
   
   Conditions:
     IsProduction: !Equals [!Ref CreateProdResources, 'true']
   
   Resources:
     DevInstance:
       Type: AWS::EC2::Instance
       Condition: !Not [!Condition IsProduction]
       Properties:
         InstanceType: t2.micro
         ImageId: ami-12345678
     
     ProdInstance:
       Type: AWS::EC2::Instance
       Condition: IsProduction
       Properties:
         InstanceType: t2.large
         ImageId: ami-12345678
   ```

### Step 8: Detect and Remediate Stack Drift
1. Detect drift:
   ```bash
   # Start drift detection
   aws cloudformation detect-stack-drift \
     --stack-name simple-s3-stack
   
   # Check drift status
   aws cloudformation describe-stack-drift-detection-status \
     --stack-drift-detection-id <detection-id>
   
   # View drift details
   aws cloudformation describe-stack-resource-drifts \
     --stack-name simple-s3-stack
   ```

2. Remediate drift:
   - Option 1: Update stack to match current state
   - Option 2: Restore resources to template-defined state

### Step 9: Use Nested Stacks
1. Create parent stack:
   ```yaml
   # parent-stack.yaml
   Resources:
     NetworkStack:
       Type: AWS::CloudFormation::Stack
       Properties:
         TemplateURL: https://s3.amazonaws.com/my-bucket/network.yaml
         Parameters:
           VpcCIDR: '10.0.0.0/16'
     
     ApplicationStack:
       Type: AWS::CloudFormation::Stack
       DependsOn: NetworkStack
       Properties:
         TemplateURL: https://s3.amazonaws.com/my-bucket/application.yaml
         Parameters:
           VPCId: !GetAtt NetworkStack.Outputs.VPCId
   ```

### Step 10: Implement Stack Deletion Policy
1. Protect resources from deletion:
   ```yaml
   Resources:
     MyDatabase:
       Type: AWS::RDS::DBInstance
       DeletionPolicy: Snapshot
       UpdateReplacePolicy: Snapshot
       Properties:
         # DB configuration
     
     MyBackupBucket:
       Type: AWS::S3::Bucket
       DeletionPolicy: Retain
       Properties:
         # Bucket configuration
   ```

2. Delete stack (protected resources retained):
   ```bash
   aws cloudformation delete-stack \
     --stack-name my-stack
   ```

## Validation
- [ ] CloudFormation template created successfully
- [ ] Stack deployed via console and CLI
- [ ] Parameters working correctly
- [ ] Mappings returning correct values
- [ ] Outputs displayed properly
- [ ] Cross-stack references working
- [ ] Stack updates completed successfully
- [ ] Change sets created and executed
- [ ] Drift detection completed
- [ ] Nested stacks deployed
- [ ] Deletion policies tested

## Cleanup
1. Delete all stacks (in reverse dependency order):
   ```bash
   aws cloudformation delete-stack --stack-name app-stack
   aws cloudformation delete-stack --stack-name vpc-infrastructure
   aws cloudformation delete-stack --stack-name ec2-stack
   aws cloudformation delete-stack --stack-name simple-s3-stack
   ```
2. Verify stacks deleted in console
3. Delete retained resources manually if needed

## Summary
In this lab, you mastered AWS CloudFormation for Infrastructure as Code. You created templates, deployed stacks, used parameters and mappings, implemented cross-stack references, and managed stack updates. CloudFormation enables version-controlled, repeatable infrastructure deployments, reducing manual errors and improving consistency across environments.

**Key Takeaways:**
- CloudFormation templates define infrastructure as code
- Parameters enable template reusability
- Mappings provide region and environment-specific values
- Outputs enable cross-stack references
- Change sets preview infrastructure changes
- Drift detection identifies manual modifications
- Deletion policies protect critical resources
- Nested stacks organize complex infrastructures
- Conditions enable conditional resource creation
- StackSets deploy across multiple accounts/regions
