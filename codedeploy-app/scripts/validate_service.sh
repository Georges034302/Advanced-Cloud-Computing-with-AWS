#!/bin/bash
# Wait for application to be ready (retry up to 30 seconds)
for i in {1..30}; do
  if curl -f http://127.0.0.1/health > /dev/null 2>&1; then
    echo "Application is healthy"
    
    # Update instance tag to CodeDeploy-Green after successful deployment
    INSTANCE_ID=$(ec2-metadata --instance-id | cut -d" " -f2)
    REGION=$(ec2-metadata --availability-zone | cut -d" " -f2 | sed 's/[a-z]$//')
    aws ec2 create-tags --resources "$INSTANCE_ID" --tags Key=Name,Value=CodeDeploy-Green --region "$REGION" 2>/dev/null || true
    
    exit 0
  fi
  sleep 1
done
echo "Application failed health check after 30 seconds"
exit 1
