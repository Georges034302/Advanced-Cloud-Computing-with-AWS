# Lab 4.D: ElastiCache Redis for Session Management

## Overview
This lab demonstrates how to use Amazon ElastiCache Redis as a high-performance in-memory data store for session management. You will deploy a Redis cluster, integrate it with a simple Flask web application, implement session storage, and test basic cache operations.

---

## Objectives
- Create ElastiCache Redis cluster in VPC
- Configure security groups for Redis access
- Deploy simple Flask application with Redis session management
- Test session persistence and basic Redis operations
- Clean up all resources

---

## Prerequisites
- AWS CLI configured (`aws configure`)
- Default VPC with subnets in multiple availability zones
- IAM permissions to manage ElastiCache, EC2, and VPC resources
- Basic understanding of caching concepts and Redis commands

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

# Set cache cluster identifier
CACHE_CLUSTER_ID="lab-redis-cluster"
echo "CACHE_CLUSTER_ID=$CACHE_CLUSTER_ID"

# Set cache configuration
CACHE_NODE_TYPE="cache.t3.micro"
echo "CACHE_NODE_TYPE=$CACHE_NODE_TYPE"

NUM_CACHE_NODES=1
echo "NUM_CACHE_NODES=$NUM_CACHE_NODES"

# Get default VPC ID
VPC_ID=$(aws ec2 describe-vpcs \
  --filters "Name=is-default,Values=true" \
  --query 'Vpcs[0].VpcId' \
  --output text \
  --region "$REGION")
echo "VPC_ID=$VPC_ID"

# Get first subnet ID
SUBNET_ID=$(aws ec2 describe-subnets \
  --filters "Name=vpc-id,Values=$VPC_ID" \
  --query 'Subnets[0].SubnetId' \
  --output text \
  --region "$REGION")
echo "SUBNET_ID=$SUBNET_ID"

# Get all subnet IDs for cache subnet group
SUBNET_IDS=$(aws ec2 describe-subnets \
  --filters "Name=vpc-id,Values=$VPC_ID" \
  --query 'Subnets[*].SubnetId' \
  --output text \
  --region "$REGION")
echo "SUBNET_IDS=$SUBNET_IDS"

# Verify AWS CLI is configured
aws sts get-caller-identity
```

---

## Step 2 – Create Security Groups

```bash
# Create security group for ElastiCache Redis
REDIS_SG_ID=$(aws ec2 create-security-group \
  --group-name "elasticache-redis-sg" \
  --description "Security group for ElastiCache Redis cluster" \
  --vpc-id "$VPC_ID" \
  --region "$REGION" \
  --query 'GroupId' \
  --output text)
echo "REDIS_SG_ID=$REDIS_SG_ID"

# Create security group for EC2 application servers
APP_SG_ID=$(aws ec2 create-security-group \
  --group-name "redis-app-sg" \
  --description "Security group for application servers accessing Redis" \
  --vpc-id "$VPC_ID" \
  --region "$REGION" \
  --query 'GroupId' \
  --output text)
echo "APP_SG_ID=$APP_SG_ID"

# Allow SSH access to application servers
aws ec2 authorize-security-group-ingress \
  --group-id "$APP_SG_ID" \
  --protocol tcp \
  --port 22 \
  --cidr 0.0.0.0/0 \
  --region "$REGION"

# Allow Flask port access
aws ec2 authorize-security-group-ingress \
  --group-id "$APP_SG_ID" \
  --protocol tcp \
  --port 5000 \
  --cidr 0.0.0.0/0 \
  --region "$REGION"

# Allow Redis access from application security group
aws ec2 authorize-security-group-ingress \
  --group-id "$REDIS_SG_ID" \
  --protocol tcp \
  --port 6379 \
  --source-group "$APP_SG_ID" \
  --region "$REGION"

echo "Security groups created successfully"

# Describe security groups
aws ec2 describe-security-groups \
  --group-ids "$REDIS_SG_ID" "$APP_SG_ID" \
  --query 'SecurityGroups[*].{GroupId:GroupId,GroupName:GroupName,Description:Description}' \
  --output table \
  --region "$REGION"
```

---

## Step 3 – Create Cache Subnet Group

```bash
# Create cache subnet group spanning multiple availability zones
aws elasticache create-cache-subnet-group \
  --cache-subnet-group-name "lab-cache-subnet-group" \
  --cache-subnet-group-description "Subnet group for ElastiCache Redis lab" \
  --subnet-ids $SUBNET_IDS \
  --region "$REGION"

echo "Cache subnet group created"

# Describe cache subnet group
aws elasticache describe-cache-subnet-groups \
  --cache-subnet-group-name "lab-cache-subnet-group" \
  --query 'CacheSubnetGroups[0].{Name:CacheSubnetGroupName,VpcId:VpcId,Subnets:Subnets[*].SubnetIdentifier}' \
  --output json \
  --region "$REGION" | jq '.'
```

---

## Step 4 – Create ElastiCache Redis Cluster

```bash
# Create Redis cluster (single node for simplicity)
echo "Creating ElastiCache Redis cluster..."

aws elasticache create-cache-cluster \
  --cache-cluster-id "$CACHE_CLUSTER_ID" \
  --cache-node-type "$CACHE_NODE_TYPE" \
  --engine redis \
  --engine-version "7.0" \
  --num-cache-nodes "$NUM_CACHE_NODES" \
  --cache-subnet-group-name "lab-cache-subnet-group" \
  --security-group-ids "$REDIS_SG_ID" \
  --region "$REGION"

echo "Redis cluster creation initiated..."
echo "This will take 5-10 minutes..."

# Wait for cluster to be available
echo "Waiting for Redis cluster to become available..."
aws elasticache wait cache-cluster-available \
  --cache-cluster-id "$CACHE_CLUSTER_ID" \
  --region "$REGION"

echo "✅ Redis cluster is now available!"

# Get cluster details
aws elasticache describe-cache-clusters \
  --cache-cluster-id "$CACHE_CLUSTER_ID" \
  --show-cache-node-info \
  --query 'CacheClusters[0].{ClusterId:CacheClusterId,Status:CacheClusterStatus,NodeType:CacheNodeType,Engine:Engine,EngineVersion:EngineVersion}' \
  --output table \
  --region "$REGION"
```

---

## Step 5 – Get Redis Endpoint

```bash
# Get Redis endpoint address
REDIS_ENDPOINT=$(aws elasticache describe-cache-clusters \
  --cache-cluster-id "$CACHE_CLUSTER_ID" \
  --show-cache-node-info \
  --query 'CacheClusters[0].CacheNodes[0].Endpoint.Address' \
  --output text \
  --region "$REGION")
echo "REDIS_ENDPOINT=$REDIS_ENDPOINT"

# Get Redis port
REDIS_PORT=$(aws elasticache describe-cache-clusters \
  --cache-cluster-id "$CACHE_CLUSTER_ID" \
  --show-cache-node-info \
  --query 'CacheClusters[0].CacheNodes[0].Endpoint.Port' \
  --output text \
  --region "$REGION")
echo "REDIS_PORT=$REDIS_PORT"

echo ""
echo "Redis connection details:"
echo "Host: $REDIS_ENDPOINT"
echo "Port: $REDIS_PORT"
echo ""
echo "Connection string: redis://${REDIS_ENDPOINT}:${REDIS_PORT}"
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
  --output text \
  --region "$REGION")
echo "AMI_ID=$AMI_ID"

# Display AMI details
aws ec2 describe-images \
  --image-ids "$AMI_ID" \
  --query 'Images[0].{ImageId:ImageId,Name:Name,CreationDate:CreationDate}' \
  --output table \
  --region "$REGION"
```

---

## Step 7 – Create Simple Flask Application

```bash
# Create Flask application directory
mkdir -p redis-app
cd redis-app

# Create simple Flask application with Redis session management
cat > app.py <<'EOF'
from flask import Flask, session, render_template_string
from flask_session import Session
import redis
import os
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'lab-secret-key'
app.config['SESSION_TYPE'] = 'redis'
app.config['SESSION_PERMANENT'] = False

# Redis connection
REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.environ.get('REDIS_PORT', 6379))

app.config['SESSION_REDIS'] = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    decode_responses=True
)

Session(app)

# HTML template
TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Redis Session Demo</title>
    <style>
        body { font-family: Arial; max-width: 600px; margin: 50px auto; padding: 20px; }
        .info { background: #f0f0f0; padding: 15px; margin: 10px 0; border-radius: 5px; }
        .button { padding: 10px 20px; margin: 5px; background: #007bff; color: white; 
                  text-decoration: none; border-radius: 5px; display: inline-block; }
    </style>
</head>
<body>
    <h1>Redis Session Demo</h1>
    <div class="info">
        <h2>Session Info</h2>
        <p><strong>Visit Count:</strong> {{ visits }}</p>
        <p><strong>Last Visit:</strong> {{ last_visit }}</p>
        <p><strong>Redis Host:</strong> {{ redis_host }}</p>
    </div>
    <div>
        <a href="/test" class="button">Test Redis</a>
        <a href="/clear" class="button">Clear Session</a>
        <a href="/" class="button">Refresh</a>
    </div>
    {% if test_result %}
    <div class="info"><h3>Test Result</h3><pre>{{ test_result }}</pre></div>
    {% endif %}
</body>
</html>
'''

@app.route('/')
def index():
    if 'visits' not in session:
        session['visits'] = 0
    session['visits'] += 1
    session['last_visit'] = datetime.now().isoformat()
    
    return render_template_string(
        TEMPLATE,
        visits=session['visits'],
        last_visit=session['last_visit'],
        redis_host=REDIS_HOST,
        test_result=None
    )

@app.route('/test')
def test():
    cache = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    
    # Simple Redis tests
    cache.set('test:key', 'Hello Redis!', ex=60)
    value = cache.get('test:key')
    result = f"SET/GET test: {value}\n"
    
    cache.hset('test:user', mapping={'name': 'John', 'email': 'john@example.com'})
    user = cache.hgetall('test:user')
    result += f"Hash test: {user}"
    
    return render_template_string(
        TEMPLATE,
        visits=session['visits'],
        last_visit=session['last_visit'],
        redis_host=REDIS_HOST,
        test_result=result
    )

@app.route('/clear')
def clear():
    session.clear()
    return '<html><body><h1>Session Cleared!</h1><a href="/">Go Back</a></body></html>'

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
EOF

# Create requirements.txt
cat > requirements.txt <<'EOF'
Flask==3.0.0
Flask-Session==0.5.0
redis==5.0.1
EOF

echo "Flask application created in redis-app/ directory"
ls -la

cd ..
```

---

## Step 8 – Create User Data Script for EC2

```bash
# Create user data script to install and run Flask app
cat > redis-app-userdata.sh <<EOF
#!/bin/bash
# Update system packages
dnf update -y

# Install Python 3 and pip
dnf install -y python3 python3-pip

# Create application directory
mkdir -p /home/ec2-user/app
cd /home/ec2-user/app

# Create Flask application
cat > app.py <<'PYAPP'
$(cat redis-app/app.py)
PYAPP

# Create requirements.txt
cat > requirements.txt <<'PYREQ'
$(cat redis-app/requirements.txt)
PYREQ

# Install Python dependencies
pip3 install -r requirements.txt

# Create systemd service for Flask app
cat > /etc/systemd/system/flask-app.service <<'SERVICE'
[Unit]
Description=Flask Redis Session Demo
After=network.target

[Service]
Type=simple
User=ec2-user
WorkingDirectory=/home/ec2-user/app
Environment="REDIS_HOST=${REDIS_ENDPOINT}"
Environment="REDIS_PORT=${REDIS_PORT}"
ExecStart=/usr/bin/python3 app.py
Restart=always

[Install]
WantedBy=multi-user.target
SERVICE

# Set ownership
chown -R ec2-user:ec2-user /home/ec2-user/app

# Enable and start Flask service
systemctl daemon-reload
systemctl enable flask-app
systemctl start flask-app

echo "Flask application started successfully" > /var/log/userdata-complete.log
EOF

echo "User data script created for EC2 instance"
```

---

## Step 9 – Launch EC2 Instance with Flask Application

```bash
# Launch EC2 instance with Flask application
echo "Launching EC2 instance with Flask application..."

INSTANCE_OUTPUT=$(aws ec2 run-instances \
  --image-id "$AMI_ID" \
  --instance-type t2.micro \
  --subnet-id "$SUBNET_ID" \
  --security-group-ids "$APP_SG_ID" \
  --user-data file://redis-app-userdata.sh \
  --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=redis-app-server},{Key=Lab,Value=4D}]" \
  --count 1 \
  --region "$REGION")

# Extract instance ID
INSTANCE_ID=$(echo "$INSTANCE_OUTPUT" | jq -r '.Instances[0].InstanceId')
echo "INSTANCE_ID=$INSTANCE_ID"

# Wait for instance to be running
echo "Waiting for EC2 instance to be running..."
aws ec2 wait instance-running \
  --instance-ids "$INSTANCE_ID" \
  --region "$REGION"

echo "✅ Instance is now running!"

# Get public IP address
PUBLIC_IP=$(aws ec2 describe-instances \
  --instance-ids "$INSTANCE_ID" \
  --query 'Reservations[0].Instances[0].PublicIpAddress' \
  --output text \
  --region "$REGION")
echo "PUBLIC_IP=$PUBLIC_IP"

# Display instance details
aws ec2 describe-instances \
  --instance-ids "$INSTANCE_ID" \
  --query 'Reservations[0].Instances[0].{InstanceId:InstanceId,PublicIP:PublicIpAddress,PrivateIP:PrivateIpAddress,State:State.Name}' \
  --output table \
  --region "$REGION"

echo ""
echo "================================================"
echo "APPLICATION ACCESS"
echo "================================================"
echo ""
echo "Wait 2-3 minutes for application to start"
echo ""
echo "Then access the application at:"
echo "  http://${PUBLIC_IP}:5000"
echo ""
echo "Test the following:"
echo "  1. Refresh the page - visit count increases"
echo "  2. Click 'Test Redis' - verify Redis operations"
echo "  3. Click 'Clear Session' - reset visit count"
echo "  4. Refresh again - visit count starts from 1"
echo ""
echo "================================================"
```

---

## Step 10 – Test Redis Connection 

```bash
# Create Redis connection test script
cat > test-redis.sh <<EOF
#!/bin/bash
# Test Redis connection from EC2 instance

echo "Testing Redis connection to ${REDIS_ENDPOINT}:${REDIS_PORT}"
echo ""

# Install redis-cli if needed
if ! command -v redis-cli &> /dev/null; then
    echo "Installing redis-cli..."
    sudo dnf install -y redis6
fi

echo "Testing PING..."
redis-cli -h ${REDIS_ENDPOINT} -p ${REDIS_PORT} PING

echo ""
echo "Setting test key..."
redis-cli -h ${REDIS_ENDPOINT} -p ${REDIS_PORT} SET test:connection "success"

echo ""
echo "Getting test key..."
redis-cli -h ${REDIS_ENDPOINT} -p ${REDIS_PORT} GET test:connection

echo ""
echo "Connection test completed!"
EOF

chmod +x test-redis.sh

echo ""
echo "Redis test script created: test-redis.sh"
echo ""
echo "To run on EC2 instance:"
echo "  1. SSH to instance: ssh -i <key.pem> ec2-user@${PUBLIC_IP}"
echo "  2. Copy and run the test script"
```

---

## Step 11 – Cleanup Resources

```bash
# Terminate EC2 instance
echo "Terminating EC2 instance..."
aws ec2 terminate-instances \
  --instance-ids "$INSTANCE_ID" \
  --region "$REGION"

# Wait for instance to terminate
echo "Waiting for instance to terminate..."
aws ec2 wait instance-terminated \
  --instance-ids "$INSTANCE_ID" \
  --region "$REGION"

echo "Instance terminated successfully"

# Delete ElastiCache cluster
echo "Deleting ElastiCache Redis cluster..."
aws elasticache delete-cache-cluster \
  --cache-cluster-id "$CACHE_CLUSTER_ID" \
  --region "$REGION"

# Wait for cluster deletion
echo "Waiting for cluster to be deleted (this may take a few minutes)..."
sleep 60

# Check cluster status
aws elasticache describe-cache-clusters \
  --cache-cluster-id "$CACHE_CLUSTER_ID" \
  --region "$REGION" 2>&1 || echo "Cache cluster deleted successfully"

# Delete cache subnet group
echo "Deleting cache subnet group..."
aws elasticache delete-cache-subnet-group \
  --cache-subnet-group-name "lab-cache-subnet-group" \
  --region "$REGION"

# Delete security groups
echo "Deleting security groups..."
sleep 10

aws ec2 delete-security-group \
  --group-id "$APP_SG_ID" \
  --region "$REGION"

aws ec2 delete-security-group \
  --group-id "$REDIS_SG_ID" \
  --region "$REGION"

# Verify security group deletion
aws ec2 describe-security-groups \
  --group-ids "$REDIS_SG_ID" \
  --region "$REGION" 2>&1 || echo "Security groups deleted"

# Delete local files
echo "Cleaning up local files..."
rm -rf redis-app/
rm -f redis-app-userdata.sh test-redis.sh

echo ""
echo "✅ Cleanup completed successfully!"
echo ""
echo "All resources deleted:"
echo "- EC2 instance"
echo "- ElastiCache Redis cluster"
echo "- Cache subnet group"
echo "- Security groups (2)"
echo "- Local application files"
```

---

## Summary

In this lab, you have:
- Created Amazon ElastiCache Redis cluster in VPC
- Configured security groups for secure Redis access
- Deployed simple Flask web application with Redis session management
- Tested basic Redis operations (strings and hashes)
- Verified session persistence with Redis

**Key Takeaways:**
- **In-Memory Performance**: Sub-millisecond latency for cache operations
- **Session Management**: Persistent sessions using Redis as session store
- **Simple Integration**: Easy to integrate Redis with web applications
- **Fully Managed**: AWS handles infrastructure, patching, and backups
- **Cost Effective**: cache.t3.micro is free tier eligible

**Common Redis Use Cases:**
| Use Case | Description |
|----------|-------------|
| **Session Store** | Web application session storage |
| **Cache** | Database query result caching |
| **Rate Limiting** | API request throttling |
| **Real-time Analytics** | Counters and leaderboards |
| **Message Queue** | Background job processing |

**Best Practices:**
- Use appropriate TTL (time-to-live) for cached data
- Implement connection pooling in applications
- Monitor cache memory usage
- Set maxmemory-policy for eviction strategy
- Use Redis data structures efficiently
- Secure Redis with VPC security groups

**Real-World Architectures:**
- **Web Applications**: Session storage for load-balanced servers
- **E-commerce**: Shopping cart persistence
- **Gaming**: Player sessions and leaderboards
- **APIs**: Response caching and rate limiting

---

## Additional Resources
- [Amazon ElastiCache for Redis](https://docs.aws.amazon.com/AmazonElastiCache/latest/red-ug/WhatIs.html)
- [Redis Commands Reference](https://redis.io/commands/)
- [ElastiCache Best Practices](https://docs.aws.amazon.com/AmazonElastiCache/latest/red-ug/BestPractices.html)
- [Flask-Session Documentation](https://flask-session.readthedocs.io/)
- [Caching Strategies](https://docs.aws.amazon.com/AmazonElastiCache/latest/red-ug/Strategies.html)

---
