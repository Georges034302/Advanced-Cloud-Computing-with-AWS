# Lab 10.B: Build and deploy infrastructure using AWS CDK (Python version)

## Overview
Use the AWS Cloud Development Kit (CDK) with Python to define, synthesize, and deploy cloud infrastructure as code. This lab shows how to initialize a CDK Python project, author a simple stack (S3 + Lambda + IAM), bootstrap an environment, deploy the stack, and clean up.

## Objectives
- Install and initialize AWS CDK (v2) for Python
- Author and synthesize a CDK app and stack
- Bootstrap the environment and deploy the stack
- Inspect deployed resources and logs
- Update and destroy the stack

## Prerequisites
- AWS CLI v2 configured with credentials
- Python 3.9+ and pip
- Node.js (required by CDK)
- IAM permissions to create IAM, S3, Lambda, CloudFormation resources

---

## Quick setup (commands)
Run these in the workspace (Ubuntu devcontainer).

```bash
# install CDK CLI (global)
npm install -g aws-cdk@2

# create project directory
cd /workspaces/Advanced-Cloud-Computing-with-AWS/session10
mkdir cdk-python-app && cd cdk-python-app

# initialize python cdk app
cdk init app --language python

# create and activate virtualenv
python3 -m venv .venv
source .venv/bin/activate

# install dependencies
pip install -r requirements.txt
# if aws-cdk-lib not in requirements, add:
pip install aws-cdk-lib constructs
```

If this is a fresh account/region, bootstrap (required once):
```bash
cdk bootstrap aws://$(aws sts get-caller-identity --query Account --output text)/$(aws configure get region)
```

---

## Example stack: S3 bucket + Lambda (minimal)

Replace contents of app code with the following examples.

app.py (entry)
```python
# filepath: cdk-python-app/app.py
import aws_cdk as cdk
from stacks.simple_stack import SimpleStack

app = cdk.App()
SimpleStack(app, "lab-cdk-simple-stack")
app.synth()
```

stacks/simple_stack.py
```python
# filepath: cdk-python-app/stacks/simple_stack.py
from aws_cdk import (
    Stack,
    aws_s3 as s3,
    aws_lambda as _lambda,
    aws_iam as iam,
)
from constructs import Construct
import aws_cdk as cdk
import os

class SimpleStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        # S3 bucket (encrypted, versioned)
        bucket = s3.Bucket(self, "LabBucket",
            versioned=True,
            encryption=s3.BucketEncryption.S3_MANAGED,
            removal_policy=cdk.RemovalPolicy.RETAIN
        )

        # Lambda role (basic)
        role = iam.Role(self, "LambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole"),
            ]
        )
        bucket.grant_read_write(role)

        # Lambda function (inline code example)
        fn = _lambda.Function(self, "ProcessorFn",
            runtime=_lambda.Runtime.PYTHON_3_9,
            handler="handler.lambda_handler",
            code=_lambda.InlineCode(
                "import boto3,os\ns3=boto3.client('s3')\ndef lambda_handler(event,context):\n  print('hello from cdk lambda')\n  return {'status':'ok'}"
            ),
            role=role,
            timeout=cdk.Duration.seconds(30),
        )

        # Output bucket name
        cdk.CfnOutput(self, "BucketName", value=bucket.bucket_name)
```

handler (if packaging a real lambda)
```python
# filepath: cdk-python-app/lambda/handler.py
import json
def lambda_handler(event, context):
    print("hello from deployed lambda")
    return {"statusCode": 200, "body": json.dumps({"msg":"ok"})}
```

Add the lambda code path to the Function 'code' property if you package instead of InlineCode.

---

## Synthesize, deploy, update, destroy

Synthesize the CloudFormation template:
```bash
cdk synth
```

Deploy the stack:
```bash
cdk deploy --require-approval never
```

Inspect outputs and resources:
- CDK prints outputs (BucketName)
- Use AWS CLI to verify:
  aws s3 ls s3://<BucketName>
  aws lambda list-functions --query "Functions[?contains(FunctionName,'lab-cdk-simple-stack')]" 

Update: change code or stack, then:
```bash
# synth + deploy picks up changes
cdk synth
cdk deploy --require-approval never
```

Destroy:
```bash
cdk destroy --force
```

Note: RemovalPolicy.RETAIN on the bucket prevents accidental deletion; remove or change it to DESTROY to allow CDK to delete the bucket (empty bucket required).

---

## Tips & best practices
- Use CDK context and parameters for environment-specific values.
- Keep Lambdas small and package dependencies using Docker or pip wheel caching.
- Use constructs and patterns to share reusable infrastructure.
- Use CI/CD (GitHub Actions) to synth/deploy CDK stacks with least-privilege roles and OIDC where possible.
- Enable versioning and encryption on data stores; use removal policies carefully.

---

## Validation checklist
- [ ] CDK v2 CLI installed
- [ ] Virtualenv created and dependencies installed
- [ ] App synthesizes: cdk synth
- [ ] Stack deployed: cdk deploy
- [ ] Resources present (S3 bucket, Lambda) and outputs visible
- [ ] Stack updated and destroyed successfully

---

## Cleanup
- Run cdk destroy to remove deployed resources (adjust bucket removal policy if needed).
- Deactivate virtualenv: deactivate
- Remove project folder if desired.

## Summary
This lab demonstrates authoring and deploying infrastructure with AWS CDK (Python). It covers project initialization, stack authoring (S3 + Lambda), bootstrapping, deploy/update lifecycle, and cleanup — enabling modern, code-first infrastructure workflows.
