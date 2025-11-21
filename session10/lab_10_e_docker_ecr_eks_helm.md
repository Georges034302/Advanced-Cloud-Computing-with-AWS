# Lab 10.E: Docker → ECR → EKS with Helm - Kubernetes Deployment
<img width="1536" height="605" alt="IMG" src="https://github.com/user-attachments/assets/5d406dba-462d-4145-949d-24023c9e4be3" />


## Overview
This lab demonstrates deploying containerized applications to Amazon EKS using Helm charts. You'll create a Flask API, build Docker images locally, push to ECR, package with Helm, and deploy to EKS with rolling updates. This showcases Kubernetes deployment workflows and Helm package management.

---

## Objectives
- Create Helm chart for Flask application
- Build Docker images locally and push to ECR
- Deploy to EKS using Helm from local machine
- Implement rolling updates with Kubernetes
- Understand Helm templating and values
- Test applications on EKS LoadBalancer

---

## Prerequisites
- AWS CLI configured (`aws configure`)
- Docker installed and running (`docker --version`)
- kubectl installed (`kubectl version`)
- Helm 3 installed (`helm version`)
- Git installed (`git --version`)
- IAM permissions for ECR, EKS, VPC, EC2
- Region: ap-southeast-2
- **Note:** This lab will create an EKS cluster (~15-20 minutes)

---

## Architecture

```
Local Development → Docker Build → ECR → kubectl/Helm → EKS Cluster
                         ↓
                    Docker image
```

**Deployment Flow:**
1. Create Flask application and Helm chart locally
2. Build Docker image locally
3. Push image to Amazon ECR
4. Deploy to EKS using `helm upgrade --install`
5. Kubernetes performs rolling update of pods

---

## Step 1 – Set Variables

```bash
# Set AWS region
REGION="ap-southeast-2"
export AWS_REGION="$REGION"

# Application configuration
APP_FOLDER="flask-k8s-app"           # Local workspace directory
APP_NAME="joke-api"                  # Helm release name
CHART_NAME="joke-api-chart"          # Helm chart name
ECR_REPO_NAME="joke-api-k8s"         # ECR repository name
CLUSTER_NAME="my-eks-cluster"        # EKS cluster name (from Lab 6.D)
NAMESPACE="default"                  # Kubernetes namespace

# Get AWS account ID for ECR URI
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo "ACCOUNT_ID=$ACCOUNT_ID"

# Build ECR repository URI
ECR_URI="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${ECR_REPO_NAME}"
echo "ECR_URI=$ECR_URI"
```

---

## Step 2 – Create EKS Cluster

```bash
# Create EKS cluster using eksctl (takes ~15-20 minutes)
# eksctl creates VPC, subnets, security groups, and managed node group automatically
eksctl create cluster \
  --name "$CLUSTER_NAME" \
  --region "$REGION" \
  --nodegroup-name workers \
  --node-type t3.medium \
  --nodes 2 \
  --nodes-min 2 \
  --nodes-max 3 \
  --managed

# eksctl automatically configures kubectl context
# Verify cluster is ready
kubectl get nodes
```

---

## Step 3 – Verify EKS Cluster and Configure kubectl

```bash
# Verify EKS cluster exists and is active
aws eks describe-cluster \
  --name "$CLUSTER_NAME" \
  --region "$REGION" \
  --query 'cluster.status' \
  --output text

# Verify kubectl connection to cluster
kubectl get nodes
```

---

## Step 4 – Create Application Directory

```bash
# Create and navigate to application workspace
mkdir -p "$APP_FOLDER" && cd "$APP_FOLDER"
echo "Working directory: $(pwd)"
```

---

## Step 5 – Create Flask Application

```bash
# Create Flask API with three endpoints: /, /joke, /health
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

## Step 6 – Create Requirements and Dockerfile

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

## Step 7 – Create Helm Chart Structure

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

## Step 8 – Create ECR Repository

```bash
# Create ECR repository to store Docker images
aws ecr create-repository \
  --repository-name "$ECR_REPO_NAME" \
  --region "$REGION"
echo "ECR_URI=$ECR_URI"
```

---

## Step 9 – Build Docker Image Locally

```bash
# Build Docker image and tag with ECR URI
docker build -t "${ECR_URI}:latest" .

# Verify image created successfully
docker images | grep "$ECR_REPO_NAME"
```

---

## Step 10 – Test Docker Image Locally (Optional)

```bash
# Run container locally (maps container port 8000 → host port 8080)
docker run -d -p 8080:8000 --name joke-api-test "${ECR_URI}:latest"
sleep 3

# Test endpoints with curl
curl http://localhost:8080/              # Service info
curl http://localhost:8080/joke          # Get random joke
curl http://localhost:8080/health        # Health check

# Test endpoints in browser
"$BROWSER" "http://localhost:8080/" 
"$BROWSER" "http://localhost:8080/joke" 
"$BROWSER" "http://localhost:8080/health" 

# Clean up test container
docker stop joke-api-test && docker rm joke-api-test
```

---

## Step 11 – Login to ECR and Push Image

```bash
# Authenticate Docker client to ECR
aws ecr get-login-password --region "$REGION" | \
  docker login --username AWS --password-stdin \
  "${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"

# Push Docker image to ECR repository
docker push "${ECR_URI}:latest"

# Verify image uploaded successfully
aws ecr describe-images \
  --repository-name "$ECR_REPO_NAME" \
  --region "$REGION" \
  --query 'imageDetails[0].[imageTags[0],imagePushedAt]' \
  --output table
```

---

## Step 12 – Validate Helm Chart

```bash
# Validate Helm chart syntax and structure
helm lint "./helm/${CHART_NAME}"

# Preview Kubernetes resources that will be created (dry-run)
helm install "${APP_NAME}" "./helm/${CHART_NAME}" \
  --namespace "$NAMESPACE" \
  --dry-run --debug | head -100
```

---

## Step 13 – Deploy to EKS with Helm

```bash
# Deploy application to EKS (installs if new, upgrades if exists)
helm upgrade --install "${APP_NAME}" "./helm/${CHART_NAME}" \
  --namespace "$NAMESPACE" \
  --wait \
  --timeout 5m

# Verify pods are running (should see 2 replicas)
kubectl get pods -n "$NAMESPACE" -l app="$CHART_NAME"
```

---

## Step 14 – Check Deployment Status

```bash
# View all resources (deployment, pods, service)
kubectl get all -n "$NAMESPACE" -l app="$CHART_NAME"

# View service details including LoadBalancer hostname
kubectl describe svc -n "$NAMESPACE" "$CHART_NAME"

# Note: Wait 2-3 minutes for AWS to provision the LoadBalancer
```

---

## Step 15 – Get LoadBalancer URL and Test Application

```bash
# Get LoadBalancer hostname (wait 2-3 minutes if not ready)
LB_HOSTNAME=$(kubectl get svc -n "$NAMESPACE" "$CHART_NAME" \
  -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')
echo "LoadBalancer URL: http://$LB_HOSTNAME"

# Test application endpoints with curl
curl -s "http://$LB_HOSTNAME/" | jq .              # Service info
curl -s "http://$LB_HOSTNAME/joke" | jq .          # Random joke
curl -s "http://$LB_HOSTNAME/health" | jq .        # Health check

# Test application in browser
"$BROWSER" "http://$LB_HOSTNAME/" 
"$BROWSER" "http://$LB_HOSTNAME/joke" 
"$BROWSER" "http://$LB_HOSTNAME/health" 
```

---

## Step 16 – Test Rolling Update

```bash
# Navigate to application directory
cd /workspaces/Advanced-Cloud-Computing-with-AWS/flask-k8s-app

# Update image tag from 1.0.0 to 2.0.0 in values.yaml
sed -i 's/tag: "1.0.0"/tag: "2.0.0"/' helm/joke-api-chart/values.yaml

# Update APP_VERSION environment variable to 2.0.0
sed -i 's/APP_VERSION: "1.0.0"/APP_VERSION: "2.0.0"/' helm/joke-api-chart/values.yaml

# Verify changes were applied successfully
grep -E 'tag:|APP_VERSION:' helm/joke-api-chart/values.yaml

# Build new Docker image with version 2.0.0 tag
docker build -t joke-api-k8s:2.0.0 .

# Tag image for ECR repository
docker tag joke-api-k8s:2.0.0 \
  013709423315.dkr.ecr.ap-southeast-2.amazonaws.com/joke-api-k8s:2.0.0

# Push new version to ECR
docker push \
  013709423315.dkr.ecr.ap-southeast-2.amazonaws.com/joke-api-k8s:2.0.0

# Perform rolling update (Kubernetes replaces pods gradually with zero downtime)
helm upgrade "${APP_NAME}" "./helm/${CHART_NAME}" \
  --namespace "$NAMESPACE" \
  --wait \
  --timeout 5m

# Watch rolling update progress in real-time
kubectl rollout status deployment/"$CHART_NAME" -n "$NAMESPACE"

# Get LoadBalancer URL
LB_URL=$(kubectl get svc -n "$NAMESPACE" "$CHART_NAME" \
  -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')

# Test updated version - should display "2.0.0"
echo "=== Testing version after update ==="
curl -s "http://$LB_URL/" | grep version
echo ""

# Verify health endpoint also shows version 2.0.0
curl -s "http://$LB_URL/health"
```

---

## Step 17 – View Application Logs

```bash
# Get first pod name
FIRST_POD=$(kubectl get pods -n "$NAMESPACE" -l app="$CHART_NAME" \
  -o jsonpath='{.items[0].metadata.name}')

# View pod logs
kubectl logs -n "$NAMESPACE" "$FIRST_POD" --tail=50

# Stream logs in real-time (Ctrl+C to stop)
kubectl logs -n "$NAMESPACE" "$FIRST_POD" -f
```

---

## Step 18 – View Helm Release Information

```bash
# List all Helm releases
helm list -n "$NAMESPACE"

# View deployment history (shows all revisions)
helm history "${APP_NAME}" -n "$NAMESPACE"

# View current values used for deployment
helm get values "${APP_NAME}" -n "$NAMESPACE"
```

---

## Step 19 – Cleanup

```bash
# Uninstall Helm release (removes all Kubernetes resources)
helm uninstall "$APP_NAME" -n "$NAMESPACE"

# Verify resources deleted
kubectl get all -n "$NAMESPACE" -l app="$CHART_NAME"

# Delete ECR repository and all images
aws ecr delete-repository \
  --repository-name "$ECR_REPO_NAME" \
  --force \
  --region "$REGION"

# Delete EKS cluster (removes all nodes, VPC, and associated resources)
eksctl delete cluster --name "$CLUSTER_NAME" --region "$REGION"

# Remove local application directory
cd .. && rm -rf "$APP_FOLDER"

echo "✅ Cleanup complete"
```

---

## Summary

In this lab, you:
- Created Helm chart for Flask application with templates and values
- Built Docker images locally and pushed to ECR
- Deployed to EKS using Helm with rolling updates
- Tested Kubernetes service with LoadBalancer
- Updated application and performed rolling update
- Viewed logs and Helm release information

**Key Takeaways:**
- **Helm Charts**: Package Kubernetes applications with templates and values
- **Rolling Updates**: Kubernetes gradually replaces pods with zero downtime
- **Local Development**: Build and deploy from local machine without CI/CD pipeline
- **EKS Deployment**: kubectl and Helm interact directly with EKS cluster
- **Production Ready**: Liveness and readiness probes ensure reliability

**Deployment Workflow:**
```
Local Development → Docker Build → ECR → Helm Deploy → EKS Cluster
```

---

## Best Practices

**Helm Charts:**
- Use `values.yaml` for environment-specific configuration
- Template all resources for reusability across environments
- Version your charts with `Chart.yaml`
- Include health probes in deployment templates
- Use `.Values` for all configurable parameters

**Docker Images:**
- Build locally for quick iteration and testing
- Use descriptive tags (not just `latest` in production)
- Test containers locally before pushing to ECR
- Keep images small using slim base images

**EKS Deployments:**
- Always set resource limits and requests
- Implement readiness and liveness probes
- Use multiple replicas for high availability
- Use LoadBalancer type for external access
- Monitor pod health with `kubectl get pods`

**Kubernetes Operations:**
- Use `helm lint` to validate charts before deployment
- Use `--dry-run --debug` to preview changes
- Monitor rollout status during updates
- Check logs regularly with `kubectl logs`
- Use labels for resource organization

---

## Troubleshooting

**kubectl cannot connect to EKS:**
- Run `aws eks update-kubeconfig` to configure kubectl
- Verify cluster exists: `aws eks describe-cluster --name CLUSTER_NAME`
- Check IAM permissions for EKS access
- Ensure correct AWS region is set

**Docker build fails:**
- Verify Docker daemon is running: `docker info`
- Check Dockerfile syntax and paths
- Ensure all required files are present
- Use `docker build --no-cache` to force clean build

**ECR push fails:**
- Check ECR login succeeded (look for "Login Succeeded")
- Verify ECR repository exists
- Ensure IAM permissions for ECR operations
- Check network connectivity to ECR

**Helm deployment fails:**
- Validate chart: `helm lint ./helm/joke-api-chart`
- Check image exists in ECR: `aws ecr describe-images`
- Review pod logs: `kubectl logs -n default -l app=joke-api-chart`
- Check events: `kubectl describe deployment joke-api-chart`

**LoadBalancer not getting external IP:**
- Wait 2-3 minutes for AWS to provision ELB
- Check service status: `kubectl describe svc joke-api-chart`
- Verify AWS Load Balancer Controller is installed on EKS
- Check security groups allow traffic on port 80

**Pods not starting:**
- Check pod status: `kubectl describe pod POD_NAME`
- View pod logs: `kubectl logs POD_NAME`
- Verify readiness probe configuration
- Check image pull errors (ECR authentication)

**Rolling update stuck:**
- Check readiness probe passes for new pods
- Verify sufficient cluster resources (CPU/memory)
- Review deployment events: `kubectl describe deployment`
- Check pod logs for application errors

---

## Additional Resources

- [Helm Documentation](https://helm.sh/docs/)
- [Amazon EKS Best Practices](https://aws.github.io/aws-eks-best-practices/)
- [Kubernetes Rolling Updates](https://kubernetes.io/docs/tutorials/kubernetes-basics/update/update-intro/)
- [Amazon ECR User Guide](https://docs.aws.amazon.com/ecr/)
- [kubectl Cheat Sheet](https://kubernetes.io/docs/reference/kubectl/cheatsheet/)

