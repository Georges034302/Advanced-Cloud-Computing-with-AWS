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
- Existing EKS cluster (from Session 6 Lab 6.D)
- GitHub account with repository access
- IAM permissions for ECR, EKS
- Region: ap-southeast-2

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
APP_FOLDER="flask-k8s-app"
APP_NAME="joke-api"
CHART_NAME="joke-api-chart"
ECR_REPO_NAME="joke-api-k8s"
CLUSTER_NAME="my-eks-cluster"
NAMESPACE="default"

# Get AWS account ID
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# Build ECR URI
ECR_URI="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${ECR_REPO_NAME}"

# Display configuration
echo "REGION=$REGION"
echo "ACCOUNT_ID=$ACCOUNT_ID"
echo "CLUSTER_NAME=$CLUSTER_NAME"
echo "ECR_URI=$ECR_URI"
```

---

## Step 2 – Verify EKS Cluster and Configure kubectl

```bash
# Verify EKS cluster exists
aws eks describe-cluster \
  --name "$CLUSTER_NAME" \
  --region "$REGION" \
  --query 'cluster.status' \
  --output text

# Update kubeconfig to access EKS cluster
# This configures kubectl to communicate with your EKS cluster
aws eks update-kubeconfig \
  --name "$CLUSTER_NAME" \
  --region "$REGION"

# Verify kubectl can access the cluster
kubectl get nodes

# Expected output: List of worker nodes in READY status
```

---

## Step 3 – Create Application Directory

```bash
# Create application directory in current location
mkdir -p "$APP_FOLDER"
cd "$APP_FOLDER"

echo "Working directory: $(pwd)"
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

## Step 7 – Create ECR Repository

```bash
# Create ECR repository for Docker images
aws ecr create-repository \
  --repository-name "$ECR_REPO_NAME" \
  --region "$REGION"

# Display repository URI (already set in Step 1)
echo "ECR_URI=$ECR_URI"
```

---

## Step 8 – Build Docker Image Locally

```bash
# Build Docker image with ECR URI and latest tag
# -t: Tag the image
docker build -t "${ECR_URI}:latest" .

# Verify image was built successfully
docker images | grep "$ECR_REPO_NAME"
```

---

## Step 9 – Test Docker Image Locally (Optional)

```bash
# Run container locally to test
# -d: Run in detached mode
# -p: Map container port 8000 to host port 8080
# --name: Give container a friendly name
docker run -d -p 8080:8000 --name joke-api-test "${ECR_URI}:latest"

# Wait for container to start
sleep 3

# Test endpoints
curl http://localhost:8080/              # Service info
curl http://localhost:8080/joke          # Get a joke
curl http://localhost:8080/health        # Health check

# Open in browser to test endpoints
"$BROWSER" "http://localhost:8080/" 
"$BROWSER" "http://localhost:8080/joke" 
"$BROWSER" "http://localhost:8080/health" 

# Stop and remove test container
docker stop joke-api-test
docker rm joke-api-test
```

---

## Step 10 – Login to ECR and Push Image

```bash
# Authenticate Docker to ECR
# This retrieves temporary authentication token from ECR
aws ecr get-login-password --region "$REGION" | \
  docker login --username AWS --password-stdin \
  "${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"

# Push Docker image to ECR
# This uploads all layers of the image to ECR
docker push "${ECR_URI}:latest"

# Verify image in ECR
aws ecr describe-images \
  --repository-name "$ECR_REPO_NAME" \
  --region "$REGION"
```

---

## Step 11 – Validate Helm Chart

```bash
# Check Helm chart syntax and values
# This validates the chart structure and templates
helm lint "./helm/${CHART_NAME}"

# Dry-run to see what Kubernetes resources will be created
# --dry-run: Simulate installation without applying
# --debug: Show all generated manifests
helm install "${APP_NAME}" "./helm/${CHART_NAME}" \
  --namespace "$NAMESPACE" \
  --dry-run --debug

# Expected: YAML output showing Deployment and Service resources
```

---

## Step 12 – Deploy to EKS with Helm

```bash
# Deploy application to EKS using Helm
# upgrade --install: Install if not exists, upgrade if exists
# --wait: Wait for all resources to be ready
# --timeout: Maximum time to wait
helm upgrade --install "${APP_NAME}" "./helm/${CHART_NAME}" \
  --namespace "$NAMESPACE" \
  --wait \
  --timeout 5m

# Verify deployment
kubectl get pods -n "$NAMESPACE" -l app="$CHART_NAME"

# Expected: 2 pods in Running status (replicaCount: 2)
```

---

## Step 13 – Check Deployment Status

```bash
# View deployment details
kubectl get deployment -n "$NAMESPACE" "$CHART_NAME"

# View pod details
kubectl get pods -n "$NAMESPACE" -l app="$CHART_NAME" -o wide

# View service and get LoadBalancer URL
kubectl get svc -n "$NAMESPACE" "$CHART_NAME"

# Get detailed service info including LoadBalancer hostname
kubectl describe svc -n "$NAMESPACE" "$CHART_NAME"

# Wait 2-3 minutes for AWS to provision the LoadBalancer
```

---

## Step 14 – Get LoadBalancer URL and Test Application

```bash
# Wait for LoadBalancer to be provisioned (2-3 minutes)
# Get the LoadBalancer hostname
LB_HOSTNAME=$(kubectl get svc -n "$NAMESPACE" "$CHART_NAME" \
  -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')

echo "LoadBalancer URL: http://$LB_HOSTNAME"

# Test application endpoints
echo "Testing application..."
curl -s "http://$LB_HOSTNAME/" | jq .              # Service info
curl -s "http://$LB_HOSTNAME/joke" | jq .          # Get a joke
curl -s "http://$LB_HOSTNAME/health" | jq .        # Health check

# Open application in browser
"$BROWSER" "http://$LB_HOSTNAME/" 
"$BROWSER" "http://$LB_HOSTNAME/joke" 
"$BROWSER" "http://$LB_HOSTNAME/health" 
```

---

## Step 15 – Test Rolling Update

```bash
# Update application version to test rolling update
# Modify the values.yaml to change APP_VERSION
sed -i 's/value: "1.0.0"/value: "2.0.0"/' "helm/${CHART_NAME}/values.yaml"

# Perform rolling update with Helm
# Helm will update the deployment and Kubernetes will perform rolling update
helm upgrade "${APP_NAME}" "./helm/${CHART_NAME}" \
  --namespace "$NAMESPACE" \
  --wait \
  --timeout 5m

# Watch the rolling update in real-time
# This shows pods being terminated and new ones starting
kubectl rollout status deployment/"$CHART_NAME" -n "$NAMESPACE"

# Verify new version is deployed
kubectl get pods -n "$NAMESPACE" -l app="$CHART_NAME"

# Test updated application
curl -s "http://$LB_HOSTNAME/" | jq .

# Expected: version should show "2.0.0"
```

---

## Step 16 – View Application Logs

```bash
# Get pod names
POD_NAMES=$(kubectl get pods -n "$NAMESPACE" -l app="$CHART_NAME" -o jsonpath='{.items[*].metadata.name}')

# View logs from first pod
FIRST_POD=$(echo $POD_NAMES | awk '{print $1}')
kubectl logs -n "$NAMESPACE" "$FIRST_POD"

# Stream logs in real-time
kubectl logs -n "$NAMESPACE" "$FIRST_POD" -f

# Press Ctrl+C to stop streaming
```

---

## Step 17 – View Helm Release Information

```bash
# List all Helm releases in namespace
helm list -n "$NAMESPACE"

# Get release history
helm history "${APP_NAME}" -n "$NAMESPACE"

# Get release values
helm get values "${APP_NAME}" -n "$NAMESPACE"

# Get all Kubernetes manifests for the release
helm get manifest "${APP_NAME}" -n "$NAMESPACE"
```

---

## Step 18 – Cleanup

```bash
# Uninstall Helm release from EKS
# This removes all Kubernetes resources (Deployment, Service, Pods)
helm uninstall "$APP_NAME" -n "$NAMESPACE"

# Verify resources are deleted
kubectl get all -n "$NAMESPACE" -l app="$CHART_NAME"

# Delete ECR repository with all images
aws ecr delete-repository \
  --repository-name "$ECR_REPO_NAME" \
  --force \
  --region "$REGION"

# Remove application directory
cd ..
rm -rf "$APP_FOLDER"

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

