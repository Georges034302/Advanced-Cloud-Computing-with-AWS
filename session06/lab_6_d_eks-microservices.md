# Lab 6.D: Deploy Microservices to Amazon EKS

## Overview
This lab demonstrates how to deploy containerized microservices to Amazon Elastic Kubernetes Service (EKS). You'll create an EKS cluster, build multiple simple joke API microservices, deploy them as Kubernetes pods, expose them via services, and test inter-service communication. This provides hands-on experience with Kubernetes orchestration on AWS.

**💰 Cost Warning**: ⚠️ **NOT FREE TIER** - EKS costs approximately:
- **EKS Control Plane**: $0.10/hour = **~$73/month**
- **Worker Nodes**: t3.small minimum = $0.023/hour × 2 = **~$34/month**
- **Total**: ~$107/month if running 24/7
- **This Lab** (~2-3 hours): **~$0.35**

**Cost Optimization**: Delete cluster immediately after completing the lab to minimize charges.

---

## Objectives
- Install and configure kubectl and eksctl
- Create EKS cluster with managed node group
- Build two simple microservice joke APIs
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
# Verify kubectl
kubectl version --client || { echo "❌ kubectl not installed"; exit 1; }

# Verify eksctl
eksctl version || { echo "❌ eksctl not installed"; exit 1; }

# Get AWS account ID
ACCOUNT_ID=$(aws sts get-caller-identity \
  --query Account \
  --output text)
echo "ACCOUNT_ID=$ACCOUNT_ID"

# Set region
REGION="ap-southeast-2"
echo "REGION=$REGION"

# Set cluster configuration
CLUSTER_NAME="joke-api-cluster"
echo "CLUSTER_NAME=$CLUSTER_NAME"

NODE_TYPE="t3.small"
echo "NODE_TYPE=$NODE_TYPE"

NODE_COUNT=2
echo "NODE_COUNT=$NODE_COUNT"

# Set microservice names
SERVICE1_NAME="dad-jokes"
echo "SERVICE1_NAME=$SERVICE1_NAME"

SERVICE2_NAME="tech-jokes"
echo "SERVICE2_NAME=$SERVICE2_NAME"

echo ""
echo "⚠️  COST WARNING:"
echo "   EKS Control Plane: $0.10/hour (~$73/month)"
echo "   Worker Nodes (2 × t3.small): $0.046/hour (~$34/month)"
echo "   Total: ~$0.15/hour"
echo ""
echo "   DELETE cluster immediately after lab!"
echo ""
echo "✅ Prerequisites verified"
```

---

## Step 2 – Create Dad Jokes Microservice

```bash
# Create project directory
mkdir -p joke-microservices
cd joke-microservices

# Create dad jokes microservice
mkdir -p dad-jokes
cd dad-jokes

cat > app.py <<'EOF'
from flask import Flask, jsonify
import random

app = Flask(__name__)

DAD_JOKES = [
    "Why don't scientists trust atoms? Because they make up everything!",
    "What do you call a fake noodle? An impasta!",
    "Why did the scarecrow win an award? He was outstanding in his field!",
    "What do you call a bear with no teeth? A gummy bear!",
    "Why don't eggs tell jokes? They'd crack each other up!",
    "What's the best thing about Switzerland? I don't know, but the flag is a big plus!"
]

@app.route('/')
def home():
    return jsonify({
        "service": "Dad Jokes API",
        "platform": "Amazon EKS",
        "endpoints": {
            "/": "This message",
            "/joke": "Get random dad joke",
            "/jokes": "Get all dad jokes"
        }
    })

@app.route('/joke')
def get_joke():
    return jsonify({
        "service": "dad-jokes",
        "joke": random.choice(DAD_JOKES)
    })

@app.route('/jokes')
def get_all():
    return jsonify({
        "service": "dad-jokes",
        "count": len(DAD_JOKES),
        "jokes": DAD_JOKES
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

echo "✅ Dad jokes microservice created"
cd ..
```

---

## Step 3 – Create Tech Jokes Microservice

```bash
# Create tech jokes microservice
mkdir -p tech-jokes
cd tech-jokes

cat > app.py <<'EOF'
from flask import Flask, jsonify
import random

app = Flask(__name__)

TECH_JOKES = [
    "Why do programmers prefer dark mode? Because light attracts bugs!",
    "Why do Java developers wear glasses? Because they don't C#!",
    "How many programmers does it take to change a light bulb? None, that's a hardware problem!",
    "Why did the developer go broke? Because he used up all his cache!",
    "What's a programmer's favorite hangout place? Foo Bar!",
    "Why do programmers hate nature? It has too many bugs!"
]

@app.route('/')
def home():
    return jsonify({
        "service": "Tech Jokes API",
        "platform": "Amazon EKS",
        "endpoints": {
            "/": "This message",
            "/joke": "Get random tech joke",
            "/jokes": "Get all tech jokes"
        }
    })

@app.route('/joke')
def get_joke():
    return jsonify({
        "service": "tech-jokes",
        "joke": random.choice(TECH_JOKES)
    })

@app.route('/jokes')
def get_all():
    return jsonify({
        "service": "tech-jokes",
        "count": len(TECH_JOKES),
        "jokes": TECH_JOKES
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

echo "✅ Tech jokes microservice created"
cd ..
```

---

## Step 4 – Create ECR Repositories

```bash
# Create ECR repository for dad-jokes
echo "Creating ECR repositories..."

aws ecr create-repository \
  --repository-name "$SERVICE1_NAME" \
  --region "$REGION"

aws ecr create-repository \
  --repository-name "$SERVICE2_NAME" \
  --region "$REGION"

# Get repository URIs
DAD_JOKES_REPO=$(aws ecr describe-repositories \
  --repository-names "$SERVICE1_NAME" \
  --query 'repositories[0].repositoryUri' \
  --output text \
  --region "$REGION")
echo "DAD_JOKES_REPO=$DAD_JOKES_REPO"

TECH_JOKES_REPO=$(aws ecr describe-repositories \
  --repository-names "$SERVICE2_NAME" \
  --query 'repositories[0].repositoryUri' \
  --output text \
  --region "$REGION")
echo "TECH_JOKES_REPO=$TECH_JOKES_REPO"

echo "✅ ECR repositories created"
```

---

## Step 5 – Build and Push Docker Images

```bash
# Authenticate Docker to ECR
echo "Authenticating Docker to ECR..."

aws ecr get-login-password \
  --region "$REGION" | docker login \
  --username AWS \
  --password-stdin "${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"

# Build and push dad-jokes image
echo "Building dad-jokes image..."
cd dad-jokes

docker build \
  --tag "${DAD_JOKES_REPO}:latest" \
  --platform linux/amd64 \
  .

docker push "${DAD_JOKES_REPO}:latest"

cd ..

# Build and push tech-jokes image
echo "Building tech-jokes image..."
cd tech-jokes

docker build \
  --tag "${TECH_JOKES_REPO}:latest" \
  --platform linux/amd64 \
  .

docker push "${TECH_JOKES_REPO}:latest"

cd ..

echo "✅ Docker images built and pushed to ECR"
```

---

## Step 6 – Create EKS Cluster

```bash
# Return to parent directory
cd ..

echo ""
echo "Creating EKS cluster..."
echo "⚠️  This will take 15-20 minutes!"
echo "💰 EKS control plane charges start now ($0.10/hour)"
echo ""

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

echo ""
echo "✅ EKS cluster created"
echo "💰 Cluster is now running and incurring charges"
```

---

## Step 7 – Verify Cluster and Nodes

```bash
# Verify kubectl context
echo "Verifying kubectl configuration..."

kubectl config current-context

# Get nodes
echo ""
echo "Cluster Nodes:"
kubectl get nodes \
  -o wide

# Get cluster info
echo ""
echo "Cluster Info:"
kubectl cluster-info

echo ""
echo "✅ Cluster is ready"
```

---

## Step 8 – Create Kubernetes Deployments

```bash
# Create deployment for dad-jokes
cat > dad-jokes-deployment.yaml <<EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: dad-jokes
  labels:
    app: dad-jokes
spec:
  replicas: 2
  selector:
    matchLabels:
      app: dad-jokes
  template:
    metadata:
      labels:
        app: dad-jokes
    spec:
      containers:
      - name: dad-jokes
        image: ${DAD_JOKES_REPO}:latest
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

# Create deployment for tech-jokes
cat > tech-jokes-deployment.yaml <<EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: tech-jokes
  labels:
    app: tech-jokes
spec:
  replicas: 2
  selector:
    matchLabels:
      app: tech-jokes
  template:
    metadata:
      labels:
        app: tech-jokes
    spec:
      containers:
      - name: tech-jokes
        image: ${TECH_JOKES_REPO}:latest
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
echo "Deploying microservices to EKS..."

kubectl apply -f dad-jokes-deployment.yaml
kubectl apply -f tech-jokes-deployment.yaml

echo "Waiting for deployments to be ready..."
sleep 30

echo ""
echo "✅ Deployments created"
```

---

## Step 9 – Create Kubernetes Services

```bash
# Create service for dad-jokes (LoadBalancer type)
cat > dad-jokes-service.yaml <<'EOF'
apiVersion: v1
kind: Service
metadata:
  name: dad-jokes
spec:
  type: LoadBalancer
  selector:
    app: dad-jokes
  ports:
  - port: 80
    targetPort: 80
    protocol: TCP
EOF

# Create service for tech-jokes (LoadBalancer type)
cat > tech-jokes-service.yaml <<'EOF'
apiVersion: v1
kind: Service
metadata:
  name: tech-jokes
spec:
  type: LoadBalancer
  selector:
    app: tech-jokes
  ports:
  - port: 80
    targetPort: 80
    protocol: TCP
EOF

# Apply services
echo "Creating Kubernetes services..."

kubectl apply -f dad-jokes-service.yaml
kubectl apply -f tech-jokes-service.yaml

echo "Waiting for LoadBalancers to provision (this takes 2-3 minutes)..."
sleep 180

echo "✅ Services created"
```

---

## Step 10 – Get Service URLs and Test

```bash
# Get dad-jokes service URL
echo ""
echo "Getting service endpoints..."

DAD_JOKES_URL=$(kubectl get service dad-jokes \
  -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')
echo "DAD_JOKES_URL=$DAD_JOKES_URL"

TECH_JOKES_URL=$(kubectl get service tech-jokes \
  -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')
echo "TECH_JOKES_URL=$TECH_JOKES_URL"

echo ""
echo "================================================"
echo "MICROSERVICES DEPLOYED TO EKS"
echo "================================================"
echo ""
echo "Dad Jokes API: http://${DAD_JOKES_URL}"
echo "Tech Jokes API: http://${TECH_JOKES_URL}"
echo ""
echo "Testing microservices..."
echo ""

# Test dad-jokes service
echo "1. Testing Dad Jokes API:"
curl -s "http://${DAD_JOKES_URL}/" | python3 -m json.tool
echo ""

echo "Random dad joke:"
curl -s "http://${DAD_JOKES_URL}/joke" | python3 -m json.tool
echo ""

# Test tech-jokes service
echo "2. Testing Tech Jokes API:"
curl -s "http://${TECH_JOKES_URL}/" | python3 -m json.tool
echo ""

echo "Random tech joke:"
curl -s "http://${TECH_JOKES_URL}/joke" | python3 -m json.tool
echo ""

echo "================================================"
echo "✅ All microservices working!"
echo ""
echo "Try in browser:"
echo "  http://${DAD_JOKES_URL}/"
echo "  http://${DAD_JOKES_URL}/joke"
echo "  http://${TECH_JOKES_URL}/"
echo "  http://${TECH_JOKES_URL}/joke"
```

---

## Step 11 – View Cluster Resources

```bash
echo ""
echo "Kubernetes Resources:"
echo ""

echo "Deployments:"
kubectl get deployments

echo ""
echo "Pods:"
kubectl get pods \
  -o wide

echo ""
echo "Services:"
kubectl get services

echo ""
echo "Nodes:"
kubectl get nodes

echo ""
echo "Pod Details (Dad Jokes):"
kubectl describe deployment dad-jokes
```

---

## Step 12 – Test Pod Scaling

```bash
echo ""
echo "Testing pod scaling..."

# Scale dad-jokes to 3 replicas
kubectl scale deployment dad-jokes --replicas=3

echo "Waiting for new pod to start..."
sleep 20

echo ""
echo "Updated Pods:"
kubectl get pods \
  -l app=dad-jokes

echo ""
echo "✅ Scaling works! Pods can be scaled independently"

# Scale back to 2
kubectl scale deployment dad-jokes --replicas=2
```

---

## Step 13 – View Logs

```bash
echo ""
echo "Viewing pod logs..."

# Get first dad-jokes pod name
POD_NAME=$(kubectl get pods \
  -l app=dad-jokes \
  -o jsonpath='{.items[0].metadata.name}')
echo "POD_NAME=$POD_NAME"

echo ""
echo "Logs from $POD_NAME:"
kubectl logs "$POD_NAME" --tail=20
```

---

## Step 14 – Cleanup Resources (IMPORTANT!)

```bash
echo ""
echo "⚠️  CLEANUP - Stopping charges immediately..."
echo ""

# Delete Kubernetes services (removes Load Balancers)
echo "Deleting Kubernetes services..."
kubectl delete service dad-jokes tech-jokes

echo "Waiting for Load Balancers to be deleted..."
sleep 30

# Delete deployments
echo "Deleting deployments..."
kubectl delete deployment dad-jokes tech-jokes

# Delete EKS cluster (this deletes everything)
echo "Deleting EKS cluster..."
echo "⚠️  This will take 10-15 minutes..."

eksctl delete cluster \
  --name "$CLUSTER_NAME" \
  --region "$REGION" \
  --wait

echo "✅ EKS cluster deleted"

# Delete ECR repositories
echo "Deleting ECR repositories..."
aws ecr delete-repository \
  --repository-name "$SERVICE1_NAME" \
  --force \
  --region "$REGION"

aws ecr delete-repository \
  --repository-name "$SERVICE2_NAME" \
  --force \
  --region "$REGION"

# Delete local files
echo "Cleaning up local files..."
rm -rf joke-microservices
rm -f dad-jokes-deployment.yaml tech-jokes-deployment.yaml
rm -f dad-jokes-service.yaml tech-jokes-service.yaml

echo ""
echo "✅ Cleanup completed successfully!"
echo ""
echo "All resources deleted:"
echo "- EKS cluster (control plane charges stopped)"
echo "- Worker nodes (t3.small charges stopped)"
echo "- Load Balancers"
echo "- Deployments and pods"
echo "- ECR repositories and images"
echo "- Local files"
echo ""
echo "💰 All EKS charges stopped!"
```

---

## Summary

In this lab, you have:
- Installed kubectl and eksctl for Kubernetes management
- Created Amazon EKS cluster with managed node group
- Built two microservice applications (dad-jokes and tech-jokes)
- Pushed Docker images to ECR
- Created Kubernetes deployments with replicas
- Exposed microservices with LoadBalancer services
- Tested microservice endpoints
- Scaled deployments dynamically
- Viewed logs and cluster resources
- Cleaned up all resources to stop charges

**Key Takeaways:**
- **EKS**: Managed Kubernetes control plane on AWS
- **Managed Node Groups**: AWS handles node provisioning and updates
- **Microservices**: Independent, scalable services
- **Service Discovery**: Kubernetes DNS for inter-service communication
- **Load Balancing**: Automatic with LoadBalancer service type
- **Scaling**: Independent scaling per deployment

**Kubernetes Concepts:**
| Resource | Purpose |
|----------|---------|
| **Cluster** | Set of nodes running containers |
| **Node** | Worker machine (EC2 instance) |
| **Pod** | Smallest deployable unit (container wrapper) |
| **Deployment** | Manages pod replicas |
| **Service** | Exposes pods to network |
| **LoadBalancer** | Provisions AWS ELB for external access |

**EKS Pricing:**
- **Control Plane**: $0.10/hour = $73/month (per cluster)
- **Worker Nodes**: EC2 instance pricing (t3.small = $0.023/hour)
- **Load Balancers**: Classic LB or ALB pricing
- **Data Transfer**: Standard AWS rates

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

## Cost Breakdown

**This Lab Costs (assuming 3-hour runtime):**
- EKS control plane: $0.10/hour × 3 = **$0.30**
- Worker nodes (2 × t3.small): $0.046/hour × 3 = **$0.14**
- Load Balancers (2 × CLB): $0.05/hour × 3 = **$0.15**
- **Total lab cost: ~$0.60**

**If left running 24/7:**
- EKS control plane: $0.10/hour × 730 = **$73/month**
- Worker nodes: $0.046/hour × 730 = **$34/month**
- Load Balancers: $0.05/hour × 730 = **$36/month**
- **Total: ~$143/month**

**⚠️ CRITICAL: Always delete EKS clusters after testing!**

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
   kubectl autoscale deployment dad-jokes --cpu-percent=50 --min=2 --max=10
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
