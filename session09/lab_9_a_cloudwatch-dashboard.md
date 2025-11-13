# Lab 9.A: Configure CloudWatch dashboards, metrics, and alarms

## Overview
This lab explores advanced CloudFormation features including custom resources with Lambda, CloudFormation macros, StackSets for multi-account deployment, and integrating CloudFormation with CI/CD pipelines. You'll learn production-grade patterns for automating complex infrastructure deployments at scale.

## Objectives
- Create custom resources with Lambda-backed Custom Resources
- Implement CloudFormation macros for template transformation
- Deploy infrastructure across multiple accounts with StackSets
- Integrate CloudFormation with CodePipeline for CI/CD
- Use CloudFormation Registry and third-party extensions
- Implement blue-green deployments with CloudFormation
- Optimize large-scale stack deployments
- Implement stack protection and termination protection

## Requirements
- Completed Lab 9.A or equivalent CloudFormation knowledge
- Multiple AWS accounts (for StackSets) or Organizations setup
- Advanced Python or Node.js skills
- Understanding of CI/CD concepts
- AWS CLI and Git installed

## Steps

### Step 1: Create Lambda-Backed Custom Resource
1. Create Lambda function for custom resource:
   ```python
   # custom_resource_function.py
   import json
   import boto3
   import cfnresponse
   
   def lambda_handler(event, context):
       print(f"Event: {json.dumps(event)}")
       
       request_type = event['RequestType']
       properties = event.get('ResourceProperties', {})
       
       try:
           if request_type == 'Create':
               # Custom creation logic
               result = create_resource(properties)
               cfnresponse.send(event, context, cfnresponse.SUCCESS, 
                              {'ResourceId': result})
           
           elif request_type == 'Update':
               # Custom update logic
               result = update_resource(properties)
               cfnresponse.send(event, context, cfnresponse.SUCCESS,
                              {'ResourceId': result})
           
           elif request_type == 'Delete':
               # Custom deletion logic
               delete_resource(properties)
               cfnresponse.send(event, context, cfnresponse.SUCCESS, {})
       
       except Exception as e:
           print(f"Error: {str(e)}")
           cfnresponse.send(event, context, cfnresponse.FAILED,
                          {'Error': str(e)})
   
   def create_resource(properties):
       # Example: Create DynamoDB item
       table_name = properties.get('TableName')
       item_id = properties.get('ItemId')
       
       dynamodb = boto3.resource('dynamodb')
       table = dynamodb.Table(table_name)
       table.put_item(Item={'id': item_id, 'data': 'custom resource'})
       
       return item_id
   
   def update_resource(properties):
       # Update logic
       return properties.get('ItemId')
   
   def delete_resource(properties):
       # Delete logic
       table_name = properties.get('TableName')
       item_id = properties.get('ItemId')
       
       dynamodb = boto3.resource('dynamodb')
       table = dynamodb.Table(table_name)
       table.delete_item(Key={'id': item_id})
   ```

2. Package and deploy Lambda:
   ```bash
   zip custom_resource.zip custom_resource_function.py
   
   aws lambda create-function \
     --function-name CustomResourceHandler \
     --runtime python3.12 \
     --role arn:aws:iam::account:role/lambda-execution-role \
     --handler custom_resource_function.lambda_handler \
     --zip-file fileb://custom_resource.zip
   ```

3. Use custom resource in template:
   ```yaml
   # template-with-custom-resource.yaml
   Resources:
     DynamoDBTable:
       Type: AWS::DynamoDB::Table
       Properties:
         TableName: CustomResourceTable
         AttributeDefinitions:
           - AttributeName: id
             AttributeType: S
         KeySchema:
           - AttributeName: id
             KeyType: HASH
         BillingMode: PAY_PER_REQUEST
     
     CustomResourceHandler:
       Type: AWS::Lambda::Function
       Properties:
         FunctionName: CustomResourceHandler
         Runtime: python3.12
         Handler: index.lambda_handler
         Role: !GetAtt LambdaExecutionRole.Arn
         Code:
           ZipFile: |
             # Inline code here
     
     CustomResource:
       Type: Custom::DynamoDBInitializer
       Properties:
         ServiceToken: !GetAtt CustomResourceHandler.Arn
         TableName: !Ref DynamoDBTable
         ItemId: initial-item
   ```

### Step 2: Create CloudFormation Macro
1. Create macro Lambda function:
   ```python
   # macro_function.py
   import json
   
   def lambda_handler(event, context):
       fragment = event['fragment']
       template_parameter_values = event.get('templateParameterValues', {})
       
       # Transform template
       transformed_fragment = transform_template(fragment, template_parameter_values)
       
       return {
           'requestId': event['requestId'],
           'status': 'success',
           'fragment': transformed_fragment
       }
   
   def transform_template(fragment, params):
       # Example: Add common tags to all resources
       common_tags = [
           {'Key': 'ManagedBy', 'Value': 'CloudFormation'},
           {'Key': 'Environment', 'Value': params.get('Environment', 'dev')}
       ]
       
       for resource_name, resource in fragment.get('Resources', {}).items():
           if 'Properties' not in resource:
               resource['Properties'] = {}
           
           # Add tags to taggable resources
           if resource['Type'] in ['AWS::EC2::Instance', 'AWS::S3::Bucket']:
               if 'Tags' not in resource['Properties']:
                   resource['Properties']['Tags'] = []
               resource['Properties']['Tags'].extend(common_tags)
       
       return fragment
   ```

2. Register macro:
   ```yaml
   # macro-template.yaml
   Resources:
     MacroFunction:
       Type: AWS::Lambda::Function
       Properties:
         FunctionName: AddCommonTagsMacro
         Runtime: python3.12
         Handler: index.lambda_handler
         Role: !GetAtt MacroExecutionRole.Arn
         Code:
           ZipFile: |
             # Inline code
     
     Macro:
       Type: AWS::CloudFormation::Macro
       Properties:
         Name: AddCommonTags
         FunctionName: !GetAtt MacroFunction.Arn
   ```

3. Use macro in templates:
   ```yaml
   Transform: AddCommonTags
   
   Parameters:
     Environment:
       Type: String
       Default: dev
   
   Resources:
     MyBucket:
       Type: AWS::S3::Bucket
       # Tags will be added automatically by macro
   ```

### Step 3: Configure StackSets for Multi-Account Deployment
1. Create StackSet template:
   ```yaml
   # stackset-template.yaml
   AWSTemplateFormatVersion: '2010-09-09'
   Description: 'Security baseline for all accounts'
   
   Resources:
     CloudTrailBucket:
       Type: AWS::S3::Bucket
       Properties:
         BucketName: !Sub 'cloudtrail-logs-${AWS::AccountId}'
         PublicAccessBlockConfiguration:
           BlockPublicAcls: true
           BlockPublicPolicy: true
           IgnorePublicAcls: true
           RestrictPublicBuckets: true
     
     CloudTrail:
       Type: AWS::CloudTrail::Trail
       Properties:
         TrailName: organization-trail
         S3BucketName: !Ref CloudTrailBucket
         IsLogging: true
         IncludeGlobalServiceEvents: true
         IsMultiRegionTrail: true
   ```

2. Create StackSet:
   ```bash
   aws cloudformation create-stack-set \
     --stack-set-name security-baseline \
     --template-body file://stackset-template.yaml \
     --capabilities CAPABILITY_IAM \
     --permission-model SERVICE_MANAGED \
     --auto-deployment Enabled=true,RetainStacksOnAccountRemoval=false
   ```

3. Deploy to accounts and regions:
   ```bash
   aws cloudformation create-stack-instances \
     --stack-set-name security-baseline \
     --deployment-targets OrganizationalUnitIds=ou-xxxx-xxxx \
     --regions us-east-1 us-west-2 eu-west-1
   ```

### Step 4: Integrate with CodePipeline
1. Create pipeline template:
   ```yaml
   # pipeline-template.yaml
   Resources:
     ArtifactBucket:
       Type: AWS::S3::Bucket
     
     CodePipeline:
       Type: AWS::CodePipeline::Pipeline
       Properties:
         Name: infrastructure-pipeline
         RoleArn: !GetAtt PipelineRole.Arn
         ArtifactStore:
           Type: S3
           Location: !Ref ArtifactBucket
         Stages:
           - Name: Source
             Actions:
               - Name: SourceAction
                 ActionTypeId:
                   Category: Source
                   Owner: AWS
                   Provider: CodeCommit
                   Version: 1
                 Configuration:
                   RepositoryName: infrastructure-repo
                   BranchName: main
                 OutputArtifacts:
                   - Name: SourceOutput
           
           - Name: Deploy-Dev
             Actions:
               - Name: CreateChangeSet
                 ActionTypeId:
                   Category: Deploy
                   Owner: AWS
                   Provider: CloudFormation
                   Version: 1
                 Configuration:
                   ActionMode: CHANGE_SET_REPLACE
                   StackName: app-stack-dev
                   ChangeSetName: app-changeset-dev
                   TemplatePath: SourceOutput::template.yaml
                   Capabilities: CAPABILITY_IAM
                   RoleArn: !GetAtt CloudFormationRole.Arn
                 InputArtifacts:
                   - Name: SourceOutput
               
               - Name: ExecuteChangeSet
                 ActionTypeId:
                   Category: Deploy
                   Owner: AWS
                   Provider: CloudFormation
                   Version: 1
                 Configuration:
                   ActionMode: CHANGE_SET_EXECUTE
                   StackName: app-stack-dev
                   ChangeSetName: app-changeset-dev
                 RunOrder: 2
           
           - Name: Manual-Approval
             Actions:
               - Name: ApproveProduction
                 ActionTypeId:
                   Category: Approval
                   Owner: AWS
                   Provider: Manual
                   Version: 1
           
           - Name: Deploy-Prod
             Actions:
               - Name: CreateChangeSet
                 ActionTypeId:
                   Category: Deploy
                   Owner: AWS
                   Provider: CloudFormation
                   Version: 1
                 Configuration:
                   ActionMode: CHANGE_SET_REPLACE
                   StackName: app-stack-prod
                   ChangeSetName: app-changeset-prod
                   TemplatePath: SourceOutput::template.yaml
                   Capabilities: CAPABILITY_IAM
                   RoleArn: !GetAtt CloudFormationRole.Arn
                 InputArtifacts:
                   - Name: SourceOutput
               
               - Name: ExecuteChangeSet
                 ActionTypeId:
                   Category: Deploy
                   Owner: AWS
                   Provider: CloudFormation
                   Version: 1
                 Configuration:
                   ActionMode: CHANGE_SET_EXECUTE
                   StackName: app-stack-prod
                   ChangeSetName: app-changeset-prod
                 RunOrder: 2
   ```

### Step 5: Implement Blue-Green Deployment
1. Create blue-green template:
   ```yaml
   Parameters:
     ActiveEnvironment:
       Type: String
       Default: blue
       AllowedValues: [blue, green]
   
   Resources:
     BlueEnvironment:
       Type: AWS::ElasticBeanstalk::Environment
       Properties:
         EnvironmentName: app-blue
         # Configuration
     
     GreenEnvironment:
       Type: AWS::ElasticBeanstalk::Environment
       Properties:
         EnvironmentName: app-green
         # Configuration
     
     Route53Record:
       Type: AWS::Route53::RecordSet
       Properties:
         HostedZoneId: Z1234567890ABC
         Name: app.example.com
         Type: CNAME
         TTL: 300
         ResourceRecords:
           - !If
             - IsBlueActive
             - !GetAtt BlueEnvironment.EndpointURL
             - !GetAtt GreenEnvironment.EndpointURL
   
   Conditions:
     IsBlueActive: !Equals [!Ref ActiveEnvironment, blue]
   ```

2. Switch traffic:
   ```bash
   # Update parameter to switch from blue to green
   aws cloudformation update-stack \
     --stack-name app-stack \
     --use-previous-template \
     --parameters ParameterKey=ActiveEnvironment,ParameterValue=green
   ```

### Step 6: Use CloudFormation Registry Extensions
1. Activate third-party extension:
   ```bash
   # List available extensions
   aws cloudformation list-types --visibility PUBLIC
   
   # Activate extension
   aws cloudformation activate-type \
     --type RESOURCE \
     --type-name Example::ThirdParty::Resource \
     --public-version-number 1.0.0
   ```

2. Use in template:
   ```yaml
   Resources:
     ThirdPartyResource:
       Type: Example::ThirdParty::Resource
       Properties:
         # Extension-specific properties
   ```

### Step 7: Implement Stack Protection
1. Enable termination protection:
   ```bash
   aws cloudformation update-termination-protection \
     --stack-name production-stack \
     --enable-termination-protection
   ```

2. Create stack with protection:
   ```bash
   aws cloudformation create-stack \
     --stack-name critical-stack \
     --template-body file://template.yaml \
     --enable-termination-protection
   ```

### Step 8: Optimize Large Stack Deployments
1. Use nested stacks for modularity:
   ```yaml
   Resources:
     NetworkLayer:
       Type: AWS::CloudFormation::Stack
       Properties:
         TemplateURL: !Sub 'https://s3.amazonaws.com/${TemplateBucket}/network.yaml'
     
     DataLayer:
       Type: AWS::CloudFormation::Stack
       Properties:
         TemplateURL: !Sub 'https://s3.amazonaws.com/${TemplateBucket}/data.yaml'
         Parameters:
           VPCId: !GetAtt NetworkLayer.Outputs.VPCId
     
     AppLayer:
       Type: AWS::CloudFormation::Stack
       DependsOn: DataLayer
       Properties:
         TemplateURL: !Sub 'https://s3.amazonaws.com/${TemplateBucket}/app.yaml'
   ```

2. Use parallel stack creation where possible
3. Implement resource chunking for large resource sets

### Step 9: Implement Stack Monitoring and Alerts
1. Create SNS topic for stack events:
   ```yaml
   Resources:
     StackEventsTopic:
       Type: AWS::SNS::Topic
       Properties:
         DisplayName: CloudFormation Stack Events
         Subscription:
           - Endpoint: ops-team@example.com
             Protocol: email
   
   Outputs:
     EventTopicArn:
       Value: !Ref StackEventsTopic
       Export:
         Name: stack-events-topic
   ```

2. Configure stack notifications:
   ```bash
   aws cloudformation create-stack \
     --stack-name monitored-stack \
     --template-body file://template.yaml \
     --notification-arns arn:aws:sns:region:account:stack-events-topic
   ```

### Step 10: Implement Infrastructure Testing
1. Use cfn-lint for template validation:
   ```bash
   pip install cfn-lint
   cfn-lint template.yaml
   ```

2. Use taskcat for multi-region testing:
   ```yaml
   # .taskcat.yml
   project:
     name: infrastructure-testing
   tests:
     default:
       template: template.yaml
       regions:
         - us-east-1
         - us-west-2
       parameters:
         Environment: test
   ```

3. Run tests:
   ```bash
   taskcat test run
   ```

## Validation
- [ ] Custom resources with Lambda created
- [ ] CloudFormation macro implemented
- [ ] StackSets deployed across accounts
- [ ] CodePipeline integration working
- [ ] Blue-green deployment tested
- [ ] Third-party extensions activated
- [ ] Stack protection enabled
- [ ] Nested stacks deployed successfully
- [ ] Stack monitoring configured
- [ ] Infrastructure tests passing

## Cleanup
1. Delete StackSet instances and StackSets
2. Delete CodePipeline and related resources
3. Delete all stacks in order
4. Deactivate CloudFormation extensions
5. Delete Lambda functions for custom resources/macros
6. Delete S3 buckets (empty first)
7. Verify all resources removed

## Summary
In this lab, you mastered advanced CloudFormation features including custom resources, macros, StackSets, and CI/CD integration. You learned how to build production-grade infrastructure automation, deploy across multiple accounts, implement blue-green deployments, and integrate infrastructure testing. These patterns enable enterprise-scale infrastructure management with CloudFormation.

**Key Takeaways:**
- Custom resources extend CloudFormation capabilities
- Macros transform templates dynamically
- StackSets enable multi-account, multi-region deployment
- CI/CD integration automates infrastructure changes
- Blue-green deployments minimize risk
- Termination protection prevents accidental deletions
- Nested stacks organize complex infrastructures
- cfn-lint and taskcat improve template quality
- CloudFormation Registry provides third-party extensions
- Monitoring and alerting ensure stack health
