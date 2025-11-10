# Lab 10.A: AWS Well-Architected Framework and Cloud Architecture Best Practices

## Overview
This lab explores the AWS Well-Architected Framework, a set of best practices for designing and operating reliable, secure, efficient, and cost-effective systems in the cloud. You'll learn the six pillars of the framework and implement practical solutions based on Well-Architected principles.

## Objectives
- Understand the six pillars of the Well-Architected Framework
- Conduct Well-Architected reviews
- Implement operational excellence practices
- Design for security and compliance
- Build reliable and resilient architectures
- Optimize performance efficiency
- Implement cost optimization strategies
- Design sustainable cloud architectures

## Requirements
- AWS account with access to multiple services
- Understanding of all previous lab concepts
- AWS Well-Architected Tool access
- CloudWatch, Cost Explorer, and Trusted Advisor access
- Multi-service deployment experience

## Steps

### Step 1: Understand the Six Pillars
**1. Operational Excellence:**
- Perform operations as code
- Annotate documentation
- Anticipate failure
- Frequently make small, reversible changes
- Refine operations procedures frequently
- Learn from failures

**2. Security:**
- Implement strong identity foundation
- Enable traceability
- Apply security at all layers
- Automate security best practices
- Protect data in transit and at rest
- Keep people away from data
- Prepare for security events

**3. Reliability:**
- Test recovery procedures
- Automatically recover from failure
- Scale horizontally to increase aggregate workload availability
- Stop guessing capacity
- Manage change through automation

**4. Performance Efficiency:**
- Democratize advanced technologies
- Go global in minutes
- Use serverless architectures
- Experiment more often
- Consider mechanical sympathy

**5. Cost Optimization:**
- Implement cloud financial management
- Adopt a consumption model
- Measure overall efficiency
- Stop spending money on undifferentiated heavy lifting
- Analyze and attribute expenditure

**6. Sustainability:**
- Understand your impact
- Establish sustainability goals
- Maximize utilization
- Anticipate and adopt new, more efficient offerings
- Use managed services
- Reduce downstream impact

### Step 2: Access AWS Well-Architected Tool
1. Navigate to AWS Well-Architected Tool
2. Define workload:
   - Name: `Production Web Application`
   - Description: Multi-tier web application
   - Industry: Technology
   - Environment: Production
   - AWS Regions: us-east-1, us-west-2
3. Apply lenses:
   - AWS Well-Architected Framework
   - Serverless Application Lens
   - SaaS Lens (if applicable)

### Step 3: Conduct Well-Architected Review
1. Answer questions for each pillar:

**Operational Excellence Sample Questions:**
- How do you implement observability in your workload?
- How do you understand the health of your workload?
- How do you evolve your workload?

**Security Sample Questions:**
- How do you securely operate your workload?
- How do you detect and investigate security events?
- How do you protect your compute resources?

2. Document current state and improvements
3. Review risk summaries (High, Medium, Low)
4. Generate improvement plan

### Step 4: Implement Operational Excellence

**A. Operations as Code:**
```yaml
# infrastructure.yaml - Everything as code
Resources:
  MonitoringDashboard:
    Type: AWS::CloudWatch::Dashboard
    Properties:
      DashboardName: operations-dashboard
      DashboardBody: !Sub |
        {
          "widgets": [
            {
              "type": "metric",
              "properties": {
                "metrics": [
                  ["AWS/EC2", "CPUUtilization"],
                  ["AWS/RDS", "DatabaseConnections"],
                  ["AWS/ApplicationELB", "TargetResponseTime"]
                ],
                "period": 300,
                "stat": "Average",
                "region": "${AWS::Region}",
                "title": "System Health"
              }
            }
          ]
        }
```

**B. Runbook Automation:**
```python
# automated_runbook.py
import boto3

def handle_high_cpu(instance_id):
    """Automated response to high CPU"""
    ec2 = boto3.client('ec2')
    
    # 1. Capture diagnostics
    ec2.create_snapshot(InstanceId=instance_id)
    
    # 2. Scale out if in Auto Scaling group
    asg = boto3.client('autoscaling')
    # Trigger scale-out
    
    # 3. Alert operations team
    sns = boto3.client('sns')
    sns.publish(
        TopicArn='arn:aws:sns:region:account:ops-alerts',
        Message=f'High CPU on {instance_id} - Auto-remediation initiated'
    )
```

**C. Implement Tagging Strategy:**
```yaml
Resources:
  EC2Instance:
    Type: AWS::EC2::Instance
    Properties:
      Tags:
        - Key: Environment
          Value: Production
        - Key: Application
          Value: WebApp
        - Key: CostCenter
          Value: Engineering
        - Key: Owner
          Value: team@example.com
        - Key: Compliance
          Value: HIPAA
        - Key: BackupPolicy
          Value: Daily
```

### Step 5: Implement Security Best Practices

**A. Defense in Depth:**
```yaml
# Multi-layer security
Resources:
  # Layer 1: Network ACLs
  PrivateNACL:
    Type: AWS::EC2::NetworkAcl
    Properties:
      VpcId: !Ref VPC
  
  # Layer 2: Security Groups
  ApplicationSG:
    Type: AWS::EC2::SecurityGroup
    Properties:
      GroupDescription: Application tier
      SecurityGroupIngress:
        - IpProtocol: tcp
          FromPort: 443
          ToPort: 443
          SourceSecurityGroupId: !Ref LoadBalancerSG
  
  # Layer 3: WAF
  WebACL:
    Type: AWS::WAFv2::WebACL
    Properties:
      Rules:
        - Name: RateLimitRule
          Priority: 1
          Statement:
            RateBasedStatement:
              Limit: 2000
              AggregateKeyType: IP
          Action:
            Block: {}
```

**B. Enable Comprehensive Logging:**
```yaml
Resources:
  # CloudTrail for API logging
  CloudTrail:
    Type: AWS::CloudTrail::Trail
    Properties:
      IsLogging: true
      IsMultiRegionTrail: true
      IncludeGlobalServiceEvents: true
      S3BucketName: !Ref LogBucket
  
  # VPC Flow Logs
  VPCFlowLog:
    Type: AWS::EC2::FlowLog
    Properties:
      ResourceType: VPC
      ResourceId: !Ref VPC
      TrafficType: ALL
      LogDestinationType: cloud-watch-logs
      LogGroupName: /aws/vpc/flowlogs
  
  # Config for compliance
  ConfigRecorder:
    Type: AWS::Config::ConfigurationRecorder
    Properties:
      RecordingGroup:
        AllSupported: true
        IncludeGlobalResourceTypes: true
```

**C. Implement Encryption:**
```yaml
Resources:
  # KMS for encryption
  EncryptionKey:
    Type: AWS::KMS::Key
    Properties:
      EnableKeyRotation: true
      KeyPolicy:
        Statement:
          - Sid: Enable IAM policies
            Effect: Allow
            Principal:
              AWS: !Sub 'arn:aws:iam::${AWS::AccountId}:root'
            Action: 'kms:*'
            Resource: '*'
  
  # Encrypted S3 bucket
  DataBucket:
    Type: AWS::S3::Bucket
    Properties:
      BucketEncryption:
        ServerSideEncryptionConfiguration:
          - ServerSideEncryptionByDefault:
              SSEAlgorithm: aws:kms
              KMSMasterKeyID: !Ref EncryptionKey
      PublicAccessBlockConfiguration:
        BlockPublicAcls: true
        BlockPublicPolicy: true
        IgnorePublicAcls: true
        RestrictPublicBuckets: true
```

### Step 6: Build Reliable Architecture

**A. Multi-AZ Deployment:**
```yaml
Resources:
  # Multi-AZ RDS
  Database:
    Type: AWS::RDS::DBInstance
    Properties:
      MultiAZ: true
      BackupRetentionPeriod: 30
      PreferredBackupWindow: "03:00-04:00"
  
  # Multi-AZ Auto Scaling
  AutoScalingGroup:
    Type: AWS::AutoScaling::AutoScalingGroup
    Properties:
      VPCZoneIdentifier:
        - !Ref PrivateSubnet1
        - !Ref PrivateSubnet2
        - !Ref PrivateSubnet3
      MinSize: 3
      MaxSize: 12
      HealthCheckType: ELB
      HealthCheckGracePeriod: 300
```

**B. Implement Health Checks and Auto-Recovery:**
```yaml
Resources:
  # ELB Health Check
  TargetGroup:
    Type: AWS::ElasticLoadBalancingV2::TargetGroup
    Properties:
      HealthCheckEnabled: true
      HealthCheckIntervalSeconds: 30
      HealthCheckPath: /health
      HealthCheckProtocol: HTTP
      HealthCheckTimeoutSeconds: 5
      HealthyThresholdCount: 2
      UnhealthyThresholdCount: 3
  
  # Auto-recovery alarm
  StatusCheckAlarm:
    Type: AWS::CloudWatch::Alarm
    Properties:
      AlarmActions:
        - !Sub 'arn:aws:automate:${AWS::Region}:ec2:recover'
      MetricName: StatusCheckFailed_System
      Namespace: AWS/EC2
      Statistic: Minimum
      Period: 60
      EvaluationPeriods: 2
      Threshold: 1
      ComparisonOperator: GreaterThanThreshold
```

**C. Disaster Recovery Strategy:**
```python
# disaster_recovery_plan.py
"""
RTO (Recovery Time Objective): 4 hours
RPO (Recovery Point Objective): 1 hour

Strategy: Warm Standby in secondary region
"""

import boto3

def failover_to_secondary_region():
    """Automated failover procedure"""
    
    # 1. Promote read replica to primary
    rds = boto3.client('rds', region_name='us-west-2')
    rds.promote_read_replica(
        DBInstanceIdentifier='replica-instance'
    )
    
    # 2. Update Route 53 to point to secondary region
    route53 = boto3.client('route53')
    route53.change_resource_record_sets(
        HostedZoneId='Z1234567890ABC',
        ChangeBatch={
            'Changes': [{
                'Action': 'UPSERT',
                'ResourceRecordSet': {
                    'Name': 'app.example.com',
                    'Type': 'CNAME',
                    'TTL': 60,
                    'ResourceRecords': [
                        {'Value': 'secondary-alb.us-west-2.elb.amazonaws.com'}
                    ]
                }
            }]
        }
    )
    
    # 3. Scale up secondary region capacity
    asg = boto3.client('autoscaling', region_name='us-west-2')
    asg.set_desired_capacity(
        AutoScalingGroupName='app-asg-secondary',
        DesiredCapacity=10
    )
```

### Step 7: Optimize Performance

**A. Use CDN for Global Performance:**
```yaml
Resources:
  CloudFrontDistribution:
    Type: AWS::CloudFront::Distribution
    Properties:
      DistributionConfig:
        Enabled: true
        Origins:
          - DomainName: !GetAtt ALB.DNSName
            Id: ALB
            CustomOriginConfig:
              OriginProtocolPolicy: https-only
        DefaultCacheBehavior:
          TargetOriginId: ALB
          ViewerProtocolPolicy: redirect-to-https
          CachePolicyId: 658327ea-f89d-4fab-a63d-7e88639e58f6  # CachingOptimized
          Compress: true
        PriceClass: PriceClass_All
```

**B. Implement Caching Strategy:**
```python
# multi_tier_caching.py
import boto3
import redis
from functools import wraps

# Layer 1: Application cache (Redis/ElastiCache)
redis_client = redis.Redis(host='cache.example.com', port=6379)

# Layer 2: Database query cache
dynamodb = boto3.resource('dynamodb')

def cache_result(ttl=300):
    """Multi-tier caching decorator"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache_key = f"{func.__name__}:{args}:{kwargs}"
            
            # Try Layer 1: Redis
            cached = redis_client.get(cache_key)
            if cached:
                return cached
            
            # Execute function
            result = func(*args, **kwargs)
            
            # Store in cache
            redis_client.setex(cache_key, ttl, result)
            
            return result
        return wrapper
    return decorator
```

**C. Choose Right Database for Workload:**
```yaml
# Different databases for different access patterns
Resources:
  # Relational data: RDS
  TransactionalDB:
    Type: AWS::RDS::DBInstance
    Properties:
      Engine: postgres
      DBInstanceClass: db.r6g.xlarge
  
  # Key-value: DynamoDB
  SessionStore:
    Type: AWS::DynamoDB::Table
    Properties:
      BillingMode: PAY_PER_REQUEST
      TimeToLiveSpecification:
        Enabled: true
        AttributeName: ttl
  
  # Search: OpenSearch
  SearchCluster:
    Type: AWS::OpenSearchService::Domain
    Properties:
      EngineVersion: 'OpenSearch_2.5'
  
  # Analytics: Redshift
  DataWarehouse:
    Type: AWS::Redshift::Cluster
    Properties:
      NodeType: dc2.large
      NumberOfNodes: 2
```

### Step 8: Implement Cost Optimization

**A. Right-Sizing Resources:**
```python
# cost_optimization.py
import boto3
from datetime import datetime, timedelta

def analyze_resource_utilization():
    """Identify underutilized resources"""
    cloudwatch = boto3.client('cloudwatch')
    ec2 = boto3.client('ec2')
    
    recommendations = []
    
    # Check EC2 CPU utilization
    instances = ec2.describe_instances()
    for reservation in instances['Reservations']:
        for instance in reservation['Instances']:
            instance_id = instance['InstanceId']
            
            metrics = cloudwatch.get_metric_statistics(
                Namespace='AWS/EC2',
                MetricName='CPUUtilization',
                Dimensions=[{'Name': 'InstanceId', 'Value': instance_id}],
                StartTime=datetime.now() - timedelta(days=14),
                EndTime=datetime.now(),
                Period=3600,
                Statistics=['Average']
            )
            
            avg_cpu = sum(m['Average'] for m in metrics['Datapoints']) / len(metrics['Datapoints'])
            
            if avg_cpu < 10:
                recommendations.append({
                    'resource': instance_id,
                    'type': 'EC2',
                    'recommendation': 'Consider downsizing or terminating',
                    'avg_utilization': avg_cpu
                })
    
    return recommendations
```

**B. Use Savings Plans and Reserved Instances:**
```bash
# Analyze savings opportunities
aws ce get-reservation-purchase-recommendation \
  --service EC2 \
  --lookback-period-in-days SIXTY_DAYS \
  --payment-option NO_UPFRONT

aws ce get-savings-plans-purchase-recommendation \
  --savings-plans-type COMPUTE_SP \
  --lookback-period-in-days SIXTY_DAYS \
  --payment-option NO_UPFRONT
```

**C. Implement Auto-Scaling and Scheduling:**
```yaml
# Auto-scaling based on schedule
Resources:
  ScheduledActionScaleUp:
    Type: AWS::AutoScaling::ScheduledAction
    Properties:
      AutoScalingGroupName: !Ref AutoScalingGroup
      DesiredCapacity: 10
      Recurrence: "0 8 * * MON-FRI"  # Scale up at 8 AM weekdays
  
  ScheduledActionScaleDown:
    Type: AWS::AutoScaling::ScheduledAction
    Properties:
      AutoScalingGroupName: !Ref AutoScalingGroup
      DesiredCapacity: 2
      Recurrence: "0 18 * * MON-FRI"  # Scale down at 6 PM weekdays
```

### Step 9: Design for Sustainability

**A. Choose Energy-Efficient Regions:**
- Use AWS regions with renewable energy
- Prefer Graviton processors (better performance per watt)
- Select latest generation instances

**B. Optimize Resource Utilization:**
```yaml
Resources:
  # Use Graviton instances
  EC2Instance:
    Type: AWS::EC2::Instance
    Properties:
      InstanceType: t4g.micro  # Graviton-based
      ImageId: !Sub '{{resolve:ssm:/aws/service/ami-amazon-linux-latest/amzn2-ami-hvm-arm64-gp2}}'
  
  # Use Fargate Spot for non-critical workloads
  ECSService:
    Type: AWS::ECS::Service
    Properties:
      CapacityProviderStrategy:
        - CapacityProvider: FARGATE_SPOT
          Weight: 4
        - CapacityProvider: FARGATE
          Weight: 1
```

### Step 10: Review and Iterate
1. Generate Well-Architected Review report
2. Prioritize improvements by risk level
3. Create improvement plan with timeline
4. Implement changes incrementally
5. Re-run Well-Architected Review quarterly
6. Track metrics and improvements over time

## Validation
- [ ] Well-Architected Review completed
- [ ] High-risk items identified and documented
- [ ] Operational excellence practices implemented
- [ ] Security best practices applied
- [ ] Multi-AZ deployment configured
- [ ] Performance optimization implemented
- [ ] Cost optimization strategies applied
- [ ] Sustainability considered in design
- [ ] Improvement plan created
- [ ] Monitoring and observability configured

## Cleanup
This is a conceptual lab focused on best practices. Clean up any test resources created during implementation.

## Summary
In this lab, you explored the AWS Well-Architected Framework and implemented best practices across all six pillars. You learned how to conduct reviews, identify improvements, and build cloud architectures that are operationally excellent, secure, reliable, performant, cost-optimized, and sustainable. These principles form the foundation for production-grade AWS deployments.

**Key Takeaways:**
- Well-Architected Framework provides proven best practices
- Six pillars: Operational Excellence, Security, Reliability, Performance, Cost, Sustainability
- Regular reviews identify risks and improvement opportunities
- Defense in depth implements layered security
- Multi-AZ deployments ensure high availability
- Right-sizing and auto-scaling optimize costs
- Sustainability focuses on environmental impact
- Continuous improvement is essential
- Monitoring and observability enable operational excellence
- Automation reduces human error and improves consistency
