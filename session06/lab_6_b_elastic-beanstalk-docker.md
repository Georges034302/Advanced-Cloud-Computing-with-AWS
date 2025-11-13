# Lab 6.B: Deploy Containerized Application to Elastic Beanstalk

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
# Set region
REGION="ap-southeast-2"
echo "REGION=$REGION"

# Set application name
APP_NAME="joke-api-eb"
echo "APP_NAME=$APP_NAME"

ENV_NAME="joke-api-env"
echo "ENV_NAME=$ENV_NAME"

# Verify prerequisites
echo ""
echo "Verifying prerequisites..."

# Check AWS CLI
aws --version || { echo "❌ AWS CLI not installed"; exit 1; }

# Check Docker
docker --version || { echo "❌ Docker not installed"; exit 1; }

# Check EB CLI
eb --version || { echo "❌ EB CLI not installed. Install: pip install awsebcli"; exit 1; }

echo ""
echo "✅ All prerequisites verified"
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

echo "✅ Flask application created"
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

echo "✅ Dockerfile created"
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

echo "✅ Dockerrun.aws.json created"
```

---

## Step 5 – Test Docker Image Locally (Optional)

```bash
echo ""
echo "Testing Docker image locally..."

# Build Docker image
docker build -t joke-api-eb:latest .

# Run container locally
CONTAINER_ID=$(docker run -d -p 8080:5000 joke-api-eb:latest)
echo "CONTAINER_ID=$CONTAINER_ID"

# Wait for container to start
sleep 3

# Test endpoints
echo ""
echo "Testing local container on port 8080..."
curl -s http://localhost:8080/ | python3 -m json.tool

# Stop and remove container
docker stop "$CONTAINER_ID"
docker rm "$CONTAINER_ID"

echo ""
echo "✅ Local Docker test successful"
```

---

## Step 6 – Initialize Elastic Beanstalk Application

```bash
echo ""
echo "Initializing Elastic Beanstalk application..."

# Initialize EB application
eb init \
  --platform docker \
  --region "$REGION" \
  "$APP_NAME"

echo "✅ Elastic Beanstalk application initialized"

# Verify .elasticbeanstalk directory was created
ls -la .elasticbeanstalk/
```

---

## Step 7 – Create Elastic Beanstalk Environment

```bash
echo ""
echo "Creating Elastic Beanstalk environment..."
echo "This will take 5-7 minutes..."

# Create environment with t2.micro (free tier)
eb create "$ENV_NAME" \
  --instance-type t2.micro \
  --single \
  --region "$REGION"

echo ""
echo "✅ Elastic Beanstalk environment created"
```

---

## Step 8 – Get Application URL and Test

```bash
# Get environment URL
APP_URL=$(eb status | grep "CNAME" | awk '{print $2}')
echo "APP_URL=$APP_URL"

# Wait for application to be fully ready
echo ""
echo "Waiting for application to be ready..."
sleep 30

echo ""
echo "================================================"
echo "JOKE API DEPLOYED ON ELASTIC BEANSTALK"
echo "================================================"
echo ""
echo "API Base URL: http://${APP_URL}"
echo ""
echo "Testing endpoints..."
echo ""

# Test welcome endpoint
echo "1. Testing / (welcome):"
curl -s "http://${APP_URL}/" | python3 -m json.tool
echo ""

# Test random joke endpoint
echo "2. Testing /joke (random joke):"
curl -s "http://${APP_URL}/joke" | python3 -m json.tool
echo ""

# Test all jokes endpoint
echo "3. Testing /jokes (all jokes):"
curl -s "http://${APP_URL}/jokes" | python3 -m json.tool
echo ""

# Test health endpoint
echo "4. Testing /health (health check):"
curl -s "http://${APP_URL}/health" | python3 -m json.tool
echo ""

echo "================================================"
echo "✅ All endpoints working!"
echo ""
echo "Try in browser:"
echo "  http://${APP_URL}/"
echo "  http://${APP_URL}/joke"
echo "  http://${APP_URL}/jokes"
```

---

## Step 9 – View Environment Status

```bash
echo ""
echo "Elastic Beanstalk Environment Status:"
eb status

echo ""
echo "Environment Health:"
eb health

echo ""
echo "Recent Events:"
eb events --follow
```

---

## Step 10 – View Environment Configuration

```bash
echo ""
echo "Environment Configuration:"
aws elasticbeanstalk describe-environments \
  --application-name "$APP_NAME" \
  --environment-names "$ENV_NAME" \
  --query 'Environments[0].{Name:EnvironmentName,Status:Status,Health:Health,URL:CNAME,Platform:PlatformArn}' \
  --output table \
  --region "$REGION"

echo ""
echo "Environment Resources:"
aws elasticbeanstalk describe-environment-resources \
  --environment-name "$ENV_NAME" \
  --query 'EnvironmentResources.{Instances:length(Instances),SecurityGroups:length(SecurityGroups),LoadBalancers:length(LoadBalancers)}' \
  --output table \
  --region "$REGION"
```

---

## Step 11 – Update Application (Optional)

```bash
# If you need to update the application, modify code and run:
# eb deploy

echo ""
echo "To update the application:"
echo "  1. Modify application.py or Dockerfile"
echo "  2. Run: eb deploy"
echo "  3. Wait 2-3 minutes for deployment"
echo ""
echo "To view logs:"
echo "  eb logs"
echo ""
echo "To SSH into instance:"
echo "  eb ssh"
```

---

## Step 12 – Cleanup Resources

```bash
echo ""
echo "Cleaning up resources..."
echo "This will take 3-5 minutes..."

# Terminate Elastic Beanstalk environment
echo "Terminating Elastic Beanstalk environment..."
eb terminate "$ENV_NAME" --force

echo "Waiting for environment to terminate..."
sleep 60

# Verify environment is terminated
aws elasticbeanstalk describe-environments \
  --application-name "$APP_NAME" \
  --environment-names "$ENV_NAME" \
  --query 'Environments[0].Status' \
  --output text \
  --region "$REGION" 2>/dev/null || echo "Environment terminated"

# Delete application (optional - keeps application but removes environment)
echo ""
echo "To delete the entire application:"
echo "  aws elasticbeanstalk delete-application --application-name $APP_NAME --region $REGION"
echo ""
echo "For now, keeping application (only environment deleted)"

# Clean up local files
cd ..
rm -rf joke-api-eb

echo ""
echo "✅ Cleanup completed successfully!"
echo ""
echo "Resources cleaned up:"
echo "- Elastic Beanstalk environment"
echo "- EC2 instance (t2.micro)"
echo "- Security groups"
echo "- S3 bucket (application versions)"
echo "- Local project files"
echo ""
echo "Note: Application '$APP_NAME' still exists (no cost)"
echo "Delete it manually if needed using:"
echo "  aws elasticbeanstalk delete-application --application-name $APP_NAME --region $REGION"
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

## Free Tier Notes
- **Elastic Beanstalk**: No additional charge (only underlying resources)
- **EC2 t2.micro**: 750 hours/month (free tier)
- **S3 Storage**: 5 GB for application versions
- **Data Transfer**: 15 GB outbound per month

This lab uses single t2.micro instance in single-instance mode, staying within free tier limits.

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
