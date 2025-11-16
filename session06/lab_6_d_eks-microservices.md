# Lab 6.D: Deploy Microservices to Amazon EKS
<img width="400" height="800" alt="IMG" src="https://github.com/user-attachments/assets/478bbdbc-9333-480d-9029-e7126f0bcb90" />

## Overview
This lab demonstrates how to deploy containerized microservices to Amazon Elastic Kubernetes Service (EKS). You'll create an EKS cluster, build two microservices for a student management system (Tutor service and Report service), deploy them as Kubernetes pods, expose them via services, and test inter-service communication. This provides hands-on experience with Kubernetes orchestration on AWS.

---

## Objectives
- Install and configure kubectl and eksctl
- Create EKS cluster with managed node group
- Build two microservices: Tutor (query student reports) and Report (student data)
- Push Docker images to ECR
- Deploy microservices to EKS as Kubernetes deployments
- Create Kubernetes services to expose microservices
- Test service discovery and communication
- Clean up all resources to stop charges

---

## Prerequisites
- AWS CLI configured (`aws configure`)
- Docker installed and running
- kubectl installed (`brew install kubectl` or download from kubernetes.io)
- eksctl installed (`brew install eksctl` or download from eksctl.io)
- IAM permissions for EKS, EC2, ECR, CloudFormation, and IAM
- Basic understanding of Kubernetes concepts
- Minimum 30 minutes for cluster creation

---

## Step 1 – Install Prerequisites and Set Variables

```bash
# Verify prerequisites
kubectl version --client || { echo "❌ kubectl not installed"; exit 1; }
eksctl version || { echo "❌ eksctl not installed"; exit 1; }

# Get AWS account ID and set variables
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REGION="ap-southeast-2"
CLUSTER_NAME="student-api-cluster"
NODE_TYPE="t3.small"
NODE_COUNT=2
SERVICE1_NAME="tutor"
SERVICE2_NAME="report"

echo "ACCOUNT_ID=$ACCOUNT_ID"
echo "REGION=$REGION"
```

---

## Step 2 – Create Tutor Microservice

```bash
# Create project directory
mkdir -p student-microservices
cd student-microservices

# Create tutor microservice
mkdir -p tutor
cd tutor

cat > app.py <<'EOF'
from flask import Flask, jsonify
import requests
import os

app = Flask(__name__)

# Report service URL (will be set via environment variable in Kubernetes)
REPORT_SERVICE_URL = os.getenv('REPORT_SERVICE_URL', 'http://report')

@app.route('/')
def home():
    return jsonify({
        "service": "Tutor API",
        "platform": "Amazon EKS",
        "endpoints": {
            "/": "This message",
            "/student/<id>": "Get student report by ID",
            "/students": "Get all student reports",
            "/health": "Health check"
        }
    })

@app.route('/student/<student_id>')
def get_student_report(student_id):
    try:
        response = requests.get(f'{REPORT_SERVICE_URL}/student/{student_id}')
        if response.status_code == 200:
            return jsonify({
                "service": "tutor",
                "student": response.json()
            })
        else:
            return jsonify({"error": "Student not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/students')
def get_all_students():
    try:
        response = requests.get(f'{REPORT_SERVICE_URL}/students')
        if response.status_code == 200:
            return jsonify({
                "service": "tutor",
                "total_students": response.json()['count'],
                "students": response.json()['students']
            })
        else:
            return jsonify({"error": "Unable to fetch students"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/health')
def health():
    return jsonify({"status": "healthy"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80)
EOF

# Create requirements
cat > requirements.txt <<'EOF'
flask==3.0.0
werkzeug==3.0.1
EOF

# Create Dockerfile
cat > Dockerfile <<'EOF'
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
EXPOSE 80
CMD ["python", "app.py"]
EOF

cd ..
```

---

## Step 3 – Create Report Microservice

```bash
# Create report microservice
mkdir -p report
cd report

cat > app.py <<'EOF'
from flask import Flask, jsonify

app = Flask(__name__)

# Sample student data
STUDENTS = [
    {"id": "S001", "name": "Alice Johnson", "mark": 92, "grade": "HD"},
    {"id": "S002", "name": "Bob Smith", "mark": 78, "grade": "D"},
    {"id": "S003", "name": "Charlie Davis", "mark": 65, "grade": "C"},
    {"id": "S004", "name": "Diana Prince", "mark": 88, "grade": "D"},
    {"id": "S005", "name": "Ethan Hunt", "mark": 55, "grade": "P"},
    {"id": "S006", "name": "Fiona Green", "mark": 42, "grade": "Z"},
    {"id": "S007", "name": "George Wilson", "mark": 95, "grade": "HD"},
    {"id": "S008", "name": "Hannah Lee", "mark": 71, "grade": "C"}
]

@app.route('/')
def home():
    return jsonify({
        "service": "Report API",
        "platform": "Amazon EKS",
        "endpoints": {
            "/": "This message",
            "/student/<id>": "Get student report by ID",
            "/students": "Get all student reports",
            "/health": "Health check"
        }
    })

@app.route('/student/<student_id>')
def get_student(student_id):
    student = next((s for s in STUDENTS if s['id'] == student_id), None)
    if student:
        return jsonify(student)
    else:
        return jsonify({"error": "Student not found"}), 404

@app.route('/students')
def get_all_students():
    return jsonify({
        "service": "report",
        "count": len(STUDENTS),
        "students": STUDENTS
    })

@app.route('/health')
def health():
    return jsonify({"status": "healthy"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80)
EOF

# Create requirements
cat > requirements.txt <<'EOF'
flask==3.0.0
werkzeug==3.0.1
EOF

# Create Dockerfile
cat > Dockerfile <<'EOF'
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
EXPOSE 80
CMD ["python", "app.py"]
EOF

cd ..
```

---

## Step 4 – Create ECR Repositories

```bash
# Create ECR repositories
aws ecr create-repository --repository-name "$SERVICE1_NAME" --region "$REGION"
aws ecr create-repository --repository-name "$SERVICE2_NAME" --region "$REGION"

# Get repository URIs
TUTOR_REPO=$(aws ecr describe-repositories \
  --repository-names "$SERVICE1_NAME" \
  --query 'repositories[0].repositoryUri' \
  --output text \
  --region "$REGION")
echo "TUTOR_REPO=$TUTOR_REPO"

REPORT_REPO=$(aws ecr describe-repositories \
  --repository-names "$SERVICE2_NAME" \
  --query 'repositories[0].repositoryUri' \
  --output text \
  --region "$REGION")
echo "REPORT_REPO=$REPORT_REPO"
```

---

## Step 5 – Build and Push Docker Images

```bash
# Authenticate Docker to ECR
aws ecr get-login-password --region "$REGION" | docker login \
  --username AWS \
  --password-stdin "${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"

# Build and push tutor image
cd tutor
docker build --tag "${TUTOR_REPO}:latest" --platform linux/amd64 .
docker push "${TUTOR_REPO}:latest"
cd ..

# Build and push report image
cd report
docker build --tag "${REPORT_REPO}:latest" --platform linux/amd64 .
docker push "${REPORT_REPO}:latest"
cd ..
```

---

## Step 6 – Create EKS Cluster

```bash
# Return to parent directory
cd ..

echo ""
echo "⚠️  Creating EKS cluster (takes 15-20 minutes)"

# Create EKS cluster with eksctl
eksctl create cluster \
  --name "$CLUSTER_NAME" \
  --region "$REGION" \
  --nodegroup-name standard-workers \
  --node-type "$NODE_TYPE" \
  --nodes "$NODE_COUNT" \
  --nodes-min "$NODE_COUNT" \
  --nodes-max "$NODE_COUNT" \
  --managed

# If cluster exists but nodegroup wasn't created, create it separately
eksctl create nodegroup \
  --cluster "$CLUSTER_NAME" \
  --region "$REGION" \
  --name standard-workers \
  --node-type "$NODE_TYPE" \
  --nodes "$NODE_COUNT" \
  --nodes-min "$NODE_COUNT" \
  --nodes-max "$NODE_COUNT" \
  --managed
```

---

## Step 7 – Verify Cluster and Nodes

```bash
# Configure kubectl to use the EKS cluster
aws eks update-kubeconfig --name "$CLUSTER_NAME" --region "$REGION"

# Verify kubectl context
kubectl config current-context

# Get nodes
kubectl get nodes -o wide

# Get cluster info
kubectl cluster-info

# Check EKS cluster status
aws eks describe-cluster \
  --name "$CLUSTER_NAME" \
  --region "$REGION" \
  --query 'cluster.status' \
  --output text

# Check CloudFormation stack status
aws cloudformation describe-stacks \
  --stack-name "eksctl-${CLUSTER_NAME}-cluster" \
  --region "$REGION" \
  --query 'Stacks[0].[StackStatus,CreationTime]' \
  --output text
```

---

## Step 8 – Create Kubernetes Deployments

```bash
# Create deployment for tutor
cat > tutor-deployment.yaml <<EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: tutor
  labels:
    app: tutor
spec:
  replicas: 2
  selector:
    matchLabels:
      app: tutor
  template:
    metadata:
      labels:
        app: tutor
    spec:
      containers:
      - name: tutor
        image: ${TUTOR_REPO}:latest
        env:
        - name: REPORT_SERVICE_URL
          value: "http://report"
        ports:
        - containerPort: 80
        resources:
          requests:
            memory: "64Mi"
            cpu: "100m"
          limits:
            memory: "128Mi"
            cpu: "200m"
        livenessProbe:
          httpGet:
            path: /health
            port: 80
          initialDelaySeconds: 10
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 80
          initialDelaySeconds: 5
          periodSeconds: 5
EOF

# Create deployment for report
cat > report-deployment.yaml <<EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: report
  labels:
    app: report
spec:
  replicas: 2
  selector:
    matchLabels:
      app: report
  template:
    metadata:
      labels:
        app: report
    spec:
      containers:
      - name: report
        image: ${REPORT_REPO}:latest
        ports:
        - containerPort: 80
        resources:
          requests:
            memory: "64Mi"
            cpu: "100m"
          limits:
            memory: "128Mi"
            cpu: "200m"
        livenessProbe:
          httpGet:
            path: /health
            port: 80
          initialDelaySeconds: 10
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 80
          initialDelaySeconds: 5
          periodSeconds: 5
EOF

# Apply deployments
kubectl apply -f tutor-deployment.yaml
kubectl apply -f report-deployment.yaml

sleep 30
```

---

## Step 9 – Create Kubernetes Services

```bash
# Create service for report (ClusterIP - internal only)
cat > report-service.yaml <<'EOF'
apiVersion: v1
kind: Service
metadata:
  name: report
spec:
  type: ClusterIP
  selector:
    app: report
  ports:
  - port: 80
    targetPort: 80
    protocol: TCP
EOF

# Create service for tutor (LoadBalancer - external access)
cat > tutor-service.yaml <<'EOF'
apiVersion: v1
kind: Service
metadata:
  name: tutor
spec:
  type: LoadBalancer
  selector:
    app: tutor
  ports:
  - port: 80
    targetPort: 80
    protocol: TCP
EOF

# Apply services
kubectl apply -f report-service.yaml
kubectl apply -f tutor-service.yaml

echo "Waiting for LoadBalancer to provision (~3 minutes)..."
sleep 180
```

---

## Step 10 – Get Service URLs and Test

```bash
# Get tutor service URL
TUTOR_URL=$(kubectl get service tutor -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')

echo "TUTOR_URL=$TUTOR_URL"

# Test tutor service
curl -s "http://${TUTOR_URL}/" | python3 -m json.tool
curl -s "http://${TUTOR_URL}/students" | python3 -m json.tool
curl -s "http://${TUTOR_URL}/student/S001" | python3 -m json.tool
curl -s "http://${TUTOR_URL}/student/S005" | python3 -m json.tool

# Open in browser
"$BROWSER" "http://${TUTOR_URL}/"
"$BROWSER" "http://${TUTOR_URL}/students"
```

---

## Step 11 – View Cluster Resources

```bash
kubectl get deployments
kubectl get pods -o wide
kubectl get services
kubectl get nodes
kubectl describe deployment tutor
```

---

## Step 12 – Test Pod Scaling

```bash
# Scale tutor to 3 replicas
kubectl scale deployment tutor --replicas=3

sleep 20

kubectl get pods -l app=tutor

# Scale back to 2
kubectl scale deployment tutor --replicas=2
```

---

## Step 13 – View Logs

```bash
# Get first tutor pod name
POD_NAME=$(kubectl get pods -l app=tutor -o jsonpath='{.items[0].metadata.name}')
echo "POD_NAME=$POD_NAME"

kubectl logs "$POD_NAME" --tail=20
```

---

## Step 14 – Cleanup Resources (IMPORTANT!)

```bash
# Delete Kubernetes services (removes Load Balancer)
kubectl delete service tutor report

sleep 30

# Delete deployments
kubectl delete deployment tutor report

# Delete EKS cluster (this deletes everything)
echo "⚠️  Deleting EKS cluster - this will take 10-15 minutes..."

eksctl delete cluster \
  --name "$CLUSTER_NAME" \
  --region "$REGION" \
  --wait

# Delete ECR repositories
aws ecr delete-repository \
  --repository-name "$SERVICE1_NAME" \
  --force \
  --region "$REGION"

aws ecr delete-repository \
  --repository-name "$SERVICE2_NAME" \
  --force \
  --region "$REGION"

# Delete local files
rm -rf student-microservices
rm -f tutor-deployment.yaml report-deployment.yaml
rm -f tutor-service.yaml report-service.yaml
```

---

## Summary

In this lab, you have:
- Installed kubectl and eksctl for Kubernetes management
- Created Amazon EKS cluster with managed node group
- Built two microservice applications: Tutor (query service) and Report (data service)
- Pushed Docker images to ECR
- Created Kubernetes deployments with replicas
- Exposed tutor service with LoadBalancer, report service with ClusterIP
- Demonstrated inter-service communication (Tutor → Report)
- Tested student report endpoints (by ID and all students)
- Scaled deployments dynamically
- Viewed logs and cluster resources
- Cleaned up all resources to stop charges

**Key Takeaways:**
- **EKS**: Managed Kubernetes control plane on AWS
- **Managed Node Groups**: AWS handles node provisioning and updates
- **Microservices**: Independent, scalable services with service-to-service communication
- **Service Discovery**: Kubernetes DNS enables internal service communication (tutor calls report via http://report)
- **Service Types**: LoadBalancer (external access) vs ClusterIP (internal only)
- **Scaling**: Independent scaling per deployment

**Kubernetes Concepts:**
| Resource | Purpose |
|----------|---------||
| **Cluster** | Set of nodes running containers |
| **Node** | Worker machine (EC2 instance) |
| **Pod** | Smallest deployable unit (container wrapper) |
| **Deployment** | Manages pod replicas |
| **Service (ClusterIP)** | Internal service discovery (report service) |
| **Service (LoadBalancer)** | External access via AWS ELB (tutor service) |


**Best Practices:**
- Use managed node groups for easier management
- Set resource requests and limits on containers
- Implement liveness and readiness probes
- Use namespaces for environment separation
- Enable pod autoscaling (HPA) for production
- Use cluster autoscaling for nodes
- Implement network policies for security
- Use AWS Load Balancer Controller for ALB/NLB
- Monitor with CloudWatch Container Insights
- **DELETE clusters immediately after testing**

---

## Production Enhancements

For production EKS deployments:

1. **Cluster Autoscaling**
   ```bash
   # Install cluster autoscaler
   kubectl apply -f https://raw.githubusercontent.com/kubernetes/autoscaler/master/cluster-autoscaler/cloudprovider/aws/examples/cluster-autoscaler-autodiscover.yaml
   ```

2. **Horizontal Pod Autoscaling**
   ```bash
   kubectl autoscale deployment tutor --cpu-percent=50 --min=2 --max=10
   ```

3. **Ingress Controller**
   ```bash
   # Use AWS Load Balancer Controller for ALB
   kubectl apply -k "github.com/aws/eks-charts/stable/aws-load-balancer-controller//crds"
   ```

4. **Service Mesh (Istio/App Mesh)**
   - Traffic management
   - Security policies
   - Observability

5. **CI/CD Integration**
   - Build images in pipeline
   - Push to ECR
   - Update Kubernetes deployments
   - Rolling updates

6. **Monitoring and Logging**
   - CloudWatch Container Insights
   - Prometheus + Grafana
   - EFK stack (Elasticsearch, Fluentd, Kibana)

7. **Security**
   - Pod Security Standards
   - Network Policies
   - AWS IAM Roles for Service Accounts (IRSA)
   - Secrets Manager integration

8. **Multi-AZ High Availability**
   - Spread nodes across 3 AZs
   - Pod anti-affinity rules
   - Topology spread constraints
