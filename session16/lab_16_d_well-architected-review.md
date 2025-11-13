# Lab 16.D: AWS Well-Architected Tool – Framework Review

## Overview
The AWS Well-Architected Tool helps you review your workloads against AWS best practices across six pillars: Operational Excellence, Security, Reliability, Performance Efficiency, Cost Optimization, and Sustainability. This lab demonstrates how to create a workload, perform a review, and generate improvement recommendations.

---

## Objectives
- Create a Well-Architected workload
- List available lenses (frameworks)
- Review workload questions across six pillars
- Answer best practice questions
- Generate improvement recommendations
- Create review milestones
- Export workload data
- Clean up resources

---

## Prerequisites
- AWS CLI configured
- IAM permissions: `wellarchitected:*`
- Region: **ap-southeast-2** (Sydney)
- Understanding of AWS Well-Architected Framework concepts

---

## Architecture

```
┌─────────────────────────────────────────────────┐
│    AWS Well-Architected Framework               │
│    Six Pillars for Cloud Excellence             │
└─────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────┐
│         1. Operational Excellence               │
│  - Design, run, and improve systems             │
│  - Automation, monitoring, observability        │
├─────────────────────────────────────────────────┤
│         2. Security                             │
│  - Protect data, systems, and assets            │
│  - IAM, encryption, detection, response         │
├─────────────────────────────────────────────────┤
│         3. Reliability                          │
│  - Recover from failures, meet demand           │
│  - Fault tolerance, backup, disaster recovery   │
├─────────────────────────────────────────────────┤
│         4. Performance Efficiency               │
│  - Use resources efficiently                    │
│  - Right-sizing, elasticity, caching            │
├─────────────────────────────────────────────────┤
│         5. Cost Optimization                    │
│  - Achieve business outcomes at lowest cost     │
│  - Resource optimization, pricing models        │
├─────────────────────────────────────────────────┤
│         6. Sustainability                       │
│  - Minimize environmental impact                │
│  - Efficient resource usage, carbon footprint   │
└─────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────┐
│    AWS Well-Architected Tool                    │
│  - Define workload                              │
│  - Answer questions for each pillar             │
│  - Receive improvement recommendations          │
│  - Track progress with milestones               │
│  - Generate reports and share findings          │
└─────────────────────────────────────────────────┘
```

---

# Step 1 – Set Environment Variables

```bash
# Set region
REGION="ap-southeast-2"
export AWS_REGION="$REGION"

# Define workload details
WORKLOAD_NAME="SampleModernWorkload"
WORKLOAD_DESCRIPTION="Training workload for Well-Architected Framework review"
REVIEW_OWNER="CloudArchitect"
ENVIRONMENT="PRODUCTION"
LENS_ALIAS="wellarchitected"

# Echo all variables for verification
echo "=== Well-Architected Configuration ==="
echo "Region: $REGION"
echo "Workload Name: $WORKLOAD_NAME"
echo "Review Owner: $REVIEW_OWNER"
echo "Environment: $ENVIRONMENT"
echo "Lens: $LENS_ALIAS"
echo "======================================"
echo ""
```

**Expected Output:**
```
=== Well-Architected Configuration ===
Region: ap-southeast-2
Workload Name: SampleModernWorkload
Review Owner: CloudArchitect
Environment: PRODUCTION
Lens: wellarchitected
======================================
```

---

# Step 2 – List Available Lenses

```bash
# List all available Well-Architected lenses
echo "Listing available Well-Architected lenses..."

aws wellarchitected list-lenses \
  --region "$REGION" \
  --query 'LensSummaries[*].[LensAlias,LensName,Description]' \
  --output table

echo ""
echo "✅ Available lenses listed"
echo ""
```

**Expected Output:**
```
Listing available Well-Architected lenses...
----------------------------------------------------------------------------------
|                              ListLenses                                         |
+--------------------------------------------------------------------------------+
|  wellarchitected      |  AWS Well-Architected Framework  |  The AWS Well-... |
|  serverless           |  Serverless Lens                 |  Best practices...|
|  softwareasaservice   |  SaaS Lens                       |  SaaS workload...|
+--------------------------------------------------------------------------------+

✅ Available lenses listed
```

---

# Step 3 – Create a Well-Architected Workload

```bash
# Create a new workload for review
echo "Creating Well-Architected workload..."

WORKLOAD_ID=$(aws wellarchitected create-workload \
  --workload-name "$WORKLOAD_NAME" \
  --description "$WORKLOAD_DESCRIPTION" \
  --environment "$ENVIRONMENT" \
  --review-owner "$REVIEW_OWNER" \
  --aws-regions "$REGION" \
  --lenses "$LENS_ALIAS" \
  --region "$REGION" \
  --query 'WorkloadId' \
  --output text)

echo "✅ Workload created successfully"
echo "   Workload ID: $WORKLOAD_ID"
echo ""
```

**Expected Output:**
```
Creating Well-Architected workload...
✅ Workload created successfully
   Workload ID: abc123def456ghi789jkl012mno345pqr
```

---

# Step 4 – Get Workload Details

```bash
# Retrieve detailed information about the workload
echo "Retrieving workload details..."

aws wellarchitected get-workload \
  --workload-id "$WORKLOAD_ID" \
  --region "$REGION" \
  --query 'Workload.[WorkloadName,Environment,ReviewOwner,WorkloadId]' \
  --output table

echo ""
echo "✅ Workload details retrieved"
echo ""
```

**Expected Output:**
```
Retrieving workload details...
---------------------------------------------------------------------------
|                          GetWorkload                                     |
+-------------------------------------------------------------------------+
|  SampleModernWorkload  |  PRODUCTION  |  CloudArchitect  |  abc123...   |
+-------------------------------------------------------------------------+

✅ Workload details retrieved
```

---

# Step 5 – List Lens Review Summary

```bash
# Get summary of the lens review
echo "Getting lens review summary..."

aws wellarchitected get-lens-review \
  --workload-id "$WORKLOAD_ID" \
  --lens-alias "$LENS_ALIAS" \
  --region "$REGION" \
  --query 'LensReview.[LensAlias,LensName,LensStatus,PillarReviewSummaries[*].[PillarId,PillarName]]' \
  --output json | jq .

echo ""
echo "✅ Lens review summary retrieved"
echo ""
```

**Expected Output:**
```
Getting lens review summary...
[
  "wellarchitected",
  "AWS Well-Architected Framework",
  "NOT_COMPLETE",
  [
    ["operationalExcellence", "Operational Excellence"],
    ["security", "Security"],
    ["reliability", "Reliability"],
    ["performance", "Performance Efficiency"],
    ["costOptimization", "Cost Optimization"],
    ["sustainability", "Sustainability"]
  ]
]

✅ Lens review summary retrieved
```

---

# Step 6 – List Questions for Review

```bash
# List all questions for the workload
echo "Listing questions for Well-Architected review..."

aws wellarchitected list-answers \
  --workload-id "$WORKLOAD_ID" \
  --lens-alias "$LENS_ALIAS" \
  --region "$REGION" \
  --max-results 5 \
  --query 'AnswerSummaries[*].[QuestionId,QuestionTitle,PillarId]' \
  --output table

echo ""
echo "Note: Showing first 5 questions (full framework has 50+ questions)"
echo "✅ Questions listed"
echo ""
```

**Expected Output:**
```
Listing questions for Well-Architected review...
---------------------------------------------------------------------------
|                            ListAnswers                                   |
+-------------------------------------------------------------------------+
|  ops_1  |  How do you determine priorities?  |  operationalExcellence |
|  ops_2  |  How do you structure?             |  operationalExcellence |
|  sec_1  |  How do you manage identities?     |  security              |
|  sec_2  |  How do you manage permissions?    |  security              |
|  rel_1  |  How do you manage service quotas? |  reliability           |
+-------------------------------------------------------------------------+

Note: Showing first 5 questions (full framework has 50+ questions)
✅ Questions listed
```

---

# Step 7 – Get Detailed Question Information

```bash
# Get details for a specific question
echo "Getting detailed information for first question..."

QUESTION_ID=$(aws wellarchitected list-answers \
  --workload-id "$WORKLOAD_ID" \
  --lens-alias "$LENS_ALIAS" \
  --region "$REGION" \
  --max-results 1 \
  --query 'AnswerSummaries[0].QuestionId' \
  --output text)

echo "Question ID: $QUESTION_ID"
echo ""

aws wellarchitected get-answer \
  --workload-id "$WORKLOAD_ID" \
  --lens-alias "$LENS_ALIAS" \
  --question-id "$QUESTION_ID" \
  --region "$REGION" \
  --query 'Answer.[QuestionId,QuestionTitle,HelpfulResourceUrl]' \
  --output table

echo ""
echo "✅ Question details retrieved"
echo ""
```

**Expected Output:**
```
Getting detailed information for first question...
Question ID: ops_1

---------------------------------------------------------------------------
|                            GetAnswer                                     |
+-------------------------------------------------------------------------+
|  ops_1  |  How do you determine priorities?  |  https://docs.aws...  |
+-------------------------------------------------------------------------+

✅ Question details retrieved
```

---

# Step 8 – Answer a Question (Example)

```bash
# Answer a specific question with selected choices
echo "Answering a sample question..."

# Get available choices for the question
echo "Available choices for question: $QUESTION_ID"

aws wellarchitected get-answer \
  --workload-id "$WORKLOAD_ID" \
  --lens-alias "$LENS_ALIAS" \
  --question-id "$QUESTION_ID" \
  --region "$REGION" \
  --query 'Answer.Choices[*].[ChoiceId,Title]' \
  --output table

echo ""

# Update answer with selected choices
aws wellarchitected update-answer \
  --workload-id "$WORKLOAD_ID" \
  --lens-alias "$LENS_ALIAS" \
  --question-id "$QUESTION_ID" \
  --selected-choices "ops_1_a" "ops_1_b" \
  --notes "Implemented business metrics and operational priorities" \
  --region "$REGION" \
  --output json > /dev/null

echo "✅ Question answered successfully"
echo "   Question: $QUESTION_ID"
echo "   Selected choices: ops_1_a, ops_1_b"
echo ""
```

**Expected Output:**
```
Answering a sample question...
Available choices for question: ops_1

---------------------------------------------------------------------------
|                            GetAnswer                                     |
+-------------------------------------------------------------------------+
|  ops_1_a  |  Business outcomes are prioritized                          |
|  ops_1_b  |  Evaluate internal and external customer needs              |
|  ops_1_c  |  Evaluate compliance requirements                           |
|  ops_1_d  |  Evaluate threat landscape                                  |
+-------------------------------------------------------------------------+

✅ Question answered successfully
   Question: ops_1
   Selected choices: ops_1_a, ops_1_b
```

---

# Step 9 – Get Improvement Recommendations

```bash
# List improvement items from the review
echo "Generating improvement recommendations..."

aws wellarchitected list-lens-review-improvements \
  --workload-id "$WORKLOAD_ID" \
  --lens-alias "$LENS_ALIAS" \
  --region "$REGION" \
  --max-results 10 \
  --query 'ImprovementSummaries[*].[PillarId,QuestionTitle,ImprovementPlanUrl]' \
  --output table

echo ""
echo "✅ Improvement recommendations generated"
echo ""
```

**Expected Output:**
```
Generating improvement recommendations...
---------------------------------------------------------------------------
|                   ListLensReviewImprovements                             |
+-------------------------------------------------------------------------+
|  security  |  How do you manage identities?  |  https://docs.aws...   |
|  security  |  How do you detect events?      |  https://docs.aws...   |
|  reliability | How do you back up data?      |  https://docs.aws...   |
|  costOptimization | Monitor usage?         |  https://docs.aws...   |
+-------------------------------------------------------------------------+

✅ Improvement recommendations generated
```

---

# Step 10 – Create a Milestone

```bash
# Create a milestone to track progress over time
echo "Creating review milestone..."

MILESTONE_NAME="Initial-Review-$(date +%Y%m%d)"

aws wellarchitected create-milestone \
  --workload-id "$WORKLOAD_ID" \
  --milestone-name "$MILESTONE_NAME" \
  --region "$REGION" \
  --query 'MilestoneNumber' \
  --output text

echo "✅ Milestone created: $MILESTONE_NAME"
echo ""
```

**Expected Output:**
```
Creating review milestone...
✅ Milestone created: Initial-Review-20251113
```

---

# Step 11 – List All Milestones

```bash
# List all milestones for the workload
echo "Listing all milestones..."

aws wellarchitected list-milestones \
  --workload-id "$WORKLOAD_ID" \
  --region "$REGION" \
  --query 'MilestoneSummaries[*].[MilestoneNumber,MilestoneName,RecordedAt]' \
  --output table

echo ""
echo "✅ Milestones listed"
echo ""
```

**Expected Output:**
```
Listing all milestones...
---------------------------------------------------------------------------
|                          ListMilestones                                  |
+-------------------------------------------------------------------------+
|  1  |  Initial-Review-20251113  |  2025-11-13T10:30:00+00:00            |
+-------------------------------------------------------------------------+

✅ Milestones listed
```

---

# Step 12 – Export Workload Details to JSON

```bash
# Export complete workload configuration
echo "Exporting workload details to JSON..."

aws wellarchitected get-workload \
  --workload-id "$WORKLOAD_ID" \
  --region "$REGION" \
  --output json > /tmp/workload-export.json

echo "✅ Workload exported to: /tmp/workload-export.json"

# Display file info
echo ""
echo "File size: $(du -h /tmp/workload-export.json | cut -f1)"
echo ""
```

**Expected Output:**
```
Exporting workload details to JSON...
✅ Workload exported to: /tmp/workload-export.json

File size: 2.8K
```

---

# Step 13 – Export Improvement Plan to JSON

```bash
# Export improvement recommendations
echo "Exporting improvement plan to JSON..."

aws wellarchitected list-lens-review-improvements \
  --workload-id "$WORKLOAD_ID" \
  --lens-alias "$LENS_ALIAS" \
  --region "$REGION" \
  --output json > /tmp/improvement-plan.json

echo "✅ Improvement plan exported to: /tmp/improvement-plan.json"

# Display summary
echo ""
echo "=== Improvement Plan Summary ==="
IMPROVEMENT_COUNT=$(jq '.ImprovementSummaries | length' /tmp/improvement-plan.json)
echo "Total improvements identified: $IMPROVEMENT_COUNT"
echo "================================"
echo ""
```

**Expected Output:**
```
Exporting improvement plan to JSON...
✅ Improvement plan exported to: /tmp/improvement-plan.json

=== Improvement Plan Summary ===
Total improvements identified: 23
================================
```

---

# Step 14 – Cleanup Resources

```bash
# Clean up all created resources
echo "Starting cleanup process..."
echo ""

# Delete workload
echo "Deleting Well-Architected workload..."
aws wellarchitected delete-workload \
  --workload-id "$WORKLOAD_ID" \
  --region "$REGION"

echo "✅ Workload deleted: $WORKLOAD_ID"

# Delete local files
echo ""
echo "Cleaning up local files..."
rm -f /tmp/workload-export.json
rm -f /tmp/improvement-plan.json

echo "✅ Local files removed"

echo ""
echo "========================================="
echo "✅ Cleanup completed successfully!"
echo "========================================="
echo ""
echo "All resources have been deleted:"
echo "  ✓ Workload: $WORKLOAD_NAME"
echo "  ✓ Milestones and reviews"
echo "  ✓ Local export files"
echo ""
```

**Expected Output:**
```
Starting cleanup process...

Deleting Well-Architected workload...
✅ Workload deleted: abc123def456ghi789jkl012mno345pqr

Cleaning up local files...
✅ Local files removed

=========================================
✅ Cleanup completed successfully!
=========================================

All resources have been deleted:
  ✓ Workload: SampleModernWorkload
  ✓ Milestones and reviews
  ✓ Local export files
```

---

## AWS Well-Architected Framework – Six Pillars

### 1. Operational Excellence
**Focus**: Run and monitor systems to deliver business value

**Best Practices:**
- Implement Infrastructure as Code (CloudFormation, Terraform, CDK)
- Use CI/CD pipelines for automated deployments
- Monitor with CloudWatch, X-Ray, and distributed tracing
- Implement comprehensive logging and observability
- Conduct regular game days and failure testing
- Document runbooks and playbooks
- Use tagging for resource management

**Key Questions:**
- How do you determine priorities?
- How do you design workload observability?
- How do you understand operational health?

---

### 2. Security
**Focus**: Protect data, systems, and assets

**Best Practices:**
- Implement identity and access management with least privilege
- Enable detective controls (CloudTrail, GuardDuty, Config)
- Protect data at rest and in transit with encryption
- Use security groups and network segmentation
- Automate security best practices
- Enable MFA for all users
- Regularly rotate credentials and secrets

**Key Questions:**
- How do you securely operate your workload?
- How do you manage identities and permissions?
- How do you detect and investigate security events?

---

### 3. Reliability
**Focus**: Recover from failures and meet demand

**Best Practices:**
- Design for failure (assume everything fails)
- Use Multi-AZ deployments for high availability
- Implement automatic recovery and self-healing
- Back up data regularly with tested restore procedures
- Use Auto Scaling for demand changes
- Test disaster recovery procedures
- Monitor service quotas and limits

**Key Questions:**
- How do you manage service quotas and constraints?
- How do you design your workload to withstand component failures?
- How do you test reliability?

---

### 4. Performance Efficiency
**Focus**: Use computing resources efficiently

**Best Practices:**
- Right-size resources based on monitoring data
- Use elasticity to match supply with demand
- Implement caching strategies (ElastiCache, CloudFront)
- Use serverless architectures where appropriate
- Choose optimal database solutions for workloads
- Monitor performance metrics and set alarms
- Use latest AWS services and features

**Key Questions:**
- How do you select appropriate resource types?
- How do you use networking resources?
- How do you evolve your workload to take advantage of new releases?

---

### 5. Cost Optimization
**Focus**: Achieve business outcomes at the lowest price point

**Best Practices:**
- Implement cost allocation tags
- Use Reserved Instances and Savings Plans
- Right-size and terminate unused resources
- Use S3 storage classes and lifecycle policies
- Monitor costs with Cost Explorer and AWS Budgets
- Use Spot Instances for fault-tolerant workloads
- Implement automated cost optimization

**Key Questions:**
- How do you govern usage?
- How do you monitor usage and cost?
- How do you decommission resources?

---

### 6. Sustainability
**Focus**: Minimize environmental impact of cloud workloads

**Best Practices:**
- Use efficient compute resources (Graviton processors)
- Maximize resource utilization
- Use managed services to reduce overhead
- Implement data lifecycle management
- Choose regions with renewable energy
- Use serverless to eliminate idle resources
- Optimize software and architecture efficiency

**Key Questions:**
- How do you select Regions to support sustainability goals?
- How do you take advantage of software patterns to support sustainability?
- How do you manage demand and supply resources?

---

## Best Practices

### Conducting Reviews
- **Regular reviews** - Conduct reviews quarterly or when significant changes occur
- **Team involvement** - Include architects, developers, and operations teams
- **Honest assessment** - Answer questions truthfully to get accurate recommendations
- **Track progress** - Use milestones to measure improvement over time
- **Prioritize improvements** - Focus on high-risk and high-impact items first

### Using the Tool
- **Multiple workloads** - Create separate workloads for different applications
- **Custom lenses** - Use specialized lenses (Serverless, SaaS, IoT) when applicable
- **Share findings** - Export and share reports with stakeholders
- **Action plans** - Create concrete action items from improvement recommendations
- **Documentation** - Document architectural decisions and rationale

### Continuous Improvement
- **Iterative process** - Well-Architected is not one-time, it's continuous
- **Measure progress** - Compare milestones to track improvements
- **Learn from others** - Review AWS case studies and reference architectures
- **Stay current** - Framework updates regularly with new best practices
- **Automation** - Automate checks where possible (AWS Config rules, Lambda)

---

## Troubleshooting

### Issue: AccessDeniedException
**Cause**: Missing IAM permissions  
**Solution**:
```bash
# Required IAM permissions:
# - wellarchitected:CreateWorkload
# - wellarchitected:GetWorkload
# - wellarchitected:UpdateWorkload
# - wellarchitected:DeleteWorkload
# - wellarchitected:ListAnswers
# - wellarchitected:UpdateAnswer
# - wellarchitected:CreateMilestone

# Verify permissions
aws iam get-user-policy \
  --user-name YOUR_USERNAME \
  --policy-name WellArchitectedAccess
```

### Issue: Cannot Create Milestone
**Cause**: Must answer at least one question before creating milestone  
**Solution**:
```bash
# Answer at least one question first
aws wellarchitected update-answer \
  --workload-id $WORKLOAD_ID \
  --lens-alias wellarchitected \
  --question-id QUESTION_ID \
  --selected-choices CHOICE_ID
```

### Issue: Lens Not Found
**Cause**: Invalid lens alias or lens not available in region  
**Solution**:
```bash
# List available lenses
aws wellarchitected list-lenses \
  --region ap-southeast-2 \
  --query 'LensSummaries[*].LensAlias'

# Common lens aliases:
# - wellarchitected
# - serverless
# - softwareasaservice
```

### Issue: Too Many Questions to Answer
**Cause**: Full Well-Architected review has 50+ questions  
**Solution**:
- Focus on specific pillars first (security, cost optimization)
- Answer questions iteratively over time
- Use milestones to track progress
- Prioritize high-risk areas based on your workload
- Consider using AWS Partner Network consultants for comprehensive reviews

---

## Key Takeaways

1. **Six Pillars** provide comprehensive framework for cloud excellence
2. **Regular reviews** help maintain architectural best practices
3. **Improvement recommendations** linked to AWS documentation and solutions
4. **Milestones** enable progress tracking over time
5. **Multiple lenses** available for specialized workloads
6. **Free tool** accessible to all AWS customers
7. **Continuous process** - not a one-time activity
8. **Actionable insights** help prioritize improvements

---

## Summary

In this lab, you:
- ✅ Listed available Well-Architected lenses
- ✅ Created a Well-Architected workload
- ✅ Retrieved workload details and lens review summary
- ✅ Listed review questions across six pillars
- ✅ Answered sample questions with best practice choices
- ✅ Generated improvement recommendations
- ✅ Created milestone to track progress
- ✅ Exported workload and improvement plan data
- ✅ Cleaned up all resources

The AWS Well-Architected Framework and Tool provide systematic approach to building secure, high-performing, resilient, efficient, and cost-optimized cloud applications.

---

## End of Lab 16.D

**Congratulations!** You have completed Session 16 - Cost Management & Optimization

---
