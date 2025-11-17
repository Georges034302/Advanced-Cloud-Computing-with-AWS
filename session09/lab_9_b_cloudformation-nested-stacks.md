# Lab 9.B: CloudFormation Nested Stacks and Change Sets

## Overview
This lab demonstrates advanced CloudFormation patterns using nested stacks for modular infrastructure and Change Sets for safe deployments. You'll create a parent stack that references child stacks (network and compute), use cross-stack exports, preview changes with Change Sets before applying, and detect configuration drift.

---

## Objectives
- Create modular child stacks (network.yaml, compute.yaml)
- Build parent stack that references child stacks
- Use cross-stack references with Exports and Imports
- Create Change Sets to preview infrastructure changes
- Apply Change Sets safely
- Detect drift from manual changes
- Clean up nested stacks

---

## Prerequisites
- AWS CLI configured (`aws configure`)
- IAM permissions for CloudFormation, S3, VPC, EC2
- Understanding of CloudFormation basics (Lab 9.A)
- Region: ap-southeast-2

---

## Architecture

```
Parent Stack
  ├── Network Stack (VPC, Subnets, IGW, Routes)
  │     └── Exports: VPC-ID, Subnet-ID
  └── Compute Stack (EC2 Instance)
        └── Imports: VPC-ID, Subnet-ID from Network Stack
```

---

## Step 1 – Set Variables and Create Project Directory

```bash
# Set AWS region for nested stacks deployment
REGION="ap-southeast-2"

# Create S3 bucket name for storing child stack templates (required for nested stacks)
BUCKET_NAME="cf-nested-stacks-$(aws sts get-caller-identity --query Account --output text)"

# Create working directory for templates
mkdir -p /tmp/nested-stacks-lab
cd /tmp/nested-stacks-lab

echo "REGION: $REGION"
echo "BUCKET_NAME: $BUCKET_NAME"
```

---

## Step 2 – Create S3 Bucket for Templates

```bash
# Create S3 bucket to store child templates (nested stacks require S3 URLs)
if [ "$REGION" = "us-east-1" ]; then
    aws s3api create-bucket \
      --bucket "$BUCKET_NAME" \
      --region "$REGION"
else
    aws s3api create-bucket \
      --bucket "$BUCKET_NAME" \
      --region "$REGION" \
      --create-bucket-configuration LocationConstraint="$REGION"
fi

echo "$BUCKET_NAME"
```

---

## Step 3 – Create Network Child Stack Template

```bash
# Create network child stack (VPC, subnet, IGW, routes with cross-stack exports)
cat > network.yaml <<'EOF'
AWSTemplateFormatVersion: '2010-09-09'
Description: 'Network Stack - VPC with Public Subnet'

Resources:
  VPC:
    Type: AWS::EC2::VPC
    Properties:
      CidrBlock: 10.0.0.0/16
      EnableDnsHostnames: true
      Tags:
        - Key: Name
          Value: Nested-VPC

  InternetGateway:
    Type: AWS::EC2::InternetGateway
    Properties:
      Tags:
        - Key: Name
          Value: Nested-IGW

  AttachGateway:
    Type: AWS::EC2::VPCGatewayAttachment
    Properties:
      VpcId: !Ref VPC
      InternetGatewayId: !Ref InternetGateway

  PublicSubnet:
    Type: AWS::EC2::Subnet
    Properties:
      VpcId: !Ref VPC
      CidrBlock: 10.0.1.0/24
      MapPublicIpOnLaunch: true
      AvailabilityZone: !Select [0, !GetAZs '']
      Tags:
        - Key: Name
          Value: Nested-Public-Subnet

  PublicRouteTable:
    Type: AWS::EC2::RouteTable
    Properties:
      VpcId: !Ref VPC
      Tags:
        - Key: Name
          Value: Nested-Public-RT

  PublicRoute:
    Type: AWS::EC2::Route
    DependsOn: AttachGateway
    Properties:
      RouteTableId: !Ref PublicRouteTable
      DestinationCidrBlock: 0.0.0.0/0
      GatewayId: !Ref InternetGateway

  SubnetRouteTableAssociation:
    Type: AWS::EC2::SubnetRouteTableAssociation
    Properties:
      SubnetId: !Ref PublicSubnet
      RouteTableId: !Ref PublicRouteTable

Outputs:
  VPCId:
    Description: VPC ID
    Value: !Ref VPC
    Export:
      Name: !Sub '${AWS::StackName}-VPC-ID'

  PublicSubnetId:
    Description: Public Subnet ID
    Value: !Ref PublicSubnet
    Export:
      Name: !Sub '${AWS::StackName}-Subnet-ID'

  VPCCidr:
    Description: VPC CIDR Block
    Value: !GetAtt VPC.CidrBlock
    Export:
      Name: !Sub '${AWS::StackName}-VPC-CIDR'
EOF

echo "network.yaml"
```

---

## Step 4 – Create Compute Child Stack Template

```bash
# Create compute child stack (EC2 instance that imports VPC/subnet from network stack)
cat > compute.yaml <<'EOF'
AWSTemplateFormatVersion: '2010-09-09'
Description: 'Compute Stack - EC2 Instance with Security Group'

Parameters:
  NetworkStackName:
    Type: String
    Description: Name of the network stack to import values from
  
  LatestAmiId:
    Type: AWS::SSM::Parameter::Value<AWS::EC2::Image::Id>
    Default: /aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64

Resources:
  SecurityGroup:
    Type: AWS::EC2::SecurityGroup
    Properties:
      GroupDescription: Allow HTTP and SSH
      VpcId: !ImportValue 
        Fn::Sub: '${NetworkStackName}-VPC-ID'
      SecurityGroupIngress:
        - IpProtocol: tcp
          FromPort: 80
          ToPort: 80
          CidrIp: 0.0.0.0/0
          Description: Allow HTTP
        - IpProtocol: tcp
          FromPort: 22
          ToPort: 22
          CidrIp: 0.0.0.0/0
          Description: Allow SSH
      Tags:
        - Key: Name
          Value: Nested-Web-SG

  WebInstance:
    Type: AWS::EC2::Instance
    Properties:
      InstanceType: t2.micro
      ImageId: !Ref LatestAmiId
      SubnetId: !ImportValue
        Fn::Sub: '${NetworkStackName}-Subnet-ID'
      SecurityGroupIds:
        - !Ref SecurityGroup
      Tags:
        - Key: Name
          Value: Nested-Web-Server
      UserData:
        Fn::Base64: !Sub |
          #!/bin/bash
          yum update -y
          yum install -y httpd
          
          cat > /var/www/html/index.html <<HTMLEOF
          <!DOCTYPE html>
          <html>
          <head><title>Nested Stacks Demo</title></head>
          <body style="font-family: Arial; text-align: center; padding: 50px;">
              <h1>CloudFormation Nested Stacks</h1>
              <p>This EC2 instance was deployed using nested stacks</p>
              <p><strong>Network Stack:</strong> Provided VPC and Subnet</p>
              <p><strong>Compute Stack:</strong> Created this instance</p>
              <p><strong>Instance ID:</strong> $(ec2-metadata --instance-id | cut -d' ' -f2)</p>
          </body>
          </html>
          HTMLEOF
          
          systemctl enable httpd
          systemctl start httpd

Outputs:
  InstanceId:
    Description: EC2 Instance ID
    Value: !Ref WebInstance
  
  PublicIP:
    Description: Instance Public IP
    Value: !GetAtt WebInstance.PublicIp
  
  WebURL:
    Description: Web Application URL
    Value: !Sub 'http://${WebInstance.PublicIp}'
EOF

echo "compute.yaml"
```

---

## Step 5 – Upload Child Templates to S3

```bash
# Upload child templates to S3 (parent stack will reference these URLs)
aws s3 cp network.yaml s3://"$BUCKET_NAME"/network.yaml --region "$REGION"
aws s3 cp compute.yaml s3://"$BUCKET_NAME"/compute.yaml --region "$REGION"

# Generate S3 URLs for parent stack template
NETWORK_URL="https://s3.${REGION}.amazonaws.com/${BUCKET_NAME}/network.yaml"
COMPUTE_URL="https://s3.${REGION}.amazonaws.com/${BUCKET_NAME}/compute.yaml"

echo "NETWORK_URL: $NETWORK_URL"
echo "COMPUTE_URL: $COMPUTE_URL"
```

---

## Step 6 – Create Parent Stack Template

```bash
# Create parent stack that orchestrates network and compute child stacks
cat > parent.yaml <<EOF
AWSTemplateFormatVersion: '2010-09-09'
Description: 'Parent Stack - Orchestrates Network and Compute Stacks'

Resources:
  NetworkStack:
    Type: AWS::CloudFormation::Stack
    Properties:
      TemplateURL: ${NETWORK_URL}
      Tags:
        - Key: Name
          Value: Network-Child-Stack

  ComputeStack:
    Type: AWS::CloudFormation::Stack
    DependsOn: NetworkStack
    Properties:
      TemplateURL: ${COMPUTE_URL}
      Parameters:
        NetworkStackName: !GetAtt NetworkStack.Outputs.VPCId
      Tags:
        - Key: Name
          Value: Compute-Child-Stack

Outputs:
  VPCId:
    Description: VPC ID from Network Stack
    Value: !GetAtt NetworkStack.Outputs.VPCId
  
  SubnetId:
    Description: Subnet ID from Network Stack
    Value: !GetAtt NetworkStack.Outputs.PublicSubnetId
  
  InstanceId:
    Description: EC2 Instance ID from Compute Stack
    Value: !GetAtt ComputeStack.Outputs.InstanceId
  
  WebURL:
    Description: Web Application URL
    Value: !GetAtt ComputeStack.Outputs.WebURL
EOF

echo "parent.yaml"
```

---

## Step 7 – Validate Parent Template

```bash
# Validate parent template syntax and structure
aws cloudformation validate-template \
  --template-body file://parent.yaml \
  --region "$REGION" \
  --query 'Description' \
  --output text
```

---

## Step 8 – Create Change Set (Preview Changes)

```bash
# Create Change Set to preview what will be deployed (safe preview before execution)
STACK_NAME="nested-stacks-parent"
CHANGE_SET_NAME="initial-deployment"

aws cloudformation create-change-set \
  --stack-name "$STACK_NAME" \
  --change-set-name "$CHANGE_SET_NAME" \
  --template-body file://parent.yaml \
  --change-set-type CREATE \
  --region "$REGION" \
  --tags Key=Project,Value=Nested-Stacks-Lab

# Wait for Change Set to be ready for review
aws cloudformation wait change-set-create-complete \
  --stack-name "$STACK_NAME" \
  --change-set-name "$CHANGE_SET_NAME" \
  --region "$REGION"

echo "STACK_NAME: $STACK_NAME"
echo "CHANGE_SET_NAME: $CHANGE_SET_NAME"
```

---

## Step 9 – View Change Set Details

```bash
# Display what resources will be created/modified/deleted
aws cloudformation describe-change-set \
  --stack-name "$STACK_NAME" \
  --change-set-name "$CHANGE_SET_NAME" \
  --region "$REGION" \
  --query 'Changes[*].ResourceChange.{Action:Action,Resource:LogicalResourceId,Type:ResourceType}' \
  --output table
```

---

## Step 10 – Execute Change Set (Deploy Stack)

```bash
# Execute Change Set to deploy all resources (parent and child stacks)
aws cloudformation execute-change-set \
  --stack-name "$STACK_NAME" \
  --change-set-name "$CHANGE_SET_NAME" \
  --region "$REGION"

# Wait for stack creation to complete (5-7 minutes)
aws cloudformation wait stack-create-complete \
  --stack-name "$STACK_NAME" \
  --region "$REGION"

echo "$STACK_NAME"
```

---

## Step 11 – View Stack Outputs

```bash
# Display parent stack outputs (aggregated from child stacks)
aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --region "$REGION" \
  --query 'Stacks[0].Outputs[*].{Key:OutputKey,Value:OutputValue}' \
  --output table

# Extract web application URL
WEB_URL=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --region "$REGION" \
  --query 'Stacks[0].Outputs[?OutputKey==`WebURL`].OutputValue' \
  --output text)

echo "WEB_URL: $WEB_URL"
```

---

## Step 12 – View Nested Stacks

```bash
# List all stacks (parent + child stacks created automatically)
aws cloudformation list-stacks \
  --region "$REGION" \
  --stack-status-filter CREATE_COMPLETE \
  --query 'StackSummaries[?contains(StackName, `nested-stacks`)].{Name:StackName,Status:StackStatus,Created:CreationTime}' \
  --output table
```

---

## Step 13 – Test Application

```bash
# Wait for UserData script to install and start httpd
sleep 120

# Test web application
curl -s "$WEB_URL"

# Open in browser
"$BROWSER" "$WEB_URL"

echo "WEB_URL: $WEB_URL"
```

---

## Step 14 – Make Manual Change (Simulate Drift)

```bash
# Get instance ID from stack outputs
INSTANCE_ID=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --region "$REGION" \
  --query 'Stacks[0].Outputs[?OutputKey==`InstanceId`].OutputValue' \
  --output text)

# Add manual tag outside CloudFormation (simulates configuration drift)
aws ec2 create-tags \
  --resources "$INSTANCE_ID" \
  --tags Key=ManualTag,Value=This-Was-Added-Manually \
  --region "$REGION"

echo "INSTANCE_ID: $INSTANCE_ID (manual tag added)"
```

---

## Step 15 – Detect Drift

```bash
# Start drift detection to identify manual changes outside CloudFormation
DRIFT_ID=$(aws cloudformation detect-stack-drift \
  --stack-name "$STACK_NAME" \
  --region "$REGION" \
  --query 'StackDriftDetectionId' \
  --output text)

# Wait for drift detection to complete
sleep 10

# Display drift detection results
aws cloudformation describe-stack-drift-detection-status \
  --stack-drift-detection-id "$DRIFT_ID" \
  --region "$REGION" \
  --query '{Status:DetectionStatus,DriftStatus:StackDriftStatus}' \
  --output table

echo "DRIFT_ID: $DRIFT_ID"
```

---

## Step 16 – Create Change Set for Update

```bash
# Create updated parent template with additional tags
cat > parent-updated.yaml <<EOF
AWSTemplateFormatVersion: '2010-09-09'
Description: 'Parent Stack - Orchestrates Network and Compute Stacks (Updated)'

Resources:
  NetworkStack:
    Type: AWS::CloudFormation::Stack
    Properties:
      TemplateURL: ${NETWORK_URL}
      Tags:
        - Key: Name
          Value: Network-Child-Stack
        - Key: Updated
          Value: 'true'

  ComputeStack:
    Type: AWS::CloudFormation::Stack
    DependsOn: NetworkStack
    Properties:
      TemplateURL: ${COMPUTE_URL}
      Parameters:
        NetworkStackName: !GetAtt NetworkStack.Outputs.VPCId
      Tags:
        - Key: Name
          Value: Compute-Child-Stack
        - Key: Updated
          Value: 'true'

Outputs:
  VPCId:
    Description: VPC ID from Network Stack
    Value: !GetAtt NetworkStack.Outputs.VPCId
  
  SubnetId:
    Description: Subnet ID from Network Stack
    Value: !GetAtt NetworkStack.Outputs.PublicSubnetId
  
  InstanceId:
    Description: EC2 Instance ID from Compute Stack
    Value: !GetAtt ComputeStack.Outputs.InstanceId
  
  WebURL:
    Description: Web Application URL
    Value: !GetAtt ComputeStack.Outputs.WebURL
  
  StackVersion:
    Description: Stack Version
    Value: 'v2.0'
EOF

# Create Change Set to preview update (shows what will be modified)
UPDATE_CHANGE_SET="update-tags"

aws cloudformation create-change-set \
  --stack-name "$STACK_NAME" \
  --change-set-name "$UPDATE_CHANGE_SET" \
  --template-body file://parent-updated.yaml \
  --change-set-type UPDATE \
  --region "$REGION"

sleep 10

# Display what will be modified
aws cloudformation describe-change-set \
  --stack-name "$STACK_NAME" \
  --change-set-name "$UPDATE_CHANGE_SET" \
  --region "$REGION" \
  --query 'Changes[*].ResourceChange.{Action:Action,Resource:LogicalResourceId,Details:Details}' \
  --output table

echo "UPDATE_CHANGE_SET: $UPDATE_CHANGE_SET (not executed, will be deleted in cleanup)"
```

---

## Step 17 – Cleanup

```bash
# Delete Change Set (not executed)
aws cloudformation delete-change-set \
  --stack-name "$STACK_NAME" \
  --change-set-name "$UPDATE_CHANGE_SET" \
  --region "$REGION" 2>/dev/null || true

# Delete parent stack (automatically deletes all child stacks)
aws cloudformation delete-stack \
  --stack-name "$STACK_NAME" \
  --region "$REGION"

# Wait for complete deletion
aws cloudformation wait stack-delete-complete \
  --stack-name "$STACK_NAME" \
  --region "$REGION"

# Delete S3 bucket and templates
aws s3 rm s3://"$BUCKET_NAME" --recursive --region "$REGION"
aws s3api delete-bucket --bucket "$BUCKET_NAME" --region "$REGION"

# Delete local files
cd ~ && rm -rf /tmp/nested-stacks-lab

echo "Cleanup complete"
```

---

## Summary

In this lab, you have:
- Created modular child stacks (network.yaml, compute.yaml)
- Built parent stack orchestrating child stacks
- Uploaded templates to S3 for nested stack references
- Used cross-stack Exports and Imports for resource sharing
- Created Change Set to preview deployment before applying
- Executed Change Set to deploy nested stacks
- Simulated configuration drift with manual changes
- Detected drift using CloudFormation drift detection
- Created Change Set for updates to preview modifications
- Cleaned up all resources including nested stacks

**Key Takeaways:**
- **Nested Stacks**: Modular, reusable infrastructure components
- **Change Sets**: Safe deployments by previewing changes first
- **Cross-Stack References**: Share resources between stacks with Exports/Imports
- **Drift Detection**: Identify manual changes outside CloudFormation
- **Automatic Cleanup**: Deleting parent stack removes all child stacks

**Nested Stacks Benefits:**
- Break large templates into manageable pieces
- Reuse common patterns (network, database, compute)
- Independent updates to specific components
- Clear separation of concerns
- Version control for each stack

**Change Sets Benefits:**
- Preview changes before applying (no surprises)
- Review resource modifications, additions, deletions
- Approve or reject changes
- Production-safe deployment workflow
- Rollback capability if issues detected

---

## Best Practices

**Nested Stacks:**
- Store child templates in S3 (required for nested stacks)
- Use consistent naming conventions for outputs
- Keep each stack focused on single responsibility
- Use parameters for cross-stack communication
- Version child templates (v1.0, v2.0) in S3 paths

**Change Sets:**
- Always create Change Set before updates
- Review all changes carefully before execution
- Use descriptive Change Set names (update-tags, add-monitoring)
- Delete Change Sets after execution to avoid confusion
- Test Change Sets in dev before production

**Cross-Stack References:**
- Export only values needed by other stacks
- Use descriptive export names (StackName-Resource-Type)
- Don't delete stacks with exported values still in use
- Document dependencies between stacks

**Drift Detection:**
- Run drift detection regularly (weekly)
- Investigate all detected drift
- Update templates to match desired state
- Prevent manual changes in production (use Change Sets)

---

## Production Enhancements

1. **Stack Policies**
   ```bash
   # Prevent deletion of critical resources
   aws cloudformation set-stack-policy \
     --stack-name $STACK_NAME \
     --stack-policy-body '{
       "Statement": [{
         "Effect": "Deny",
         "Action": "Update:Delete",
         "Principal": "*",
         "Resource": "*"
       }]
     }'
   ```

2. **Termination Protection**
   ```bash
   # Prevent accidental stack deletion
   aws cloudformation update-termination-protection \
     --stack-name $STACK_NAME \
     --enable-termination-protection
   ```

3. **SNS Notifications**
   ```yaml
   # Add to parent stack
   NotificationARNs:
     - !Ref SNSTopic
   ```

4. **CI/CD Integration**
   - GitHub Actions or CodePipeline
   - Automated Change Set creation on PR
   - Manual approval before execution
   - Automated drift detection

---

## Troubleshooting

**Nested stack creation fails:**
- Verify S3 URLs are accessible (check bucket policy)
- Ensure templates are valid YAML
- Check CloudFormation Events for specific errors
- Verify IAM permissions for nested stack operations

**Change Set shows no changes:**
- Template is identical to current stack
- Only metadata or descriptions changed
- No actual resource modifications

**Drift detection fails:**
- Some resources don't support drift detection
- Check DetectionStatus for specific errors
- Not all resource properties support drift detection

**Cannot delete stack:**
- Check for exported values still in use by other stacks
- Verify no termination protection enabled
- Review stack dependencies

---

## Additional Resources

- [CloudFormation Nested Stacks](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/using-cfn-nested-stacks.html)
- [Change Sets Documentation](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/using-cfn-updating-stacks-changesets.html)
- [Drift Detection Guide](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/using-cfn-stack-drift.html)
- [Cross-Stack References](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/walkthrough-crossstackref.html)
