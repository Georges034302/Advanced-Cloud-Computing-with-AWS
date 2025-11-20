# Lab 10.E: CodePipeline → EKS with Helm - Kubernetes CI/CD
<img width="1525" height="623" alt="IMG" src="https://github.com/user-attachments/assets/1adbfc14-1520-4eb9-8973-e143898b1b14" />

## Overview
This lab demonstrates building a complete CI/CD pipeline for Kubernetes deployments using AWS CodePipeline, CodeBuild, and Helm charts. You'll create a Flask API, package it with Helm, and deploy to Amazon EKS with automated rolling updates. This showcases production-grade Kubernetes CI/CD workflows.

---

## Objectives
- Create Helm chart for Flask application
- Configure CodePipeline for EKS deployments
- Build Docker images and push to ECR
- Deploy to EKS using Helm with CodeBuild
- Implement rolling updates with Kubernetes
- Understand Helm templating and values

---

## Prerequisites
- AWS CLI configured (`aws configure`)
- kubectl installed (`kubectl version`)
- Helm 3 installed (`helm version`)
- Git installed (`git --version`)
- Existing EKS cluster (from Session 6 Lab 6.D)
- GitHub account with repository access
- IAM permissions for CodePipeline, CodeBuild, ECR, EKS, S3, IAM
- Region: ap-southeast-2

---

## Architecture

```
GitHub → CodePipeline → CodeBuild:
                          → Build Docker image
                          → Push to ECR
                          → Deploy with Helm to EKS
                          ↓
                        ECR + EKS Cluster
```

**Pipeline Flow:**
1. GitHub hosts application code and Helm chart
2. CodePipeline detects changes and triggers CodeBuild
3. CodeBuild builds Docker image and pushes to ECR
4. CodeBuild deploys to EKS using helm upgrade --install
5. Kubernetes performs rolling update

---

## Step 1 – Set Variables

```bash
# Set AWS region
REGION="ap-southeast-2"
export AWS_REGION="$REGION"

# Dynamically get GitHub repository info
GITHUB_URL=$(git remote get-url origin)
GITHUB_OWNER=$(echo "$GITHUB_URL" | sed -E 's|.*github\.com[:/]([^/]+)/.*|\1|')
GITHUB_REPO=$(echo "$GITHUB_URL" | sed -E 's|.*github\.com[:/][^/]+/([^.]+)(\.git)?$|\1|')

# Application configuration
APP_FOLDER="flask-k8s-app"
APP_NAME="joke-api"
CHART_NAME="joke-api-chart"
ECR_REPO_NAME="joke-api-k8s"
CLUSTER_NAME="my-eks-cluster"
NAMESPACE="default"

# Pipeline configuration
PIPELINE_NAME="eks-helm-pipeline"
CODEBUILD_PROJECT="eks-helm-deploy"
ARTIFACT_BUCKET="codepipeline-artifacts-eks-$(aws sts get-caller-identity --query Account --output text)"

# Get AWS account ID
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

echo "REGION=$REGION"
echo "GITHUB_OWNER=$GITHUB_OWNER"
echo "GITHUB_REPO=$GITHUB_REPO"
echo "ACCOUNT_ID=$ACCOUNT_ID"
echo "CLUSTER_NAME=$CLUSTER_NAME"
```

---

## Step 2 – Verify GitHub Repository and EKS Cluster

```bash
# Navigate to repository root
REPO_DIR=$(git rev-parse --show-toplevel)
cd "$REPO_DIR"

# Sync with remote
git checkout main
git pull origin main

# Verify EKS cluster exists
aws eks describe-cluster \
  --name "$CLUSTER_NAME" \
  --region "$REGION" \
  --query 'cluster.status' \
  --output text

# Update kubeconfig
aws eks update-kubeconfig \
  --name "$CLUSTER_NAME" \
  --region "$REGION"

# Verify kubectl access
kubectl get nodes
```

---

## Step 3 – Create Application Directory

```bash
# Create and navigate to application directory
mkdir -p "$APP_FOLDER"
cd "$APP_FOLDER"
```

---

## Step 4 – Create Flask Application

```bash
# Create Flask joke API
cat > app.py <<'EOF'
from flask import Flask, jsonify
import random
import os

app = Flask(__name__)

jokes = [
    "Why do programmers prefer dark mode? Because light attracts bugs!",
    "Why do Java developers wear glasses? Because they don't C#.",
    "How many programmers does it take to change a light bulb? None, that's a hardware problem.",
    "Why did the developer go broke? Because he used up all his cache.",
    "What's a programmer's favorite hangout place? The Foo Bar.",
]

@app.route('/')
def home():
    return jsonify({
        "service": "joke-api",
        "version": os.getenv("APP_VERSION", "1.0.0"),
        "environment": os.getenv("ENVIRONMENT", "production"),
        "status": "running"
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

## Step 5 – Create Requirements and Dockerfile

```bash
# Python dependencies
cat > requirements.txt <<'EOF'
Flask==2.3.0
gunicorn==21.2.0
EOF

# Dockerfile for containerization
cat > Dockerfile <<'EOF'
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY app.py .

# Run with gunicorn
EXPOSE 8000
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "app:app"]
EOF
```

---

## Step 6 – Create Helm Chart Structure

```bash
# Create Helm chart directory structure
mkdir -p "helm/${CHART_NAME}/templates"

# Create Chart.yaml
cat > "helm/${CHART_NAME}/Chart.yaml" <<EOF
apiVersion: v2
name: ${CHART_NAME}
description: A Helm chart for Flask Joke API on Kubernetes
type: application
version: 1.0.0
appVersion: "1.0.0"
EOF

# Create values.yaml
cat > "helm/${CHART_NAME}/values.yaml" <<EOF
replicaCount: 2

image:
  repository: ${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${ECR_REPO_NAME}
  tag: latest
  pullPolicy: Always

service:
  type: LoadBalancer
  port: 80
  targetPort: 8000

resources:
  limits:
    cpu: 200m
    memory: 256Mi
  requests:
    cpu: 100m
    memory: 128Mi

env:
  - name: ENVIRONMENT
    value: "production"
  - name: APP_VERSION
    value: "1.0.0"
EOF

# Create deployment template
cat > "helm/${CHART_NAME}/templates/deployment.yaml" <<'EOF'
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ .Chart.Name }}
  labels:
    app: {{ .Chart.Name }}
spec:
  replicas: {{ .Values.replicaCount }}
  selector:
    matchLabels:
      app: {{ .Chart.Name }}
  template:
    metadata:
      labels:
        app: {{ .Chart.Name }}
    spec:
      containers:
      - name: {{ .Chart.Name }}
        image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}"
        imagePullPolicy: {{ .Values.image.pullPolicy }}
        ports:
        - containerPort: {{ .Values.service.targetPort }}
        env:
        {{- range .Values.env }}
        - name: {{ .name }}
          value: {{ .value | quote }}
        {{- end }}
        resources:
          {{- toYaml .Values.resources | nindent 10 }}
        livenessProbe:
          httpGet:
            path: /health
            port: {{ .Values.service.targetPort }}
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: {{ .Values.service.targetPort }}
          initialDelaySeconds: 5
          periodSeconds: 5
EOF

# Create service template
cat > "helm/${CHART_NAME}/templates/service.yaml" <<'EOF'
apiVersion: v1
kind: Service
metadata:
  name: {{ .Chart.Name }}
  labels:
    app: {{ .Chart.Name }}
spec:
  type: {{ .Values.service.type }}
  ports:
  - port: {{ .Values.service.port }}
    targetPort: {{ .Values.service.targetPort }}
    protocol: TCP
  selector:
    app: {{ .Chart.Name }}
EOF
```

---

## Step 7 – Create BuildSpec for CodeBuild

```bash
# Navigate back to app folder root
cd "$REPO_DIR/$APP_FOLDER"

# Create buildspec for CodeBuild
cat > buildspec.yml <<EOF
version: 0.2

phases:
  install:
    commands:
      # Install kubectl
      - curl -LO "https://dl.k8s.io/release/\$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
      - chmod +x kubectl
      - mv kubectl /usr/local/bin/
      
      # Install Helm
      - curl -fsSL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
      
      # Update kubeconfig
      - aws eks update-kubeconfig --name ${CLUSTER_NAME} --region ${REGION}

  pre_build:
    commands:
      # Login to ECR
      - aws ecr get-login-password --region ${REGION} | docker login --username AWS --password-stdin ${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com
      
      # Set image tag (using commit SHA)
      - IMAGE_TAG=\${CODEBUILD_RESOLVED_SOURCE_VERSION:0:7}
      - IMAGE_URI=${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${ECR_REPO_NAME}:\${IMAGE_TAG}
      - IMAGE_URI_LATEST=${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${ECR_REPO_NAME}:latest

  build:
    commands:
      # Build Docker image
      - docker build -t \${IMAGE_URI} -t \${IMAGE_URI_LATEST} .
      
      # Push to ECR
      - docker push \${IMAGE_URI}
      - docker push \${IMAGE_URI_LATEST}

  post_build:
    commands:
      # Deploy to EKS with Helm
      - |
        helm upgrade --install ${APP_NAME} ./helm/${CHART_NAME} \
          --set image.tag=\${IMAGE_TAG} \
          --namespace ${NAMESPACE} \
          --wait \
          --timeout 5m
      
      # Verify deployment
      - kubectl get pods -n ${NAMESPACE} -l app=${CHART_NAME}
      - kubectl get svc -n ${NAMESPACE} ${CHART_NAME}
EOF
```

---

## Step 8 – Commit and Push to GitHub

```bash
# Add all files
cd "$REPO_DIR"
git add "$APP_FOLDER/"

# Commit changes
git commit -m "Add Flask Kubernetes app with Helm chart"

# Push to GitHub
git push origin main
```

---

## Step 9 – Create ECR Repository

```bash
# Create ECR repository for Docker images
aws ecr create-repository \
  --repository-name "$ECR_REPO_NAME" \
  --region "$REGION"

# Get repository URI
ECR_URI="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${ECR_REPO_NAME}"
echo "ECR_URI=$ECR_URI"
```

---

## Step 10 – Create S3 Bucket for Pipeline Artifacts

```bash
# Create S3 bucket for CodePipeline artifacts
if [ "$REGION" = "us-east-1" ]; then
    aws s3api create-bucket \
      --bucket "$ARTIFACT_BUCKET" \
      --region "$REGION"
else
    aws s3api create-bucket \
      --bucket "$ARTIFACT_BUCKET" \
      --region "$REGION" \
      --create-bucket-configuration LocationConstraint="$REGION"
fi

echo "ARTIFACT_BUCKET=$ARTIFACT_BUCKET"
```

---

## Step 11 – Create IAM Role for CodeBuild

```bash
# Create trust policy for CodeBuild
cat > codebuild-trust-policy.json <<'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "codebuild.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

# Create IAM role
aws iam create-role \
  --role-name CodeBuildEKSHelmRole \
  --assume-role-policy-document file://codebuild-trust-policy.json

# Create permissions policy
cat > codebuild-permissions.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:${REGION}:${ACCOUNT_ID}:log-group:/aws/codebuild/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "ecr:GetAuthorizationToken",
        "ecr:BatchCheckLayerAvailability",
        "ecr:CompleteLayerUpload",
        "ecr:UploadLayerPart",
        "ecr:InitiateLayerUpload",
        "ecr:PutImage",
        "ecr:BatchGetImage"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject"
      ],
      "Resource": "arn:aws:s3:::${ARTIFACT_BUCKET}/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "eks:DescribeCluster"
      ],
      "Resource": "arn:aws:eks:${REGION}:${ACCOUNT_ID}:cluster/${CLUSTER_NAME}"
    },
    {
      "Effect": "Allow",
      "Action": "sts:GetCallerIdentity",
      "Resource": "*"
    }
  ]
}
EOF

# Attach permissions policy
aws iam put-role-policy \
  --role-name CodeBuildEKSHelmRole \
  --policy-name CodeBuildEKSHelmPermissions \
  --policy-document file://codebuild-permissions.json

# Wait for IAM propagation
sleep 10
```

---

## Step 12 – Update EKS ConfigMap for CodeBuild Access

```bash
# Get CodeBuild role ARN
CODEBUILD_ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/CodeBuildEKSHelmRole"

# Add CodeBuild role to EKS aws-auth ConfigMap
kubectl get configmap aws-auth -n kube-system -o yaml > aws-auth-backup.yaml

# Create patch for aws-auth
cat > aws-auth-patch.yaml <<EOF
apiVersion: v1
kind: ConfigMap
metadata:
  name: aws-auth
  namespace: kube-system
data:
  mapRoles: |
    - rolearn: ${CODEBUILD_ROLE_ARN}
      username: codebuild
      groups:
        - system:masters
EOF

# Apply the patch (append to existing mapRoles if any)
kubectl patch configmap/aws-auth -n kube-system --patch "$(cat aws-auth-patch.yaml)" || \
kubectl apply -f aws-auth-patch.yaml

echo "CodeBuild role added to EKS cluster access"
```

---

## Step 13 – Create CodeBuild Project

```bash
# Create CodeBuild project configuration
cat > codebuild-project.json <<EOF
{
  "name": "${CODEBUILD_PROJECT}",
  "description": "Build and deploy Flask app to EKS with Helm",
  "source": {
    "type": "CODEPIPELINE",
    "buildspec": "${APP_FOLDER}/buildspec.yml"
  },
  "artifacts": {
    "type": "CODEPIPELINE"
  },
  "environment": {
    "type": "LINUX_CONTAINER",
    "image": "aws/codebuild/standard:7.0",
    "computeType": "BUILD_GENERAL1_SMALL",
    "privilegedMode": true,
    "environmentVariables": [
      {"name": "AWS_DEFAULT_REGION", "value": "${REGION}"},
      {"name": "CLUSTER_NAME", "value": "${CLUSTER_NAME}"},
      {"name": "ECR_REPO_NAME", "value": "${ECR_REPO_NAME}"},
      {"name": "APP_NAME", "value": "${APP_NAME}"},
      {"name": "NAMESPACE", "value": "${NAMESPACE}"}
    ]
  },
  "serviceRole": "arn:aws:iam::${ACCOUNT_ID}:role/CodeBuildEKSHelmRole"
}
EOF

# Create CodeBuild project
aws codebuild create-project \
  --cli-input-json file://codebuild-project.json \
  --region "$REGION"
```

---

## Step 14 – Create IAM Role for CodePipeline

```bash
# Create trust policy for CodePipeline
cat > codepipeline-trust-policy.json <<'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "codepipeline.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

# Create IAM role
aws iam create-role \
  --role-name CodePipelineEKSRole \
  --assume-role-policy-document file://codepipeline-trust-policy.json

# Create permissions policy
cat > codepipeline-permissions.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:GetBucketLocation",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::${ARTIFACT_BUCKET}",
        "arn:aws:s3:::${ARTIFACT_BUCKET}/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "codebuild:BatchGetBuilds",
        "codebuild:StartBuild"
      ],
      "Resource": "arn:aws:codebuild:${REGION}:${ACCOUNT_ID}:project/${CODEBUILD_PROJECT}"
    },
    {
      "Effect": "Allow",
      "Action": [
        "codestar-connections:UseConnection"
      ],
      "Resource": "*"
    }
  ]
}
EOF

# Attach permissions policy
aws iam put-role-policy \
  --role-name CodePipelineEKSRole \
  --policy-name CodePipelineEKSPermissions \
  --policy-document file://codepipeline-permissions.json

# Wait for IAM propagation
sleep 10
```

---

## Step 15 – Create GitHub Connection

```bash
# List existing CodeStar connections
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

## Step 16 – Create CodePipeline

```bash
# Create CodePipeline configuration
cat > pipeline.json <<EOF
{
  "pipeline": {
    "name": "${PIPELINE_NAME}",
    "roleArn": "arn:aws:iam::${ACCOUNT_ID}:role/CodePipelineEKSRole",
    "artifactStore": {
      "type": "S3",
      "location": "${ARTIFACT_BUCKET}"
    },
    "stages": [
      {
        "name": "Source",
        "actions": [
          {
            "name": "SourceAction",
            "actionTypeId": {
              "category": "Source",
              "owner": "AWS",
              "provider": "CodeStarSourceConnection",
              "version": "1"
            },
            "configuration": {
              "ConnectionArn": "${CONNECTION_ARN}",
              "FullRepositoryId": "${GITHUB_OWNER}/${GITHUB_REPO}",
              "BranchName": "main",
              "OutputArtifactFormat": "CODE_ZIP"
            },
            "outputArtifacts": [
              {
                "name": "SourceOutput"
              }
            ]
          }
        ]
      },
      {
        "name": "Build",
        "actions": [
          {
            "name": "BuildAction",
            "actionTypeId": {
              "category": "Build",
              "owner": "AWS",
              "provider": "CodeBuild",
              "version": "1"
            },
            "configuration": {
              "ProjectName": "${CODEBUILD_PROJECT}"
            },
            "inputArtifacts": [
              {
                "name": "SourceOutput"
              }
            ],
            "outputArtifacts": [
              {
                "name": "BuildOutput"
              }
            ]
          }
        ]
      }
    ]
  }
}
EOF

# Create CodePipeline
aws codepipeline create-pipeline \
  --cli-input-json file://pipeline.json \
  --region "$REGION"

echo "Pipeline created: ${PIPELINE_NAME}"
```

---

## Step 17 – Monitor Pipeline Execution

```bash
# Get pipeline execution status
aws codepipeline get-pipeline-state \
  --name "$PIPELINE_NAME" \
  --region "$REGION" \
  --query 'stageStates[*].{Stage:stageName,Status:latestExecution.status}' \
  --output table

# Wait for pipeline to complete (check manually in console)
echo "Monitor pipeline: https://console.aws.amazon.com/codesuite/codepipeline/pipelines/${PIPELINE_NAME}/view"
```

---

## Step 18 – Verify Deployment

```bash
# Check Helm release
helm list -n "$NAMESPACE"

# Check pods
kubectl get pods -n "$NAMESPACE" -l app="$CHART_NAME"

# Check service and get LoadBalancer URL
kubectl get svc -n "$NAMESPACE" "$CHART_NAME"

# Get LoadBalancer DNS
LB_URL=$(kubectl get svc -n "$NAMESPACE" "$CHART_NAME" -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')

echo "Service URL: http://$LB_URL"

# Wait for LoadBalancer to be ready (may take 2-3 minutes)
sleep 60
```

---

## Step 19 – Test Application

```bash
# Test endpoints
echo "Testing home endpoint:"
curl -s "http://$LB_URL/" | jq .

echo -e "\nTesting joke endpoint:"
curl -s "http://$LB_URL/joke" | jq .

echo -e "\nTesting health endpoint:"
curl -s "http://$LB_URL/health" | jq .

# Display URL for browser testing
echo -e "\n📱 Test in browser:"
echo "http://$LB_URL/"
echo "http://$LB_URL/joke"
```

---

## Step 20 – Make Code Changes and Test Rolling Update

```bash
# Navigate to app directory
cd "$REPO_DIR/$APP_FOLDER"

# Update application with new joke
cat > app.py <<'EOF'
from flask import Flask, jsonify
import random
import os

app = Flask(__name__)

jokes = [
    "Why do programmers prefer dark mode? Because light attracts bugs!",
    "Why do Java developers wear glasses? Because they don't C#.",
    "How many programmers does it take to change a light bulb? None, that's a hardware problem.",
    "Why did the developer go broke? Because he used up all his cache.",
    "What's a programmer's favorite hangout place? The Foo Bar.",
    "Why do Kubernetes admins sleep well? Because they have good pod hygiene!",
]

@app.route('/')
def home():
    return jsonify({
        "service": "joke-api",
        "version": os.getenv("APP_VERSION", "2.0.0"),
        "environment": os.getenv("ENVIRONMENT", "production"),
        "status": "running"
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

# Commit and push
git add app.py
git commit -m "Add Kubernetes joke - trigger rolling update"
git push origin main

echo "✅ Code changes pushed - pipeline will auto-trigger"
echo "Watch rolling update: kubectl get pods -n $NAMESPACE -w"
```

---

## Step 21 – Cleanup

```bash
# Delete Helm release
helm uninstall "$APP_NAME" -n "$NAMESPACE"

# Delete CodePipeline
aws codepipeline delete-pipeline \
  --name "$PIPELINE_NAME" \
  --region "$REGION"

# Delete CodeBuild project
aws codebuild delete-project \
  --name "$CODEBUILD_PROJECT" \
  --region "$REGION"

# Delete ECR repository
aws ecr delete-repository \
  --repository-name "$ECR_REPO_NAME" \
  --force \
  --region "$REGION"

# Delete IAM roles
aws iam delete-role-policy \
  --role-name CodePipelineEKSRole \
  --policy-name CodePipelineEKSPermissions

aws iam delete-role --role-name CodePipelineEKSRole

aws iam delete-role-policy \
  --role-name CodeBuildEKSHelmRole \
  --policy-name CodeBuildEKSHelmPermissions

aws iam delete-role --role-name CodeBuildEKSHelmRole

# Empty and delete S3 bucket
aws s3 rm "s3://$ARTIFACT_BUCKET" --recursive
aws s3api delete-bucket \
  --bucket "$ARTIFACT_BUCKET" \
  --region "$REGION"

# Remove application directory
cd "$REPO_DIR"
rm -rf "$APP_FOLDER"
git rm -r "$APP_FOLDER"
git commit -m "Cleanup: Remove EKS Helm app"
git push origin main

echo "✅ Cleanup complete"
```

---

## Summary

In this lab, you:
- Created Helm chart for Flask application with templates and values
- Configured CodePipeline for automated EKS deployments
- Built Docker images and pushed to ECR via CodeBuild
- Deployed to EKS using Helm with rolling updates
- Tested Kubernetes service with LoadBalancer
- Implemented automated CI/CD for Kubernetes

**Key Takeaways:**
- **Helm Charts**: Package Kubernetes applications with templating
- **Rolling Updates**: Kubernetes gradually replaces pods with zero downtime
- **Pipeline Automation**: CodePipeline triggers on GitHub commits
- **EKS Integration**: CodeBuild needs cluster access via aws-auth ConfigMap
- **Production Ready**: Liveness and readiness probes ensure reliability

**CI/CD Workflow:**
```
GitHub → CodePipeline → CodeBuild (build + push + helm deploy) → EKS
```

---

## Best Practices

**Helm Charts:**
- Use values.yaml for environment-specific configuration
- Template all resources for reusability
- Version your charts with Chart.yaml
- Include health probes in deployment templates

**EKS Deployments:**
- Use ConfigMaps and Secrets for configuration
- Set resource limits and requests
- Implement readiness and liveness probes
- Use multiple replicas for high availability

**CodeBuild:**
- Install kubectl and helm in build phase
- Update kubeconfig for cluster access
- Use commit SHA for image tags (traceability)
- Verify deployment after helm upgrade

**Security:**
- Use IAM roles for EKS access (not kubeconfig)
- Update aws-auth ConfigMap carefully
- Use private ECR repositories
- Implement RBAC in Kubernetes

---

## Troubleshooting

**CodeBuild cannot access EKS cluster:**
- Verify CodeBuild role is in aws-auth ConfigMap
- Check EKS cluster security group allows CodeBuild access
- Ensure IAM role has eks:DescribeCluster permission

**Helm deployment fails:**
- Check chart syntax: `helm lint ./helm/joke-api-chart`
- Verify image exists in ECR
- Review pod logs: `kubectl logs -n default -l app=joke-api-chart`

**LoadBalancer service not getting external IP:**
- Wait 2-3 minutes for AWS to provision ELB
- Check AWS Load Balancer controller is installed
- Verify security groups allow traffic

**Rolling update stuck:**
- Check readiness probe configuration
- Verify new pods are healthy: `kubectl describe pod`
- Review deployment events: `kubectl describe deployment`

---

## Additional Resources

- [Helm Documentation](https://helm.sh/docs/)
- [EKS Best Practices](https://aws.github.io/aws-eks-best-practices/)
- [Kubernetes Rolling Updates](https://kubernetes.io/docs/tutorials/kubernetes-basics/update/update-intro/)
- [AWS CodePipeline for EKS](https://docs.aws.amazon.com/codepipeline/latest/userguide/eks-example.html)
