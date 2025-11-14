# Lab 4.D: ElastiCache Redis for Session Management

<img width="935" height="499" alt="IMG" src="https://github.com/user-attachments/assets/b829598b-b691-4adf-a9aa-7322d84db45e" />

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
# Set AWS region (Sydney, Australia)
REGION=ap-southeast-2
echo "REGION=$REGION"

# Set cache cluster identifier
CACHE_CLUSTER_ID=lab-redis-cluster
echo "CACHE_CLUSTER_ID=$CACHE_CLUSTER_ID"

# Set cache node type (t3.micro for cost efficiency)
CACHE_NODE_TYPE=cache.t3.micro
echo "CACHE_NODE_TYPE=$CACHE_NODE_TYPE"

# Set number of cache nodes (single node for simplicity)
NUM_CACHE_NODES=1
echo "NUM_CACHE_NODES=$NUM_CACHE_NODES"

# Get default VPC ID
VPC_ID=$(aws ec2 describe-vpcs \
  --filters "Name=is-default,Values=true" \
  --query 'Vpcs[0].VpcId' \
  --output text \
  --region "$REGION")
echo "VPC_ID=$VPC_ID"

# Get first subnet ID for EC2 instance
SUBNET_ID=$(aws ec2 describe-subnets \
  --filters "Name=vpc-id,Values=$VPC_ID" \
  --query 'Subnets[0].SubnetId' \
  --output text \
  --region "$REGION")
echo "SUBNET_ID=$SUBNET_ID"

# Get all subnet IDs for cache subnet group (multi-AZ support)
SUBNET_IDS=$(aws ec2 describe-subnets \
  --filters "Name=vpc-id,Values=$VPC_ID" \
  --query 'Subnets[*].SubnetId' \
  --output text \
  --region "$REGION")
echo "SUBNET_IDS=$SUBNET_IDS"
```

---

## Step 2 – Create Security Groups

```bash
# Create security group for ElastiCache Redis cluster
REDIS_SG_ID=$(aws ec2 create-security-group \
  --group-name elasticache-redis-sg \
  --description "Security group for ElastiCache Redis cluster" \
  --vpc-id "$VPC_ID" \
  --region "$REGION" \
  --query 'GroupId' \
  --output text)
echo "REDIS_SG_ID=$REDIS_SG_ID"

# Create security group for application server
APP_SG_ID=$(aws ec2 create-security-group \
  --group-name redis-app-sg \
  --description "Security group for Flask application" \
  --vpc-id "$VPC_ID" \
  --region "$REGION" \
  --query 'GroupId' \
  --output text)
echo "APP_SG_ID=$APP_SG_ID"

# Allow SSH access (port 22) to application server
aws ec2 authorize-security-group-ingress \
  --group-id "$APP_SG_ID" \
  --protocol tcp \
  --port 22 \
  --cidr 0.0.0.0/0 \
  --region "$REGION"
echo "SSH access (port 22) allowed"

# Allow HTTP access (port 5000) for Flask application
aws ec2 authorize-security-group-ingress \
  --group-id "$APP_SG_ID" \
  --protocol tcp \
  --port 5000 \
  --cidr 0.0.0.0/0 \
  --region "$REGION"
echo "Flask access (port 5000) allowed"

# Allow Redis access (port 6379) from application security group only
aws ec2 authorize-security-group-ingress \
  --group-id "$REDIS_SG_ID" \
  --protocol tcp \
  --port 6379 \
  --source-group "$APP_SG_ID" \
  --region "$REGION"
echo "Redis access (port 6379) allowed from app servers"
```

---

## Step 3 – Create Cache Subnet Group

```bash
# Create cache subnet group (multi-AZ support for high availability)
aws elasticache create-cache-subnet-group \
  --cache-subnet-group-name lab-cache-subnet-group \
  --cache-subnet-group-description "Subnet group for Redis cluster" \
  --subnet-ids $SUBNET_IDS \
  --region "$REGION"
echo "Cache subnet group created"
```

---

## Step 4 – Create ElastiCache Redis Cluster

```bash
# Create Redis cluster (single node, Redis 7.0)
aws elasticache create-cache-cluster \
  --cache-cluster-id "$CACHE_CLUSTER_ID" \
  --cache-node-type "$CACHE_NODE_TYPE" \
  --engine redis \
  --engine-version 7.0 \
  --num-cache-nodes "$NUM_CACHE_NODES" \
  --cache-subnet-group-name lab-cache-subnet-group \
  --security-group-ids "$REDIS_SG_ID" \
  --region "$REGION"
echo "Redis cluster creation initiated (takes 5-10 minutes)"

# Wait for cluster to become available
aws elasticache wait cache-cluster-available \
  --cache-cluster-id "$CACHE_CLUSTER_ID" \
  --region "$REGION"
echo "Redis cluster is now available"
```

---

## Step 5 – Get Redis Endpoint

```bash
# Get Redis endpoint hostname
REDIS_ENDPOINT=$(aws elasticache describe-cache-clusters \
  --cache-cluster-id "$CACHE_CLUSTER_ID" \
  --show-cache-node-info \
  --query 'CacheClusters[0].CacheNodes[0].Endpoint.Address' \
  --output text \
  --region "$REGION")
echo "REDIS_ENDPOINT=$REDIS_ENDPOINT"

# Get Redis port number
REDIS_PORT=$(aws elasticache describe-cache-clusters \
  --cache-cluster-id "$CACHE_CLUSTER_ID" \
  --show-cache-node-info \
  --query 'CacheClusters[0].CacheNodes[0].Endpoint.Port' \
  --output text \
  --region "$REGION")
echo "REDIS_PORT=$REDIS_PORT"
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
```

---

## Step 7 – Create Flask Application with Redis Session Management

```bash
# Create application directory
mkdir -p redis-app
cd redis-app

# Create Flask application with Redis session support
cat > app.py <<'EOF'
from flask import Flask, session
from flask_session import Session
import redis
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'lab-secret-key'
app.config['SESSION_TYPE'] = 'redis'
app.config['SESSION_PERMANENT'] = False

# Redis connection from environment variables
REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.environ.get('REDIS_PORT', 6379))

app.config['SESSION_REDIS'] = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    decode_responses=True
)

Session(app)

@app.route('/')
def index():
    # Track visits in session (stored in Redis)
    session['visits'] = session.get('visits', 0) + 1
    return f'''
    <h1>Redis Session Demo</h1>
    <p>Visit Count: {session["visits"]}</p>
    <p>Redis: {REDIS_HOST}:{REDIS_PORT}</p>
    <p><a href="/test">Test Redis</a> | <a href="/clear">Clear</a></p>
    '''

@app.route('/test')
def test():
    # Test basic Redis operations
    cache = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    cache.set('test:key', 'Hello Redis!', ex=60)
    value = cache.get('test:key')
    return f'<h1>Redis Test</h1><p>Result: {value}</p><p><a href="/">Back</a></p>'

@app.route('/clear')
def clear():
    session.clear()
    return '<h1>Session Cleared!</h1><p><a href="/">Back</a></p>'

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
EOF

# Create requirements file
cat > requirements.txt <<'EOF'
Flask==3.0.0
Flask-Session==0.5.0
redis==5.0.1
EOF

echo "Flask application created"
cd ..
```

---

## Step 8 – Create User Data Script for EC2

```bash
# Create user data script to auto-install and run Flask app on EC2
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

# Create requirements file
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

# Set ownership to ec2-user
chown -R ec2-user:ec2-user /home/ec2-user/app

# Enable and start Flask service
systemctl daemon-reload
systemctl enable flask-app
systemctl start flask-app
EOF

echo "User data script created"
```

---

## Step 9 – Launch EC2 Instance with Flask Application

```bash
# Launch EC2 instance with Flask application (auto-configured via user data)
INSTANCE_ID=$(aws ec2 run-instances \
  --image-id "$AMI_ID" \
  --instance-type t2.micro \
  --subnet-id "$SUBNET_ID" \
  --security-group-ids "$APP_SG_ID" \
  --user-data file://redis-app-userdata.sh \
  --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=redis-app-server}]" \
  --query 'Instances[0].InstanceId' \
  --output text \
  --region "$REGION")
echo "INSTANCE_ID=$INSTANCE_ID"

# Wait for instance to be running
aws ec2 wait instance-running \
  --instance-ids "$INSTANCE_ID" \
  --region "$REGION"
echo "Instance is running"

# Get public IP address
PUBLIC_IP=$(aws ec2 describe-instances \
  --instance-ids "$INSTANCE_ID" \
  --query 'Reservations[0].Instances[0].PublicIpAddress' \
  --output text \
  --region "$REGION")
echo "PUBLIC_IP=$PUBLIC_IP"

echo ""
echo "Wait 2-3 minutes for Flask app to start, then opening browser..."
sleep 180
"$BROWSER" "http://${PUBLIC_IP}:5000"
```

---

## Step 10 – Test Application

```
Visit the application in your browser:
  http://<PUBLIC_IP>:5000

Test the following:
  1. Refresh the page - visit count increases (session stored in Redis)
  2. Click 'Test Redis' - verify Redis SET/GET and Hash operations
  3. Click 'Clear Session' - reset visit count
  4. Refresh again - visit count starts from 1
```

---

## Step 11 – Cleanup Resources

```bash
# Terminate EC2 instance
aws ec2 terminate-instances \
  --instance-ids "$INSTANCE_ID" \
  --region "$REGION"
echo "EC2 instance termination initiated"

# Wait for instance to terminate
aws ec2 wait instance-terminated \
  --instance-ids "$INSTANCE_ID" \
  --region "$REGION"
echo "EC2 instance terminated"

# Delete ElastiCache Redis cluster
aws elasticache delete-cache-cluster \
  --cache-cluster-id "$CACHE_CLUSTER_ID" \
  --region "$REGION"
echo "Redis cluster deletion initiated (takes a few minutes)"

# Wait for cluster deletion to complete
sleep 120

# Delete cache subnet group
aws elasticache delete-cache-subnet-group \
  --cache-subnet-group-name lab-cache-subnet-group \
  --region "$REGION"
echo "Cache subnet group deleted"

# Delete security groups (wait for dependencies to clear)
sleep 10
aws ec2 delete-security-group \
  --group-id "$APP_SG_ID" \
  --region "$REGION"
echo "App security group deleted"

aws ec2 delete-security-group \
  --group-id "$REDIS_SG_ID" \
  --region "$REGION"
echo "Redis security group deleted"

# Remove local files
rm -rf redis-app redis-app-userdata.sh
echo "Local files removed"
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
