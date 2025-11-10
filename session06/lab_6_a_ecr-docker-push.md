# Lab 6.A: Build and push Docker images to Amazon Elastic Container Registry (ECR)

## Overview
Build a Docker image locally (or in CI), push it to a private Amazon ECR repository, enable image scanning and lifecycle rules, and validate the pushed image. Includes CLI and CI examples.

## Objectives
- Create an ECR repository
- Authenticate Docker to ECR
- Build, tag, and push Docker images to ECR
- Enable image scanning on push and a lifecycle policy
- Verify images and clean up
- Provide a CI workflow example (GitHub Actions)

## Prerequisites
- AWS CLI v2 configured with appropriate profile
- Docker (and docker buildx for multi-arch)
- IAM permissions: ecr:CreateRepository, ecr:GetAuthorizationToken, ecr:BatchCheckLayerAvailability, ecr:PutImage, ecr:InitiateLayerUpload, ecr:UploadLayerPart, ecr:CompleteLayerUpload, ecr:DescribeRepositories, ecr:DeleteRepository, ecr:PutImageScanningConfiguration, ecr:PutLifecyclePolicy
- (Optional) GitHub repo for CI

---

## Variables (example)
- REGION=us-east-1
- ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
- REPO_NAME=lab-app
- IMAGE_TAG=latest

---

## Steps (CLI)

1. Create ECR repository
```bash
aws ecr create-repository --repository-name $REPO_NAME --region $REGION || true
```

2. Authenticate Docker to ECR
```bash
aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin "${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"
```

3. Example Dockerfile (place at project root)
```dockerfile
# filepath: Dockerfile
FROM public.ecr.aws/amazonlinux/amazonlinux:2023
RUN yum -y update && yum -y install httpd && yum clean all
COPY index.html /var/www/html/index.html
CMD ["httpd", "-D", "FOREGROUND"]
```

4. Build and tag image
```bash
docker build -t ${REPO_NAME}:${IMAGE_TAG} .
docker tag ${REPO_NAME}:${IMAGE_TAG} ${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${REPO_NAME}:${IMAGE_TAG}
```

5. Push image
```bash
docker push ${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${REPO_NAME}:${IMAGE_TAG}
```

6. Verify image in ECR
```bash
aws ecr describe-images --repository-name $REPO_NAME --region $REGION
```

7. Enable image scanning on push
```bash
aws ecr put-image-scanning-configuration --repository-name $REPO_NAME --image-scanning-configuration scanOnPush=true --region $REGION
```

8. Apply a lifecycle policy (example: keep last 10 images)
```bash
cat > lifecycle.json <<'EOF'
{
  "rules": [
    {
      "rulePriority": 1,
      "description": "keep last 10 images",
      "selection": {
        "tagStatus": "any",
        "countType": "imageCountMoreThan",
        "countNumber": 10
      },
      "action": { "type": "expire" }
    }
  ]
}
EOF

aws ecr put-lifecycle-policy --repository-name $REPO_NAME --lifecycle-policy-text file://lifecycle.json --region $REGION
```

9. Multi-arch build (optional)
```bash
docker buildx create --use --name multi-builder || true
docker buildx build --platform linux/amd64,linux/arm64 -t ${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${REPO_NAME}:${IMAGE_TAG} --push .
```

10. CI example (GitHub Actions) — build & push on push to main
```yaml
# filepath: .github/workflows/ecr-push.yml
name: Build and push to ECR
on:
  push:
    branches: [ main ]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Login to ECR
        uses: aws-actions/amazon-ecr-login@v2
        with:
          region: ${{ secrets.AWS_REGION }}
      - name: Build and push
        run: |
          IMAGE="${{ secrets.AWS_ACCOUNT_ID }}.dkr.ecr.${{ secrets.AWS_REGION }}.amazonaws.com/${{ env.REPO_NAME }}:$(date +%s)"
          docker build -t "$IMAGE" .
          docker push "$IMAGE"
        env:
          REPO_NAME: lab-app
```

11. Cleanup
```bash
# delete repository and all images
aws ecr delete-repository --repository-name $REPO_NAME --force --region $REGION
```

---

## IAM policy example (scoped)
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect":"Allow",
      "Action":[
        "ecr:CreateRepository","ecr:DeleteRepository",
        "ecr:DescribeRepositories","ecr:GetAuthorizationToken",
        "ecr:BatchCheckLayerAvailability","ecr:PutImage",
        "ecr:InitiateLayerUpload","ecr:UploadLayerPart",
        "ecr:CompleteLayerUpload","ecr:PutImageScanningConfiguration",
        "ecr:PutLifecyclePolicy"
      ],
      "Resource":"arn:aws:ecr:*:*:repository/${REPO_NAME}"
    }
  ]
}
```

## Validation checklist
- [ ] ECR repository exists
- [ ] Docker authenticated to ECR
- [ ] Image built, tagged, and pushed successfully
- [ ] Image scanning enabled and lifecycle policy applied
- [ ] CI workflow builds and pushes image (optional)

## Notes & best practices
- Use short-lived credentials or OIDC/GitHub Actions for CI.
- Sign images and enable image scanning for security.
- Use lifecycle policies to control storage costs.
- Prefer immutable tags (SHA digest) in production deployments.
