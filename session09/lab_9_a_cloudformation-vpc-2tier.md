# Lab 9.A: CloudFormation Two-Tier VPC Architecture

## Overview
Deploy a two-tier VPC architecture using CloudFormation Infrastructure as Code. The template creates a VPC with public and private subnets, a web server behind a Classic Load Balancer, and a backend API in a private subnet. Single template deployment demonstrates repeatable, version-controlled infrastructure.

---

## Objectives
- Create CloudFormation template for two-tier architecture
- Deploy VPC with public and private subnets
- Launch Classic Load Balancer for web tier
- Deploy web server with simple HTML page
- Deploy backend Flask API in private subnet
- Configure security groups for tier isolation
- Access application through Load Balancer
- Clean up with stack deletion

---

## Prerequisites
- AWS CLI configured (`aws configure`)
- IAM permissions for CloudFormation, VPC, EC2, ELB
- Text editor for YAML
- Region: ap-southeast-2

---

## Architecture

```
Internet → Classic Load Balancer → Web Server (public) → Backend API (private)
```

---

## Step 1 – Create CloudFormation Template

```bash
# Set region
REGION="ap-southeast-2"
echo "REGION=$REGION"

# Create template file
cat > two-tier-stack.yaml <<'EOF'
AWSTemplateFormatVersion: '2010-09-09'
Description: 'Two-Tier VPC with Web and Backend API'

Parameters:
  LatestAmiId:
    Type: AWS::SSM::Parameter::Value<AWS::EC2::Image::Id>
    Default: /aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64

Resources:
  # VPC
  VPC:
    Type: AWS::EC2::VPC
    Properties:
      CidrBlock: 10.0.0.0/16
      EnableDnsHostnames: true
      Tags:
        - Key: Name
          Value: CF-VPC

  # Internet Gateway
  IGW:
    Type: AWS::EC2::InternetGateway
    Properties:
      Tags:
        - Key: Name
          Value: CF-IGW

  AttachGateway:
    Type: AWS::EC2::VPCGatewayAttachment
    Properties:
      VpcId: !Ref VPC
      InternetGatewayId: !Ref IGW

  # Public Subnet
  PublicSubnet:
    Type: AWS::EC2::Subnet
    Properties:
      VpcId: !Ref VPC
      CidrBlock: 10.0.1.0/24
      MapPublicIpOnLaunch: true
      AvailabilityZone: !Select [0, !GetAZs '']
      Tags:
        - Key: Name
          Value: Public-Subnet

  # Private Subnet
  PrivateSubnet:
    Type: AWS::EC2::Subnet
    Properties:
      VpcId: !Ref VPC
      CidrBlock: 10.0.2.0/24
      AvailabilityZone: !Select [0, !GetAZs '']
      Tags:
        - Key: Name
          Value: Private-Subnet

  # Public Route Table
  PublicRT:
    Type: AWS::EC2::RouteTable
    Properties:
      VpcId: !Ref VPC
      Tags:
        - Key: Name
          Value: Public-RT

  PublicRoute:
    Type: AWS::EC2::Route
    DependsOn: AttachGateway
    Properties:
      RouteTableId: !Ref PublicRT
      DestinationCidrBlock: 0.0.0.0/0
      GatewayId: !Ref IGW

  PublicSubnetRTAssoc:
    Type: AWS::EC2::SubnetRouteTableAssociation
    Properties:
      SubnetId: !Ref PublicSubnet
      RouteTableId: !Ref PublicRT

  # Security Group - Load Balancer
  LBSG:
    Type: AWS::EC2::SecurityGroup
    Properties:
      GroupDescription: Allow HTTP to Load Balancer
      VpcId: !Ref VPC
      SecurityGroupIngress:
        - IpProtocol: tcp
          FromPort: 80
          ToPort: 80
          CidrIp: 0.0.0.0/0
      Tags:
        - Key: Name
          Value: LB-SG

  # Security Group - Web Tier
  WebSG:
    Type: AWS::EC2::SecurityGroup
    Properties:
      GroupDescription: Allow traffic from LB
      VpcId: !Ref VPC
      SecurityGroupIngress:
        - IpProtocol: tcp
          FromPort: 80
          ToPort: 80
          SourceSecurityGroupId: !Ref LBSG
      SecurityGroupEgress:
        - IpProtocol: -1
          CidrIp: 0.0.0.0/0
      Tags:
        - Key: Name
          Value: Web-SG

  # Security Group - Backend Tier
  BackendSG:
    Type: AWS::EC2::SecurityGroup
    Properties:
      GroupDescription: Allow traffic from Web tier only
      VpcId: !Ref VPC
      SecurityGroupIngress:
        - IpProtocol: tcp
          FromPort: 5000
          ToPort: 5000
          SourceSecurityGroupId: !Ref WebSG
      SecurityGroupEgress:
        - IpProtocol: -1
          CidrIp: 0.0.0.0/0
      Tags:
        - Key: Name
          Value: Backend-SG

  # Backend API Instance
  BackendInstance:
    Type: AWS::EC2::Instance
    Properties:
      InstanceType: t2.micro
      ImageId: !Ref LatestAmiId
      SubnetId: !Ref PrivateSubnet
      SecurityGroupIds:
        - !Ref BackendSG
      Tags:
        - Key: Name
          Value: Backend-API
      UserData:
        Fn::Base64: !Sub |
          #!/bin/bash
          yum update -y
          yum install -y python3 python3-pip
          
          cat > /home/ec2-user/app.py <<'PYEOF'
          from flask import Flask, jsonify
          app = Flask(__name__)

          @app.route('/')
          def home():
              return jsonify({"message": "Backend API", "status": "running"})

          @app.route('/joke')
          def joke():
              return jsonify({"joke": "Why do programmers prefer dark mode? Because light attracts bugs!"})

          if __name__ == '__main__':
              app.run(host='0.0.0.0', port=5000)
          PYEOF
          
          pip3 install flask
          nohup python3 /home/ec2-user/app.py &

  # Web Server Instance
  WebInstance:
    Type: AWS::EC2::Instance
    DependsOn: BackendInstance
    Properties:
      InstanceType: t2.micro
      ImageId: !Ref LatestAmiId
      SubnetId: !Ref PublicSubnet
      SecurityGroupIds:
        - !Ref WebSG
      Tags:
        - Key: Name
          Value: Web-Server
      UserData:
        Fn::Base64: !Sub |
          #!/bin/bash
          yum update -y
          yum install -y httpd
          
          cat > /var/www/html/index.html <<HTMLEOF
          <!DOCTYPE html>
          <html>
          <head><title>CloudFormation Two-Tier App</title></head>
          <body style="font-family: Arial; max-width: 600px; margin: 50px auto; padding: 20px;">
              <h1>CloudFormation Two-Tier Architecture</h1>
              <p><strong>Web Tier:</strong> This server (public subnet)</p>
              <p><strong>Backend Tier:</strong> API at ${BackendInstance.PrivateIp}:5000 (private subnet)</p>
              <hr>
              <h3>Test Backend API:</h3>
              <button onclick="fetch('/api/').then(r=>r.json()).then(d=>document.getElementById('r').innerText=JSON.stringify(d,null,2))">Get Status</button>
              <button onclick="fetch('/api/joke').then(r=>r.json()).then(d=>document.getElementById('r').innerText=JSON.stringify(d,null,2))">Get Joke</button>
              <pre id="r" style="background: #f4f4f4; padding: 15px; margin-top: 20px; border-radius: 5px;"></pre>
          </body>
          </html>
          HTMLEOF
          
          cat > /etc/httpd/conf.d/proxy.conf <<PROXYEOF
          LoadModule proxy_module modules/mod_proxy.so
          LoadModule proxy_http_module modules/mod_proxy_http.so
          <Location /api>
              ProxyPass http://${BackendInstance.PrivateIp}:5000
              ProxyPassReverse http://${BackendInstance.PrivateIp}:5000
          </Location>
          PROXYEOF
          
          systemctl enable httpd
          systemctl start httpd

  # Classic Load Balancer
  LoadBalancer:
    Type: AWS::ElasticLoadBalancing::LoadBalancer
    DependsOn: WebInstance
    Properties:
      LoadBalancerName: CF-CLB
      Subnets:
        - !Ref PublicSubnet
      SecurityGroups:
        - !Ref LBSG
      Instances:
        - !Ref WebInstance
      Listeners:
        - LoadBalancerPort: 80
          InstancePort: 80
          Protocol: HTTP
      HealthCheck:
        Target: HTTP:80/
        HealthyThreshold: 2
        UnhealthyThreshold: 5
        Interval: 30
        Timeout: 5

Outputs:
  LoadBalancerURL:
    Description: Application URL
    Value: !Sub 'http://${LoadBalancer.DNSName}'
  
  JokeAPIURL:
    Description: Backend Joke API
    Value: !Sub 'http://${LoadBalancer.DNSName}/api/joke'
  
  VPCId:
    Description: VPC ID
    Value: !Ref VPC
EOF

echo "✅ CloudFormation template created: two-tier-stack.yaml"
```

---

## Step 2 – Validate Template

```bash
echo ""
echo "Validating CloudFormation template..."

aws cloudformation validate-template \
  --template-body file://two-tier-stack.yaml \
  --region "$REGION"

echo "✅ Template is valid"
```

---

## Step 3 – Deploy Stack

```bash
echo ""
echo "Deploying CloudFormation stack..."

STACK_NAME="two-tier-vpc-stack"
echo "STACK_NAME=$STACK_NAME"

aws cloudformation create-stack \
  --stack-name "$STACK_NAME" \
  --template-body file://two-tier-stack.yaml \
  --region "$REGION" \
  --tags Key=Project,Value=CloudFormation-Lab

echo "✅ Stack deployment initiated"
echo ""
echo "Waiting for stack creation (5-7 minutes)..."

aws cloudformation wait stack-create-complete \
  --stack-name "$STACK_NAME" \
  --region "$REGION"

echo "✅ Stack created successfully!"
```

---

## Step 4 – View Stack Outputs

```bash
echo ""
echo "Stack outputs:"

aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --region "$REGION" \
  --query 'Stacks[0].Outputs[*].{Key:OutputKey,Value:OutputValue}' \
  --output table

# Get URLs
APP_URL=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --region "$REGION" \
  --query 'Stacks[0].Outputs[?OutputKey==`LoadBalancerURL`].OutputValue' \
  --output text)

JOKE_URL=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --region "$REGION" \
  --query 'Stacks[0].Outputs[?OutputKey==`JokeAPIURL`].OutputValue' \
  --output text)

echo ""
echo "Application URL: $APP_URL"
echo "Joke API: $JOKE_URL"
```

---

## Step 5 – Test Application

```bash
echo ""
echo "Testing application (waiting 2 minutes for initialization)..."
sleep 120

echo ""
echo "Test 1: Backend status"
curl -s "${APP_URL}/api/" | python3 -m json.tool

echo ""
echo ""
echo "Test 2: Get joke"
curl -s "$JOKE_URL" | python3 -m json.tool

echo ""
echo ""
echo "✅ Application working!"
echo "Open in browser: $APP_URL"
```

---

## Step 6 – View Stack Resources

```bash
echo ""
echo "Stack resources:"

aws cloudformation describe-stack-resources \
  --stack-name "$STACK_NAME" \
  --region "$REGION" \
  --query 'StackResources[*].{Type:ResourceType,LogicalID:LogicalResourceId,Status:ResourceStatus}' \
  --output table
```

---

## Step 7 – Cleanup

```bash
echo ""
echo "Deleting CloudFormation stack..."

aws cloudformation delete-stack \
  --stack-name "$STACK_NAME" \
  --region "$REGION"

echo "Waiting for stack deletion..."

aws cloudformation wait stack-delete-complete \
  --stack-name "$STACK_NAME" \
  --region "$REGION"

echo "✅ Stack deleted successfully!"
```

---

## Summary

In this lab, you have:
- Created CloudFormation template with VPC, subnets, security groups, instances, and load balancer
- Deployed two-tier architecture with single command
- Configured web server in public subnet with Classic Load Balancer
- Deployed Flask API in private subnet (isolated from internet)
- Used CloudFormation intrinsic functions (!Ref, !GetAtt, !Sub)
- Tested application through Load Balancer DNS
- Cleaned up entire stack with one command

**Key Takeaways:**
- **Infrastructure as Code**: Entire architecture in ~150 lines YAML
- **Repeatability**: Deploy identical infrastructure instantly
- **Dependencies**: CloudFormation handles resource ordering
- **Rollback**: Automatic rollback on failure
- **Single Source of Truth**: Template is documentation

**CloudFormation Benefits:**
- Deploy in 7 minutes vs 30+ minutes manually
- Version control infrastructure code
- Consistent deployments across environments
- Easy cleanup (delete stack = delete everything)
- Self-documenting infrastructure

---

## Best Practices

**Template Design:**
- Use SSM Parameter Store for AMI IDs (automatic updates)
- Add Tags to all resources
- Use descriptive resource names
- Export Outputs for cross-stack references
- Keep templates under 200 lines for readability

**Security:**
- Private subnets for backend services
- Minimal security group rules
- No hardcoded credentials
- Use IAM roles instead of access keys

**Production Enhancements:**
- Multi-AZ deployment (add second subnet)
- Auto Scaling Group for web tier
- RDS database in private subnet
- CloudWatch alarms for monitoring
- Nested stacks for modularity

---

## Troubleshooting

**Stack creation fails:**
- Check CloudFormation Events tab for errors
- Verify IAM permissions
- Ensure AMI is available in region
- Check template syntax with validate-template

**Application not accessible:**
- Wait 5 minutes for UserData scripts
- Check instance health in Load Balancer
- Verify security group rules
- Check logs: `sudo cat /var/log/cloud-init-output.log`

**Backend API not responding:**
- Verify Flask service: `ps aux | grep flask`
- Check security group allows port 5000
- Test from web server: `curl http://<BackendIP>:5000/`
