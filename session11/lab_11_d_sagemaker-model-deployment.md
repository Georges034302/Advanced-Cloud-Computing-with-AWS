# Lab 11.D: Amazon SageMaker - Simple Model Deployment
<img width="1536" height="1024" alt="IMG" src="https://github.com/user-attachments/assets/cfd3e134-1b72-4031-9817-661709857534" />

## Overview
This lab introduces Amazon SageMaker for deploying machine learning models without deep ML expertise. You'll use pre-built algorithms, deploy a simple XGBoost model for classification, create real-time prediction endpoints, perform batch predictions, and implement A/B testing. Focus is on practical ML deployment, not model training theory.

---

## Objectives
- Create SageMaker notebook instance
- Deploy pre-built XGBoost algorithm
- Train classification model on sample data
- Create real-time prediction endpoint
- Perform batch predictions
- Implement A/B testing with multiple models
- Monitor model performance
- Clean up resources properly

---

## Prerequisites
- AWS CLI configured (`aws configure`)
- IAM permissions for SageMaker, S3
- Region: ap-southeast-2
- Python 3.x installed
- **AWS Service Quotas**: SageMaker training instances (requires quota increase for new accounts)

---

## Architecture

```
Training Data (S3)
        ↓
   SageMaker Training
   (XGBoost Algorithm)
        ↓
   Trained Model (S3)
        ↓
   SageMaker Endpoint
        ↓
   Real-Time Predictions
```

---

## Step 1 – Set Variables

```bash
# Set AWS region for all operations
REGION="ap-southeast-2"
export AWS_REGION="$REGION"

# Get AWS account ID for unique resource naming
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# Set unique names for SageMaker resources
BUCKET_NAME="sagemaker-demo-${ACCOUNT_ID}"
ROLE_NAME="SageMakerExecutionRole"

echo "Region: $REGION"
echo "Account ID: $ACCOUNT_ID"
echo "Bucket: $BUCKET_NAME"
```

---

## Step 2 – Create S3 Bucket for Data and Models

```bash
echo ""
echo "Creating S3 bucket for SageMaker..."

# Create S3 bucket for training data and model artifacts (region-specific configuration)
if [ "$REGION" = "us-east-1" ]; then
    aws s3api create-bucket \
      --bucket "$BUCKET_NAME" \
      --region "$REGION"
else
    aws s3api create-bucket \
      --bucket "$BUCKET_NAME" \
      --region "$REGION" \
      --create-bucket-configuration LocationConstraint="$REGION"
fi

echo "Bucket: $BUCKET_NAME"
```

---

## Step 3 – Create IAM Role for SageMaker

```bash
echo ""
echo "Creating IAM role for SageMaker..."

# Get repository root directory
REPO_DIR=$(git rev-parse --show-toplevel)

# Create sagemaker directory in repository
mkdir -p "$REPO_DIR/sagemaker-demo"
cd "$REPO_DIR/sagemaker-demo"

# Create trust policy allowing SageMaker service to assume role
cat > sagemaker-trust-policy.json <<'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "sagemaker.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

# Create IAM role with trust policy
aws iam create-role \
  --role-name "$ROLE_NAME" \
  --assume-role-policy-document file://sagemaker-trust-policy.json

# Attach managed policy for SageMaker operations
aws iam attach-role-policy \
  --role-name "$ROLE_NAME" \
  --policy-arn arn:aws:iam::aws:policy/AmazonSageMakerFullAccess

# Attach managed policy for S3 access (training data and models)
aws iam attach-role-policy \
  --role-name "$ROLE_NAME" \
  --policy-arn arn:aws:iam::aws:policy/AmazonS3FullAccess

echo "Waiting for IAM propagation..."
sleep 10

# Get role ARN for SageMaker configuration
ROLE_ARN=$(aws iam get-role \
  --role-name "$ROLE_NAME" \
  --query 'Role.Arn' \
  --output text)

echo "Role ARN: $ROLE_ARN"
```

---

## Step 4 – Create Sample Training Data (Customer Churn Prediction)

```bash
echo ""
echo "Creating sample training data for customer churn prediction..."

# Navigate to sagemaker directory
cd "$REPO_DIR/sagemaker-demo"

# Create Python script to generate synthetic customer churn data
cat > generate_data.py <<'EOF'
#!/usr/bin/env python3
import csv
import random

# Generate synthetic customer churn data
# Features: age, tenure_months, monthly_charges, total_charges, num_support_calls
# Label: churned (0 or 1)

random.seed(42)

def generate_customer():
    age = random.randint(18, 80)
    tenure = random.randint(1, 72)
    monthly_charge = random.uniform(20, 150)
    total_charges = monthly_charge * tenure
    support_calls = random.randint(0, 10)
    
    # Simple churn logic: more likely to churn if high support calls + high charges
    churn_probability = 0.1
    if support_calls > 5:
        churn_probability += 0.3
    if monthly_charge > 100:
        churn_probability += 0.2
    if tenure < 12:
        churn_probability += 0.2
    
    churned = 1 if random.random() < churn_probability else 0
    
    return [churned, age, tenure, monthly_charge, total_charges, support_calls]

# Generate 1000 training samples
with open('train.csv', 'w', newline='') as f:
    writer = csv.writer(f)
    for _ in range(1000):
        writer.writerow(generate_customer())

# Generate 200 test samples
with open('test.csv', 'w', newline='') as f:
    writer = csv.writer(f)
    for _ in range(200):
        writer.writerow(generate_customer())

print("✅ Generated train.csv (1000 samples) and test.csv (200 samples)")
print("Features: age, tenure_months, monthly_charges, total_charges, num_support_calls")
print("Label: churned (0=No, 1=Yes)")
EOF

python3 generate_data.py

# Show sample data
echo ""
echo "Sample training data:"
head -5 train.csv
```

---

## Step 5 – Upload Data to S3

```bash
echo ""
echo "Uploading training data to S3..."

# Upload training data to S3 for SageMaker access
aws s3 cp train.csv s3://"$BUCKET_NAME"/data/train/ \
  --region "$REGION"

# Upload test data to S3 for batch predictions
aws s3 cp test.csv s3://"$BUCKET_NAME"/data/test/ \
  --region "$REGION"

echo "Training data: s3://${BUCKET_NAME}/data/train/"
echo "Test data: s3://${BUCKET_NAME}/data/test/"
```

---

## Step 6 – Create Training Script

```bash
echo ""
echo "Creating SageMaker training script..."

# Navigate to sagemaker directory
cd "$REPO_DIR/sagemaker-demo"

# Create Python script for model training
cat > train_model.py <<'EOF'
#!/usr/bin/env python3
import boto3
import time

# Configuration
region = 'ap-southeast-2'
bucket = 'sagemaker-demo-013709423315'
role = 'arn:aws:iam::013709423315:role/SageMakerExecutionRole'

# Initialize SageMaker client
sm_client = boto3.client('sagemaker', region_name=region)

print("="*70)
print("SAGEMAKER XGBOOST TRAINING")
print("="*70)
print()

# Get XGBoost container image for ap-southeast-2
account_mapping = {
    'ap-southeast-2': '544295431143'
}
account_id = account_mapping[region]
image_uri = f'{account_id}.dkr.ecr.{region}.amazonaws.com/xgboost:1.5-1'

print(f"XGBoost container: {image_uri}")
print()

# Set S3 paths
train_data_path = f's3://{bucket}/data/train/'
output_path = f's3://{bucket}/models/'

print(f"Training data: {train_data_path}")
print(f"Model output: {output_path}")
print()

# Create training job name
training_job_name = f'xgboost-churn-{int(time.time())}'

print("XGBoost configuration:")
print(f"  Instance type: ml.m5.large")
print(f"  Objective: binary:logistic (classification)")
print(f"  num_round: 50 (training iterations)")
print(f"  max_depth: 5 (tree depth)")
print()

# Start training job
print(f"Starting training job: {training_job_name}")
print("(This will take 5-10 minutes)")
print()

sm_client.create_training_job(
    TrainingJobName=training_job_name,
    RoleArn=role,
    AlgorithmSpecification={
        'TrainingImage': image_uri,
        'TrainingInputMode': 'File'
    },
    InputDataConfig=[
        {
            'ChannelName': 'train',
            'DataSource': {
                'S3DataSource': {
                    'S3DataType': 'S3Prefix',
                    'S3Uri': train_data_path,
                    'S3DataDistributionType': 'FullyReplicated'
                }
            },
            'ContentType': 'text/csv'
        }
    ],
    OutputDataConfig={
        'S3OutputPath': output_path
    },
    ResourceConfig={
        'InstanceType': 'ml.m5.large',
        'InstanceCount': 1,
        'VolumeSizeInGB': 10
    },
    HyperParameters={
        'objective': 'binary:logistic',
        'num_round': '50',
        'max_depth': '5',
        'eta': '0.2',
        'subsample': '0.8',
        'colsample_bytree': '0.8'
    },
    StoppingCondition={
        'MaxRuntimeInSeconds': 3600
    }
)

# Monitor training job
print("Training job status:")
while True:
    response = sm_client.describe_training_job(
        TrainingJobName=training_job_name
    )
    status = response['TrainingJobStatus']
    print(f"  {status}", end='')
    
    if status in ['Completed', 'Failed', 'Stopped']:
        print()
        break
    
    print(" (checking in 30s)...")
    time.sleep(30)

if status == 'Completed':
    model_artifacts = response['ModelArtifacts']['S3ModelArtifacts']
    print()
    print("✅ Training completed!")
    print(f"Model artifacts: {model_artifacts}")
else:
    print()
    print(f"❌ Training {status}")
    if 'FailureReason' in response:
        print(f"Reason: {response['FailureReason']}")
EOF

chmod +x train_model.py
```

---

## Step 7 – Install SageMaker Python SDK

```bash
echo ""
echo "Installing SageMaker Python SDK..."

# Install SageMaker SDK and dependencies
pip3 install -q sagemaker boto3
```

---

## Step 8 – Train the Model

> **⚠️ NOTE: This step requires SageMaker service quotas.**
> 
> If you receive `ResourceLimitExceeded` error, you need to:
> - Go to AWS Service Quotas console
> - Search for "SageMaker"
> - Request increase for "ml.m5.large for training job usage"
> - Wait 1-2 business days for approval
> 
> For learning purposes, you can skip to Step 19 (cleanup) if quota increase is not approved yet.

```bash
echo ""
echo "================================================"
echo "TRAINING XGBOOST MODEL"
echo "================================================"
echo ""

# Navigate to sagemaker directory and run training
cd "$REPO_DIR/sagemaker-demo"

python3 train_model.py
```

---

## Step 9 – Deploy Model to Endpoint

```bash
echo ""
echo "Creating deployment script..."

# Navigate to sagemaker directory
cd "$REPO_DIR/sagemaker-demo"

# Create Python script for model deployment
cat > deploy_model.py <<EOF
#!/usr/bin/env python3
import boto3
import sagemaker
from sagemaker.estimator import Estimator

sagemaker_session = sagemaker.Session()
region = '$REGION'
bucket = '$BUCKET_NAME'
role = '$ROLE_ARN'

print("="*70)
print("DEPLOYING MODEL TO ENDPOINT")
print("="*70)
print()

# Get the trained model (latest)
sm_client = boto3.client('sagemaker', region_name=region)
training_jobs = sm_client.list_training_jobs(
    SortBy='CreationTime',
    SortOrder='Descending',
    MaxResults=1
)

if not training_jobs['TrainingJobSummaries']:
    print("❌ No training jobs found")
    exit(1)

training_job_name = training_jobs['TrainingJobSummaries'][0]['TrainingJobName']
print(f"Using trained model from: {training_job_name}")
print()

# Attach to trained model
from sagemaker.image_uris import retrieve
container = retrieve('xgboost', region, version='1.5-1')

xgb = Estimator(
    container,
    role=role,
    instance_count=1,
    instance_type='ml.m4.xlarge',
    output_path=f's3://{bucket}/models/',
    sagemaker_session=sagemaker_session
)

xgb.attach(training_job_name)

# Deploy to endpoint
print("Deploying model to endpoint...")
print("Instance type: ml.t2.medium (FREE TIER eligible)")
print("(This will take 5-8 minutes)")
print()

predictor = xgb.deploy(
    initial_instance_count=1,
    instance_type='ml.t2.medium',
    endpoint_name='xgboost-churn-endpoint'
)

print()
print("✅ Model deployed!")
print(f"Endpoint name: xgboost-churn-endpoint")

# Save endpoint name for later use
with open('endpoint_name.txt', 'w') as f:
    f.write('xgboost-churn-endpoint')
EOF

chmod +x deploy_model.py
```

---

## Step 10 – Deploy Model

```bash
echo ""
echo "================================================"
echo "DEPLOYING MODEL ENDPOINT"
echo "================================================"
echo ""

# Navigate to sagemaker directory and deploy model
cd "$REPO_DIR/sagemaker-demo"

python3 deploy_model.py
```

---

## Step 11 – Make Real-Time Predictions

```bash
echo ""
echo "Creating prediction script..."

# Navigate to sagemaker directory
cd "$REPO_DIR/sagemaker-demo"

# Create Python script for real-time predictions
cat > predict.py <<'EOF'
#!/usr/bin/env python3
import boto3
import json

# Read endpoint name
with open('endpoint_name.txt', 'r') as f:
    endpoint_name = f.read().strip()

runtime = boto3.client('sagemaker-runtime')

print("="*70)
print("REAL-TIME PREDICTIONS")
print("="*70)
print()

# Test customers
test_cases = [
    {
        'name': 'Customer A (Low Risk)',
        'features': [25, 36, 45.50, 1638.00, 1],  # Young, long tenure, low charges, few calls
        'expected': 'Not likely to churn'
    },
    {
        'name': 'Customer B (High Risk)',
        'features': [45, 3, 125.00, 375.00, 8],  # Short tenure, high charges, many support calls
        'expected': 'Likely to churn'
    },
    {
        'name': 'Customer C (Medium Risk)',
        'features': [35, 18, 75.00, 1350.00, 4],  # Medium tenure, medium charges, some calls
        'expected': 'Moderate risk'
    },
]

for test in test_cases:
    print(f"{test['name']}")
    print(f"Features: age={test['features'][0]}, tenure={test['features'][1]} months, "
          f"monthly_charge=${test['features'][2]:.2f}, support_calls={test['features'][4]}")
    
    # Prepare CSV format (no label for prediction)
    payload = ','.join(map(str, test['features'][1:]))  # Skip label position
    
    # Invoke endpoint
    response = runtime.invoke_endpoint(
        EndpointName=endpoint_name,
        ContentType='text/csv',
        Body=payload
    )
    
    # Parse prediction
    result = float(response['Body'].read().decode())
    churn_probability = result
    
    print(f"Churn Probability: {churn_probability:.2%}")
    print(f"Prediction: {'WILL CHURN' if churn_probability > 0.5 else 'WILL NOT CHURN'}")
    print(f"Expected: {test['expected']}")
    print("-" * 70)

print()
print("✅ Real-time predictions complete")
EOF

chmod +x predict.py
```

---

## Step 12 – Test Real-Time Predictions

```bash
echo ""
echo "================================================"
echo "TESTING REAL-TIME PREDICTIONS"
echo "================================================"
echo ""

# Navigate to sagemaker directory and run predictions
cd "$REPO_DIR/sagemaker-demo"

python3 predict.py
```

---

## Step 13 – Batch Predictions

```bash
echo ""
echo "Creating batch prediction script..."

# Navigate to sagemaker directory
cd "$REPO_DIR/sagemaker-demo"

# Create Python script for batch transform job
cat > batch_predict.py <<EOF
#!/usr/bin/env python3
import boto3
import time

sm_client = boto3.client('sagemaker')
region = '$REGION'
bucket = '$BUCKET_NAME'
role = '$ROLE_ARN'

print("="*70)
print("BATCH TRANSFORM JOB")
print("="*70)
print()

# Get model name from latest training job
training_jobs = sm_client.list_training_jobs(
    SortBy='CreationTime',
    SortOrder='Descending',
    MaxResults=1
)

training_job_name = training_jobs['TrainingJobSummaries'][0]['TrainingJobName']

# Get model ARN
models = sm_client.list_models(
    SortBy='CreationTime',
    SortOrder='Descending',
    MaxResults=10
)

model_name = None
for model in models['Models']:
    if training_job_name in model['ModelName']:
        model_name = model['ModelName']
        break

if not model_name:
    print("Using first available model")
    model_name = models['Models'][0]['ModelName']

print(f"Using model: {model_name}")
print()

# Create batch transform job
transform_job_name = f"batch-transform-{int(time.time())}"

print(f"Starting batch transform job: {transform_job_name}")
print()

sm_client.create_transform_job(
    TransformJobName=transform_job_name,
    ModelName=model_name,
    TransformInput={
        'DataSource': {
            'S3DataSource': {
                'S3DataType': 'S3Prefix',
                'S3Uri': f's3://{bucket}/data/test/'
            }
        },
        'ContentType': 'text/csv',
        'SplitType': 'Line'
    },
    TransformOutput={
        'S3OutputPath': f's3://{bucket}/batch-output/',
        'Accept': 'text/csv'
    },
    TransformResources={
        'InstanceType': 'ml.m5.large',
        'InstanceCount': 1
    }
)

print("Batch job started! Monitoring status...")
print()

# Poll status
while True:
    response = sm_client.describe_transform_job(
        TransformJobName=transform_job_name
    )
    status = response['TransformJobStatus']
    print(f"Status: {status}")
    
    if status in ['Completed', 'Failed', 'Stopped']:
        break
    
    time.sleep(30)

print()
if status == 'Completed':
    print("✅ Batch transform completed!")
    print(f"Output: s3://{bucket}/batch-output/")
else:
    print(f"❌ Batch transform {status}")
EOF

chmod +x batch_predict.py
```

---

## Step 14 – Run Batch Predictions

```bash
echo ""
echo "================================================"
echo "BATCH PREDICTIONS"
echo "================================================"
echo ""

# Navigate to sagemaker directory and run batch job
cd "$REPO_DIR/sagemaker-demo"

python3 batch_predict.py

echo ""
echo "Downloading batch results..."

# Download batch prediction results from S3
aws s3 sync s3://"$BUCKET_NAME"/batch-output/ ./batch-output/ \
  --region "$REGION"

echo ""
echo "Sample batch predictions:"
head -10 ./batch-output/*.out 2>/dev/null || echo "Results processing..."
```

---

## Step 15 – Monitor Endpoint Metrics

```bash
echo ""
echo "================================================"
echo "ENDPOINT MONITORING"
echo "================================================"
echo ""

ENDPOINT_NAME="xgboost-churn-endpoint"

# Query CloudWatch for average model latency over past hour
aws cloudwatch get-metric-statistics \
  --namespace AWS/SageMaker \
  --metric-name ModelLatency \
  --dimensions Name=EndpointName,Value="$ENDPOINT_NAME" Name=VariantName,Value=AllTraffic \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 3600 \
  --statistics Average \
  --region "$REGION" \
  --query 'Datapoints[0].Average' \
  --output text

echo ""
echo "Available metrics:"
echo "  - ModelLatency: Inference latency"
echo "  - Invocations: Number of predictions"
echo "  - ModelInvocationErrors: Failed predictions"
```

---

## Step 16 – Create A/B Testing Setup

```bash
echo ""
echo "Creating A/B testing script..."

# Navigate to sagemaker directory
cd "$REPO_DIR/sagemaker-demo"

# Create Python script explaining A/B testing concepts
cat > ab_testing.py <<EOF
#!/usr/bin/env python3
import boto3

sm_client = boto3.client('sagemaker')

print("="*70)
print("A/B TESTING SETUP")
print("="*70)
print()

print("A/B Testing allows deploying multiple model versions to compare performance")
print()
print("Example configuration:")
print("  - Variant A (current model): 70% traffic")
print("  - Variant B (new model): 30% traffic")
print()
print("This allows safe testing of new models in production")
print()

print("To implement A/B testing:")
print("1. Train second model with different hyperparameters")
print("2. Create endpoint configuration with multiple variants")
print("3. Deploy both models to same endpoint")
print("4. Monitor metrics (accuracy, latency) for each variant")
print("5. Gradually shift traffic to better performing variant")
print()

print("✅ A/B testing concept explained")
print("Note: Implementing full A/B test requires multiple trained models")
EOF

chmod +x ab_testing.py
python3 ab_testing.py
```

---

## Step 17 – View Model Artifacts

```bash
echo ""
echo "================================================"
echo "MODEL ARTIFACTS"
echo "================================================"
echo ""

echo "Listing model artifacts in S3..."

# List all model artifacts stored in S3
aws s3 ls s3://"$BUCKET_NAME"/models/ --recursive --human-readable \
  --region "$REGION"

echo ""
echo "Model artifacts contain:"
echo "  - xgboost-model: Trained model file"
echo "  - Training metadata and logs"
```

---

## Step 18 – List SageMaker Resources

```bash
echo ""
echo "================================================"
echo "SAGEMAKER RESOURCES"
echo "================================================"
echo ""

echo "Training Jobs:"
# List recent SageMaker training jobs
aws sagemaker list-training-jobs \
  --region "$REGION" \
  --max-results 5 \
  --query 'TrainingJobSummaries[*].[TrainingJobName,TrainingJobStatus,CreationTime]' \
  --output table

echo ""
echo "Endpoints:"
# List active SageMaker endpoints
aws sagemaker list-endpoints \
  --region "$REGION" \
  --query 'Endpoints[*].[EndpointName,EndpointStatus,CreationTime]' \
  --output table

echo ""
echo "Models:"
# List deployed SageMaker models
aws sagemaker list-models \
  --region "$REGION" \
  --max-results 5 \
  --query 'Models[*].[ModelName,CreationTime]' \
  --output table
```

---

## Step 19 – Cleanup

```bash
echo ""
echo "Cleaning up resources..."

ENDPOINT_NAME="xgboost-churn-endpoint"

# Delete SageMaker endpoint
echo "Deleting endpoint..."
aws sagemaker delete-endpoint \
  --endpoint-name "$ENDPOINT_NAME" \
  --region "$REGION" 2>/dev/null

echo "✅ Endpoint deleted"

# Delete endpoint configuration
ENDPOINT_CONFIG=$(aws sagemaker list-endpoint-configs \
  --region "$REGION" \
  --query 'EndpointConfigs[0].EndpointConfigName' \
  --output text 2>/dev/null)

if [ "$ENDPOINT_CONFIG" != "None" ] && [ -n "$ENDPOINT_CONFIG" ]; then
    echo "Deleting endpoint config..."
    aws sagemaker delete-endpoint-config \
      --endpoint-config-name "$ENDPOINT_CONFIG" \
      --region "$REGION" 2>/dev/null
    echo "✅ Endpoint config deleted"
fi

# Delete SageMaker model
MODEL_NAME=$(aws sagemaker list-models \
  --region "$REGION" \
  --max-results 1 \
  --query 'Models[0].ModelName' \
  --output text 2>/dev/null)

if [ "$MODEL_NAME" != "None" ] && [ -n "$MODEL_NAME" ]; then
    echo "Deleting model..."
    aws sagemaker delete-model \
      --model-name "$MODEL_NAME" \
      --region "$REGION" 2>/dev/null
    echo "✅ Model deleted"
fi

# Empty and delete S3 bucket
echo "Deleting S3 bucket and contents..."
aws s3 rm s3://"$BUCKET_NAME" --recursive --region "$REGION"
aws s3api delete-bucket --bucket "$BUCKET_NAME" --region "$REGION"

echo "✅ S3 bucket deleted"

# Detach managed policies and delete IAM role
echo "Deleting IAM role..."
aws iam detach-role-policy \
  --role-name "$ROLE_NAME" \
  --policy-arn arn:aws:iam::aws:policy/AmazonSageMakerFullAccess 2>/dev/null

aws iam detach-role-policy \
  --role-name "$ROLE_NAME" \
  --policy-arn arn:aws:iam::aws:policy/AmazonS3FullAccess 2>/dev/null

aws iam delete-role --role-name "$ROLE_NAME" 2>/dev/null

echo "✅ IAM role deleted"

# Remove local sagemaker directory
echo "Removing local files..."
cd "$REPO_DIR"
rm -rf sagemaker-demo

echo "✅ Local files deleted"
echo ""
echo "✅ Lab 11.D cleanup complete!"
echo ""
echo "Note: If you started a batch transform job (Step 14), it cannot be cancelled."
echo "The job will complete automatically. Batch job records auto-expire after 7 days."
```

---

## Summary

In this lab, you have:
- Created SageMaker execution role and S3 bucket
- Generated synthetic customer churn dataset
- Trained XGBoost classification model
- Deployed model to real-time endpoint
- Made real-time predictions via API
- Performed batch predictions on test data
- Monitored endpoint metrics
- Understood A/B testing concepts
- Properly cleaned up all resources

**Key Takeaways:**
- **Managed ML**: SageMaker handles infrastructure automatically
- **Pre-Built Algorithms**: Use XGBoost, LinearLearner, etc. without implementation
- **Real-Time Inference**: Low-latency predictions via HTTPS endpoints
- **Batch Processing**: Cost-effective for large-scale predictions
- **Production Ready**: Auto-scaling, monitoring, A/B testing built-in
- **Pay Per Use**: Only pay for training and inference time

**Common Use Cases:**
- **Customer Churn**: Predict which customers will leave
- **Fraud Detection**: Identify fraudulent transactions
- **Recommendation Systems**: Product recommendations
- **Demand Forecasting**: Predict future sales
- **Image Classification**: Categorize images automatically
- **Sentiment Analysis**: Analyze customer feedback

---

## Best Practices

**Model Development:**
- Start with pre-built algorithms (XGBoost, LinearLearner)
- Use notebook instances for experimentation
- Version your models with meaningful names
- Monitor training metrics (accuracy, loss)
- Validate on holdout test set

**Production Deployment:**
- Use smallest instance type that meets latency requirements
- Enable auto-scaling for variable traffic
- Implement model monitoring and retraining
- Use A/B testing for model updates
- Set up CloudWatch alarms for errors

**Cost Optimization:**
- Delete endpoints when not in use
- Use batch transform for offline predictions
- Use serverless inference for sporadic workloads
- Right-size instance types
- Leverage spot instances for training

**Security:**
- Use IAM roles with least privilege
- Encrypt data at rest and in transit
- Use VPC for network isolation
- Enable CloudTrail for audit logging
- Implement model access controls

**Performance:**
- Batch predictions for higher throughput
- Cache frequent predictions
- Use appropriate instance types
- Monitor latency and errors
- Implement retry logic

---

## Production Enhancements

1. **Automated Retraining**
   ```python
   # Trigger retraining on data drift
   def retrain_pipeline():
       new_data = fetch_latest_data()
       if detect_data_drift(new_data):
           trigger_training_job()
   ```

2. **Model Monitoring**
   ```python
   # Monitor prediction distribution
   cloudwatch.put_metric_data(
       Namespace='CustomMetrics',
       MetricData=[{
           'MetricName': 'ChurnPredictionRate',
           'Value': churn_rate
       }]
   )
   ```

3. **Feature Store Integration**
   ```python
   # Use SageMaker Feature Store
   feature_store.put_record(
       FeatureGroupName='customer-features',
       Record=[...]
   )
   ```

4. **MLOps Pipeline**
   ```bash
   # Use SageMaker Pipelines
   aws sagemaker create-pipeline \
     --pipeline-name ml-pipeline \
     --pipeline-definition file://pipeline.json
   ```

---

## Troubleshooting

**Training job fails:**
- **ResourceLimitExceeded**: Service quota is 0 for training instances - request quota increase via AWS Service Quotas
- Check S3 data format (CSV without headers for XGBoost)
- Verify IAM role has S3 access
- Ensure sufficient data (minimum 100 samples)
- Review CloudWatch logs for errors

**Endpoint deployment fails:**
- Check instance type availability in region
- Verify model artifacts exist in S3
- Ensure IAM role permissions
- Check service quotas

**Prediction errors:**
- Verify input format matches training data
- Check feature order (must match training)
- Ensure endpoint is InService status
- Review endpoint logs in CloudWatch

**High latency:**
- Use larger instance type
- Enable auto-scaling
- Implement request batching
- Consider multi-model endpoints

---

## Additional Resources

- [Amazon SageMaker Documentation](https://docs.aws.amazon.com/sagemaker/)
- [SageMaker Python SDK](https://sagemaker.readthedocs.io/)
- [Built-in Algorithms](https://docs.aws.amazon.com/sagemaker/latest/dg/algos.html)
- [SageMaker Examples](https://github.com/aws/amazon-sagemaker-examples)
- [SageMaker Pricing](https://aws.amazon.com/sagemaker/pricing/)
- [Best Practices Guide](https://docs.aws.amazon.com/sagemaker/latest/dg/best-practices.html)
