# Lab 10.A: GitHub → App Runner - Direct Code Deployment

<img width="1200" height="634" alt="IMG" src="https://github.com/user-attachments/assets/9f2d9df8-99e8-45b2-a1a3-00d75ae6cd9d" />

## Overview
This lab demonstrates direct deployment from GitHub to AWS App Runner using code-based deployment. You'll connect a GitHub repository to App Runner, which automatically builds and deploys your Flask application without requiring separate build services. This showcases AWS App Runner's fully managed platform with built-in CI/CD capabilities.

---

## Objectives
- Connect GitHub repository directly to AWS App Runner
- Create Flask REST API with multiple endpoints
- Configure App Runner for Python code-based deployment
- Deploy with gunicorn production WSGI server
- Test automated deployments from GitHub
- Understand App Runner's built-in build system

---

## Prerequisites
- AWS CLI configured (`aws configure`)
- Git installed (`git --version`)
- GitHub account with existing repository 
- IAM permissions for App Runner, CodeStar Connections
- Region: ap-southeast-2

---

## Step 1 – Set Variables

```bash
# Set AWS region
REGION="ap-southeast-2"
export AWS_REGION="$REGION"

# Dynamically get GitHub repository info from git remote
GITHUB_URL=$(git remote get-url origin)
GITHUB_OWNER=$(echo "$GITHUB_URL" | sed -E 's|.*github\.com[:/]([^/]+)/.*|\1|')
GITHUB_REPO=$(echo "$GITHUB_URL" | sed -E 's|.*github\.com[:/][^/]+/([^.]+)(\.git)?$|\1|')

# Application configuration
APP_FOLDER="flask-apprunner-app"
SERVICE_NAME="flask-joke-service"

# Get AWS account ID
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

echo "REGION=$REGION"
echo "GITHUB_OWNER=$GITHUB_OWNER"
echo "GITHUB_REPO=$GITHUB_REPO"
echo "ACCOUNT_ID=$ACCOUNT_ID"
```

---

## Step 2 – Verify GitHub Repository

```bash
# Navigate to repository root and sync with remote
REPO_DIR=$(git rev-parse --show-toplevel)
cd "$REPO_DIR"
git checkout main
git pull origin main
```

---

## Step 3 – Create Application Directory

```bash
# Create and navigate to application directory
WORKSPACE="$REPO_DIR/$APP_FOLDER"
mkdir -p "$WORKSPACE"
cd "$WORKSPACE"
```

---

## Step 4 – Create Flask Application

```bash
# Create Flask API with joke endpoints
cat > app.py <<'EOF'
from flask import Flask, jsonify
import random

app = Flask(__name__)

jokes = [
    "Why do programmers prefer dark mode? Because light attracts bugs!",
    "Why do Java developers wear glasses? Because they don't C#.",
    "How many programmers does it take to change a light bulb? None, that's a hardware problem.",
    "Why did the developer go broke? Because he used up all his cache.",
    "What's a programmer's favorite hangout place? The Foo Bar."
]

@app.route('/')
def home():
    return jsonify({
        "message": "Flask Joke API on App Runner",
        "endpoints": {
            "/": "API info",
            "/joke": "Get random joke",
            "/health": "Health check"
        }
    })

@app.route('/joke')
def get_joke():
    return jsonify({"joke": random.choice(jokes)})

@app.route('/health')
def health():
    return jsonify({"status": "healthy"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
EOF
```

---

## Step 5 – Create Requirements File

```bash
# Define Python dependencies (compatible versions for App Runner)
cat > requirements.txt <<'EOF'
Flask==2.3.0
Werkzeug==2.3.0
gunicorn==21.2.0
EOF
```

---

## Step 6 – Commit and Push to GitHub

```bash
# Commit Flask application files to GitHub
git add "$APP_FOLDER/"
git commit -m "Add Flask joke API for App Runner"
git push origin main
```

---

## Step 7 – Create GitHub Connection for App Runner

```bash
# List existing CodeStar connections (GitHub connections)
CONNECTION_ARN=$(aws codestar-connections list-connections \
  --provider-type-filter GitHub \
  --region "$REGION" \
  --query 'Connections[0].ConnectionArn' \
  --output text)

echo "CONNECTION_ARN=$CONNECTION_ARN"
```

**If no connection exists:**
1. Go to AWS Console → Developer Tools → Connections
2. Click **Create connection**
3. Select **GitHub** and name it `github-connection`
4. Click **Connect to GitHub** and authorize AWS
5. Run the command above again to get the ARN

---

## Step 8 – Create App Runner Service

```bash
# Create App Runner service configuration with code-based deployment
cat > apprunner-service.json <<EOF
{
  "ServiceName": "${SERVICE_NAME}",
  "SourceConfiguration": {
    "CodeRepository": {
      "RepositoryUrl": "https://github.com/${GITHUB_OWNER}/${GITHUB_REPO}",
      "SourceCodeVersion": {
        "Type": "BRANCH",
        "Value": "main"
      },
      "SourceDirectory": "${APP_FOLDER}",
      "CodeConfiguration": {
        "ConfigurationSource": "API",
        "CodeConfigurationValues": {
          "Runtime": "PYTHON_3",
          "StartCommand": "gunicorn --bind :8000 app:app",
          "Port": "8000"
        }
      }
    },
    "AutoDeploymentsEnabled": false,
    "AuthenticationConfiguration": {
      "ConnectionArn": "${CONNECTION_ARN}"
    }
  },
  "InstanceConfiguration": {
    "Cpu": "1 vCPU",
    "Memory": "2 GB"
  }
}
EOF

# Create the App Runner service
SERVICE_ARN=$(aws apprunner create-service \
  --cli-input-json file://apprunner-service.json \
  --region "$REGION" \
  --query 'Service.ServiceArn' \
  --output text)

echo "SERVICE_ARN=$SERVICE_ARN"
```

**Note:** If you encounter CLI errors, you can create the service via AWS Console:
1. Go to AWS Console → App Runner → Create service
2. Source: Repository → Connect to GitHub
3. Select your repository and branch
4. Deployment: Code repository
5. Configure build settings:
   - Runtime: Python 3
   - Build command: (leave empty)
   - Start command: `gunicorn --bind :8000 app:app`
   - Port: 8000
6. Create and deploy

---

## Step 9 – Wait for Service to be Ready

```bash
# Wait for service deployment (1-2 minutes)
while true; do
  STATUS=$(aws apprunner describe-service --service-arn "$SERVICE_ARN" --region "$REGION" --query 'Service.Status' --output text)
  echo "Status: $STATUS"
  [ "$STATUS" = "RUNNING" ] && break
  [ "$STATUS" = "CREATE_FAILED" ] && echo "❌ Deployment failed" && break
  sleep 10
done

# Get service URL
SERVICE_URL=$(aws apprunner describe-service \
  --service-arn "$SERVICE_ARN" \
  --region "$REGION" \
  --query 'Service.ServiceUrl' \
  --output text)

echo "SERVICE_URL=$SERVICE_URL"
```

---

## Step 10 – Test Application

```bash
# Test all API endpoints
echo "Testing home endpoint:"
curl -s "https://$SERVICE_URL/" | jq .

echo -e "\nTesting joke endpoint:"
curl -s "https://$SERVICE_URL/joke" | jq .

echo -e "\nTesting health endpoint:"
curl -s "https://$SERVICE_URL/health" | jq .
```

---

## Step 11 – View Service Details

```bash
# Display service information
aws apprunner describe-service \
  --service-arn "$SERVICE_ARN" \
  --region "$REGION" \
  --query 'Service.{Name:ServiceName,Status:Status,URL:ServiceUrl,Created:CreatedAt}' \
  --output table
```

---

## Step 12 – Monitor Service Logs

**View logs in AWS Console:**
1. Go to AWS Console → App Runner
2. Select your service: `flask-joke-service`
3. Click **Logs** tab
4. View deployment and application logs in CloudWatch

```bash
# Get CloudWatch log group name
LOG_GROUP="/aws/apprunner/${SERVICE_NAME}/service"

echo "View logs in CloudWatch:"
echo "Log Group: $LOG_GROUP"
```

---

## Step 13 – Make Code Changes

```bash
# Navigate back to application directory
cd "$WORKSPACE"

# Add a new joke to the application
cat > app.py <<'EOF'
from flask import Flask, jsonify
import random

app = Flask(__name__)

jokes = [
    "Why do programmers prefer dark mode? Because light attracts bugs!",
    "Why do Java developers wear glasses? Because they don't C#.",
    "How many programmers does it take to change a light bulb? None, that's a hardware problem.",
    "Why did the developer go broke? Because he used up all his cache.",
    "What's a programmer's favorite hangout place? The Foo Bar.",
    "Why do Python programmers prefer snake case? Because camelCase is for the one-humped!"
]

@app.route('/')
def home():
    return jsonify({
        "message": "Flask Joke API on App Runner",
        "endpoints": {
            "/": "API info",
            "/joke": "Get random joke",
            "/health": "Health check"
        }
    })

@app.route('/joke')
def get_joke():
    return jsonify({"joke": random.choice(jokes)})

@app.route('/health')
def health():
    return jsonify({"status": "healthy"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
EOF

# Commit and push changes
git add app.py
git commit -m "Add new Python joke"
git push origin main

echo "✅ Code changes pushed to GitHub"
echo "Manually trigger deployment: App Runner Console → Actions → Deploy"
```

---

## Step 14 – Cleanup

```bash
# Delete App Runner service
aws apprunner delete-service --service-arn "$SERVICE_ARN" --region "$REGION"

# Wait for service deletion to complete
while true; do
  STATUS=$(aws apprunner describe-service --service-arn "$SERVICE_ARN" --region "$REGION" --query 'Service.Status' --output text 2>/dev/null) || break
  echo "Status: $STATUS"
  [ "$STATUS" = "DELETED" ] && break
  sleep 10
done

# Optional: Delete GitHub connection (keep if using for other services)
# aws codestar-connections delete-connection --connection-arn "$CONNECTION_ARN" --region "$REGION"

# Remove application directory from workspace
cd "$REPO_DIR"
rm -rf "$APP_FOLDER"

# Remove from git repository
git rm -r "$APP_FOLDER"
git commit -m "Cleanup: Remove Flask App Runner app"
git push origin main

echo "✅ Cleanup complete"
```

---

## Summary

In this lab, you:
- Connected GitHub repository directly to AWS App Runner
- Created Flask application with REST API endpoints
- Deployed using App Runner's built-in code-based deployment
- Configured gunicorn production WSGI server
- Tested deployed application endpoints
- Made code changes and learned how to redeploy
- Cleaned up all AWS resources

**Key Takeaways:**
- **Direct GitHub Integration**: App Runner connects directly to GitHub
- **Built-in Build System**: No separate CI/CD service required
- **Code-Based Deployment**: App Runner builds from source code automatically
- **No BuildSpec Required**: Python runtime auto-installs requirements.txt
- **Production Ready**: Uses gunicorn WSGI server for production workloads

**Deployment Workflow:**
```
GitHub Push → App Runner (auto-build + deploy) → HTTPS Endpoint
```

**What App Runner Does Automatically:**
1. Pulls code from GitHub on deployment trigger
2. Installs dependencies from requirements.txt
3. Runs StartCommand (gunicorn)
4. Provisions compute resources
5. Configures load balancing and HTTPS
6. Monitors health and auto-scales

---

## Best Practices

**App Runner Configuration:**
- Use specific Python package versions for reproducibility
- Enable auto-deployments for CI/CD workflows
- Use gunicorn (not Flask dev server) for production
- Configure health checks for reliability
- Monitor metrics in CloudWatch

**Application Development:**
- Keep dependencies minimal in requirements.txt
- Use environment variables for configuration
- Implement /health endpoint for health checks
- Log to stdout/stderr (captured by CloudWatch)

**Security:**
- Use CodeStar Connections (OAuth) instead of personal access tokens
- Keep GitHub connection for reuse across services
- Enable HTTPS only (App Runner default)
- Configure VPC connector if accessing private resources

**Cost Optimization:**
- Start with 1 vCPU / 2 GB memory configuration
- Monitor usage and adjust based on metrics
- Delete services when not in use
- App Runner charges only for compute time used

---

## Troubleshooting

**Connection ARN not found:**
- Create connection in AWS Console → Developer Tools → Connections
- Authorize GitHub OAuth access
- Connection must be in "AVAILABLE" status

**Service deployment fails:**
- Check SourceDirectory path (no leading slash: `flask-apprunner-app`)
- Verify Runtime is `PYTHON_3` (not `PYTHON_3.11`)
- Ensure StartCommand is correct: `gunicorn --bind :8000 app:app`
- Leave BuildCommand empty for Python runtime

**Application returns errors:**
- Check CloudWatch logs for Python errors
- Verify app.py listens on port 8000
- Ensure requirements.txt has all dependencies
- Use Flask==2.3.0 (not 3.x for App Runner compatibility)

**GitHub changes not deploying:**
- Auto-deployments disabled by default in this lab
- Manually trigger: Console → Service → Actions → Deploy
- Or enable AutoDeploymentsEnabled: true in service config

---

## Additional Resources

- [AWS App Runner Documentation](https://docs.aws.amazon.com/apprunner/)
- [App Runner Pricing](https://aws.amazon.com/apprunner/pricing/)
- [CodeStar Connections](https://docs.aws.amazon.com/dtconsole/latest/userguide/connections.html)
- [Gunicorn Configuration](https://docs.gunicorn.org/en/stable/configure.html)
- [Flask on App Runner Best Practices](https://docs.aws.amazon.com/apprunner/latest/dg/service-source-code-python.html)
