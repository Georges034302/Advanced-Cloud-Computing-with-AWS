# Lab 6.B: Deploy Containerized Application to Elastic Beanstalk
<img width="1536" height="1024" alt="IMG" src="https://github.com/user-attachments/assets/d314b7e4-827f-4d3a-9377-d7f9b42f7175" />

## Overview
This lab demonstrates how to deploy a containerized Python Flask API to AWS Elastic Beanstalk using Docker. Elastic Beanstalk automatically handles deployment, capacity provisioning, load balancing, and health monitoring, making it ideal for simple container deployments without managing infrastructure.

---

## Objectives
- Create simple Python Flask joke API
- Create Dockerfile for containerization
- Initialize Elastic Beanstalk application
- Deploy container to Elastic Beanstalk
- Test the deployed API endpoints
- Monitor application health
- Clean up all resources

---

## Prerequisites
- AWS CLI configured (`aws configure`)
- Docker installed locally (for testing)
- Elastic Beanstalk CLI (`pip install awsebcli`)
- IAM permissions for Elastic Beanstalk, EC2, and S3
- Basic understanding of Docker and Flask

---

## Step 1 – Set Variables and Verify Prerequisites

```bash
# Set region and application names
REGION="ap-southeast-2"
APP_NAME="joke-api-eb"
ENV_NAME="joke-api-env"

# Verify prerequisites
aws --version || { echo "❌ AWS CLI not installed"; exit 1; }
docker --version || { echo "❌ Docker not installed"; exit 1; }
eb --version || { echo "❌ EB CLI not installed. Install: pip install awsebcli"; exit 1; }
```

---

## Step 2 – Create Flask Application

```bash
# Create project directory
mkdir -p joke-api-eb
cd joke-api-eb

# Create Flask application
cat > application.py <<'EOF'
from flask import Flask, jsonify
import random

# Use 'application' for Elastic Beanstalk
application = Flask(__name__)

# Joke database
JOKES = [
    "Why do programmers prefer dark mode? Because light attracts bugs!",
    "Why do Java developers wear glasses? Because they don't C#!",
    "How many programmers does it take to change a light bulb? None, that's a hardware problem!",
    "Why did the developer go broke? Because he used up all his cache!",
    "What's a programmer's favorite hangout place? Foo Bar!",
    "Why do programmers hate nature? It has too many bugs!",
    "What do you call a programmer from Finland? Nerdic!",
    "Why did the programmer quit his job? Because he didn't get arrays!",
    "What's the object-oriented way to become wealthy? Inheritance!",
    "Why do programmers always mix up Halloween and Christmas? Because Oct 31 == Dec 25!"
]

@application.route('/')
def welcome():
    return jsonify({
        "message": "Welcome to the Elastic Beanstalk Joke API!",
        "platform": "AWS Elastic Beanstalk with Docker",
        "endpoints": {
            "/": "This welcome message",
            "/joke": "Get a random joke",
            "/jokes": "Get all jokes",
            "/health": "Health check endpoint"
        }
    })

@application.route('/joke')
def get_joke():
    return jsonify({
        "joke": random.choice(JOKES)
    })

@application.route('/jokes')
def get_all_jokes():
    return jsonify({
        "count": len(JOKES),
        "jokes": JOKES
    })

@application.route('/health')
def health():
    return jsonify({
        "status": "healthy",
        "service": "joke-api"
    })

if __name__ == '__main__':
    application.run(host='0.0.0.0', port=5000)
EOF

# Create requirements file
cat > requirements.txt <<'EOF'
flask==3.0.0
werkzeug==3.0.1
gunicorn==21.2.0
EOF
```

---

## Step 3 – Create Dockerfile

```bash
# Create Dockerfile
cat > Dockerfile <<'EOF'
# Use official Python runtime as base image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY application.py .

# Expose port 5000
EXPOSE 5000

# Run with gunicorn for production
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "application:application"]
EOF
```

---

## Step 4 – Create Dockerrun.aws.json

```bash
# Create Dockerrun.aws.json for Elastic Beanstalk
cat > Dockerrun.aws.json <<'EOF'
{
  "AWSEBDockerrunVersion": "1",
  "Image": {
    "Name": "joke-api-eb",
    "Update": "true"
  },
  "Ports": [
    {
      "ContainerPort": 5000,
      "HostPort": 80
    }
  ]
}
EOF
```

---

## Step 5 – Test Docker Image Locally (Optional)

```bash
# Build and test Docker image locally
docker build -t joke-api-eb:latest .

# Run container on port 8080
CONTAINER_ID=$(docker run -d -p 8080:5000 joke-api-eb:latest)
echo "CONTAINER_ID=$CONTAINER_ID"

sleep 3

# Test local endpoint
curl -s http://localhost:8080/ | python3 -m json.tool

# Open in browser
"$BROWSER" "http://localhost:8080/"

# Stop and remove container
docker stop "$CONTAINER_ID"
docker rm "$CONTAINER_ID"
```

---

## Step 6 – Initialize Elastic Beanstalk Application

```bash
# Initialize EB application with Docker platform
eb init --platform docker --region "$REGION" "$APP_NAME"

# Verify configuration directory created
ls -la .elasticbeanstalk/
```

---

## Step 7 – Create Elastic Beanstalk Environment

```bash
# Create single-instance environment with t2.micro (takes 5-7 minutes)
eb create "$ENV_NAME" \
  --instance-type t2.micro \
  --single \
  --region "$REGION"
```

---

## Step 8 – Get Application URL and Test

```bash
# Get environment URL
APP_URL=$(eb status | grep "CNAME" | awk '{print $2}')
echo "APP_URL=$APP_URL"

# Wait for application to be ready
sleep 30

echo ""
echo "API Base URL: http://${APP_URL}"
echo ""

# Test welcome endpoint
echo "Testing / (welcome):"
curl -s "http://${APP_URL}/" | python3 -m json.tool
echo ""

# Test random joke endpoint
echo "Testing /joke (random joke):"
curl -s "http://${APP_URL}/joke" | python3 -m json.tool
echo ""

# Test all jokes endpoint
echo "Testing /jokes (all jokes):"
curl -s "http://${APP_URL}/jokes" | python3 -m json.tool
echo ""

# Test health endpoint
echo "Testing /health (health check):"
curl -s "http://${APP_URL}/health" | python3 -m json.tool
echo ""

# Open in browser
"$BROWSER" "http://${APP_URL}/"
"$BROWSER" "http://${APP_URL}/joke"
"$BROWSER" "http://${APP_URL}/jokes"
```

---

## Step 9 – View Environment Status

```bash
# View environment status
eb status

# View environment health
eb health

# View recent events (press Ctrl+C to exit)
eb events --follow
```

---

## Step 10 – View Environment Configuration

```bash
# View environment configuration
aws elasticbeanstalk describe-environments \
  --application-name "$APP_NAME" \
  --environment-names "$ENV_NAME" \
  --query 'Environments[0].{Name:EnvironmentName,Status:Status,Health:Health,URL:CNAME,Platform:PlatformArn}' \
  --output table \
  --region "$REGION"

# View environment resources
aws elasticbeanstalk describe-environment-resources \
  --environment-name "$ENV_NAME" \
  --query 'EnvironmentResources.{Instances:length(Instances),SecurityGroups:length(SecurityGroups),LoadBalancers:length(LoadBalancers)}' \
  --output table \
  --region "$REGION"
```

---

## Step 11 – Cleanup Resources

```bash
# Terminate Elastic Beanstalk environment (takes 3-5 minutes)
eb terminate "$ENV_NAME" --force

sleep 60

# Verify environment is terminated
aws elasticbeanstalk describe-environments \
  --application-name "$APP_NAME" \
  --environment-names "$ENV_NAME" \
  --query 'Environments[0].Status' \
  --output text \
  --region "$REGION" 2>/dev/null || echo "Environment terminated"

# Clean up S3 bucket contents before deleting application
aws s3 rm s3://elasticbeanstalk-${REGION}-${ACCOUNT_ID} --recursive

# Delete the s3 bucket
aws s3 rb s3://elasticbeanstalk-${REGION}-${ACCOUNT_ID}

# Delete application
aws elasticbeanstalk delete-application --application-name "$APP_NAME" --region "$REGION"

# Clean up local files
cd ..
rm -rf joke-api-eb
```

---

## Summary

In this lab, you have:
- Created Python Flask joke API with multiple endpoints
- Created Dockerfile for containerization
- Configured Dockerrun.aws.json for Elastic Beanstalk
- Tested Docker image locally
- Initialized Elastic Beanstalk application
- Deployed containerized application to Elastic Beanstalk
- Tested all API endpoints on deployed environment
- Monitored environment health and status
- Cleaned up all resources

**Key Takeaways:**
- **Elastic Beanstalk**: Fully managed platform for deploying applications
- **Docker Platform**: Run any containerized application
- **Single Instance**: Free tier compatible with t2.micro
- **Auto-managed**: Handles deployment, scaling, monitoring automatically
- **Zero Infrastructure**: No need to manage EC2, security groups, load balancers manually

**Elastic Beanstalk Benefits:**
| Feature | Benefit |
|---------|---------|
| **Managed Platform** | No infrastructure management |
| **Auto Scaling** | Built-in (disabled for single instance) |
| **Health Monitoring** | Automatic health checks |
| **Rolling Updates** | Zero-downtime deployments |
| **Easy Rollback** | Quick version rollback |

**Best Practices:**
- Use `application` as Flask app name (EB convention)
- Include gunicorn for production deployments
- Use environment variables for configuration
- Enable enhanced health reporting
- Configure auto scaling for production
- Use managed platform updates
- Monitor logs with `eb logs`
- Tag resources for cost tracking

**EB CLI Commands:**
```bash
eb init          # Initialize application
eb create        # Create environment
eb deploy        # Deploy new version
eb status        # Check environment status
eb health        # Check health
eb logs          # View logs
eb ssh           # SSH into instance
eb terminate     # Terminate environment
```

---

## Production Enhancements

For production deployments:

1. **Load Balanced Environment**
   ```bash
   eb create prod-env --instance-type t2.small --scale 2
   ```

2. **Auto Scaling Configuration**
   ```bash
   eb scale 2  # Set desired capacity
   ```

3. **Environment Variables**
   ```bash
   eb setenv API_KEY=secret DATABASE_URL=postgres://...
   ```

4. **Custom Domain**
   ```bash
   # Use Route 53 to point custom domain to EB CNAME
   ```

5. **HTTPS with ACM**
   - Request certificate in ACM
   - Configure in EB load balancer settings

6. **Enhanced Health Reporting**
   - Enable in EB console
   - Configure custom health check URL

7. **Multi-Container Docker**
   - Use Dockerrun.aws.json v2
   - Define multiple containers with links
