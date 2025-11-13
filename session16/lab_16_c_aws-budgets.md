# Lab 16.C: AWS Budgets – Cost Alerts and Monitoring

## Overview
AWS Budgets enables you to set custom cost and usage budgets with automated alerts when thresholds are exceeded. This lab demonstrates how to create budgets, configure notification thresholds, and receive alerts via Amazon SNS and email.

---

## Objectives
- Create Amazon SNS topic for budget notifications
- Set up monthly cost budget with spending limits
- Configure multiple alert thresholds (forecasted and actual)
- Subscribe to budget alerts via email
- Query budget status and details
- Clean up budget resources

---

## Prerequisites
- AWS CLI configured
- IAM permissions: `budgets:*`, `sns:*`, `aws-portal:ViewBilling`
- Valid email address for notifications
- Region: **us-east-1** (SNS for budget alerts must use us-east-1)
- Note: Budgets are account-level, not region-specific

---

## Architecture

```
┌─────────────────────────────────────────────────┐
│         AWS Cost & Usage Data                   │
│  (Real-time spending across all services)       │
└─────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────┐
│         AWS Budgets                             │
│  - Monthly/Quarterly/Annual budgets             │
│  - Cost or usage thresholds                     │
│  - Forecasted vs Actual tracking                │
│  - Multiple alert thresholds                    │
└─────────────────────────────────────────────────┘
                      ↓
           Budget Threshold Exceeded
                      ↓
┌─────────────────────────────────────────────────┐
│         Amazon SNS Topic                        │
│  - budget-alerts topic                          │
│  - Publishes alerts when thresholds hit         │
└─────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────┐
│         Email Notifications                     │
│  - 80% forecasted threshold warning             │
│  - 100% actual cost alert                       │
│  - Immediate email delivery                     │
└─────────────────────────────────────────────────┘
```

---

# Step 1 – Set Environment Variables

```bash
# Set region for SNS (must be us-east-1 for budget alerts)
REGION="us-east-1"
export AWS_REGION="$REGION"

# Define budget configuration
BUDGET_NAME="MonthlyCostBudget"
BUDGET_AMOUNT="50"  # Budget limit in USD
SNS_TOPIC_NAME="budget-alerts"

# Set your email for notifications
EMAIL="your-email@example.com"  # ⚠️ CHANGE THIS to your email

# Get AWS account ID
ACCOUNT_ID=$(aws sts get-caller-identity \
  --query Account \
  --output text)

# Echo all variables for verification
echo "=== Budget Configuration ==="
echo "Region: $REGION"
echo "Account ID: $ACCOUNT_ID"
echo "Budget Name: $BUDGET_NAME"
echo "Budget Amount: \$$BUDGET_AMOUNT USD"
echo "SNS Topic: $SNS_TOPIC_NAME"
echo "Email: $EMAIL"
echo "============================"
echo ""
```

**Expected Output:**
```
=== Budget Configuration ===
Region: us-east-1
Account ID: 123456789012
Budget Name: MonthlyCostBudget
Budget Amount: $50 USD
SNS Topic: budget-alerts
Email: your-email@example.com
============================
```

---

# Step 2 – Create SNS Topic for Budget Alerts

```bash
# Create SNS topic for budget notifications
echo "Creating SNS topic for budget alerts..."

aws sns create-topic \
  --name "$SNS_TOPIC_NAME" \
  --tags "Key=Purpose,Value=Budget-Alerts" \
  --region "$REGION" \
  --output json > /dev/null

echo "✅ SNS topic created: $SNS_TOPIC_NAME"

# Get SNS topic ARN
TOPIC_ARN=$(aws sns list-topics \
  --region "$REGION" \
  --query "Topics[?contains(TopicArn, '${SNS_TOPIC_NAME}')].TopicArn" \
  --output text)

echo "✅ Topic ARN: $TOPIC_ARN"
echo ""
```

**Expected Output:**
```
Creating SNS topic for budget alerts...
✅ SNS topic created: budget-alerts
✅ Topic ARN: arn:aws:sns:us-east-1:123456789012:budget-alerts
```

---

# Step 3 – Subscribe Email to SNS Topic

```bash
# Subscribe email address to receive budget alerts
echo "Subscribing email to SNS topic..."

aws sns subscribe \
  --topic-arn "$TOPIC_ARN" \
  --protocol email \
  --notification-endpoint "$EMAIL" \
  --region "$REGION" \
  --output json > /dev/null

echo "✅ Email subscription request sent to: $EMAIL"
echo ""
echo "⚠️  IMPORTANT: Check your email and click the confirmation link!"
echo "   You will receive an email from AWS Notifications"
echo "   Subject: 'AWS Notification - Subscription Confirmation'"
echo ""
echo "Press Enter after confirming the subscription..."
read
echo ""
```

**Expected Output:**
```
Subscribing email to SNS topic...
✅ Email subscription request sent to: your-email@example.com

⚠️  IMPORTANT: Check your email and click the confirmation link!
   You will receive an email from AWS Notifications
   Subject: 'AWS Notification - Subscription Confirmation'

Press Enter after confirming the subscription...
```

---

# Step 4 – Verify SNS Subscription

```bash
# Check if email subscription is confirmed
echo "Verifying email subscription status..."

aws sns list-subscriptions-by-topic \
  --topic-arn "$TOPIC_ARN" \
  --region "$REGION" \
  --query 'Subscriptions[*].[Protocol,Endpoint,SubscriptionArn]' \
  --output table

echo ""
echo "✅ Subscription verified"
echo ""
```

**Expected Output:**
```
Verifying email subscription status...
----------------------------------------------------------------------------------
|                        ListSubscriptionsByTopic                                 |
+--------------------------------------------------------------------------------+
|  email  |  your-email@example.com  |  arn:aws:sns:us-east-1:123...           |
+--------------------------------------------------------------------------------+

✅ Subscription verified
```

---

# Step 5 – Create Monthly Cost Budget

```bash
# Create AWS budget with monthly spending limit
echo "Creating monthly cost budget..."

aws budgets create-budget \
  --account-id "$ACCOUNT_ID" \
  --budget "{
    \"BudgetName\": \"$BUDGET_NAME\",
    \"BudgetLimit\": {
      \"Amount\": \"$BUDGET_AMOUNT\",
      \"Unit\": \"USD\"
    },
    \"CostFilters\": {},
    \"CostTypes\": {
      \"IncludeTax\": true,
      \"IncludeSubscription\": true,
      \"UseBlended\": false,
      \"IncludeRefund\": false,
      \"IncludeCredit\": false,
      \"IncludeUpfront\": true,
      \"IncludeRecurring\": true,
      \"IncludeOtherSubscription\": true,
      \"IncludeSupport\": true,
      \"IncludeDiscount\": true,
      \"UseAmortized\": false
    },
    \"TimeUnit\": \"MONTHLY\",
    \"BudgetType\": \"COST\"
  }"

echo "✅ Budget created: $BUDGET_NAME"
echo "   Budget Amount: \$$BUDGET_AMOUNT USD per month"
echo ""
```

**Expected Output:**
```
Creating monthly cost budget...
✅ Budget created: MonthlyCostBudget
   Budget Amount: $50 USD per month
```

---

# Step 6 – Add Forecasted Cost Alert (80% Threshold)

```bash
# Create notification for when forecasted cost exceeds 80%
echo "Adding forecasted cost alert (80% threshold)..."

aws budgets create-notification \
  --account-id "$ACCOUNT_ID" \
  --budget-name "$BUDGET_NAME" \
  --notification "{
    \"NotificationType\": \"FORECASTED\",
    \"ComparisonOperator\": \"GREATER_THAN\",
    \"Threshold\": 80,
    \"ThresholdType\": \"PERCENTAGE\",
    \"NotificationState\": \"ALARM\"
  }" \
  --subscriber "{
    \"SubscriptionType\": \"SNS\",
    \"Address\": \"$TOPIC_ARN\"
  }"

echo "✅ Forecasted alert added: 80% threshold"
echo "   Alert triggers when forecasted spending exceeds \$40 (80% of \$50)"
echo ""
```

**Expected Output:**
```
Adding forecasted cost alert (80% threshold)...
✅ Forecasted alert added: 80% threshold
   Alert triggers when forecasted spending exceeds $40 (80% of $50)
```

---

# Step 7 – Add Actual Cost Alert (100% Threshold)

```bash
# Create notification for when actual cost exceeds 100%
echo "Adding actual cost alert (100% threshold)..."

aws budgets create-notification \
  --account-id "$ACCOUNT_ID" \
  --budget-name "$BUDGET_NAME" \
  --notification "{
    \"NotificationType\": \"ACTUAL\",
    \"ComparisonOperator\": \"GREATER_THAN\",
    \"Threshold\": 100,
    \"ThresholdType\": \"PERCENTAGE\",
    \"NotificationState\": \"ALARM\"
  }" \
  --subscriber "{
    \"SubscriptionType\": \"SNS\",
    \"Address\": \"$TOPIC_ARN\"
  }"

echo "✅ Actual cost alert added: 100% threshold"
echo "   Alert triggers when actual spending exceeds \$50"
echo ""
```

**Expected Output:**
```
Adding actual cost alert (100% threshold)...
✅ Actual cost alert added: 100% threshold
   Alert triggers when actual spending exceeds $50
```

---

# Step 8 – Add Additional Alert (90% Threshold)

```bash
# Create an additional warning at 90% forecasted
echo "Adding additional warning alert (90% threshold)..."

aws budgets create-notification \
  --account-id "$ACCOUNT_ID" \
  --budget-name "$BUDGET_NAME" \
  --notification "{
    \"NotificationType\": \"FORECASTED\",
    \"ComparisonOperator\": \"GREATER_THAN\",
    \"Threshold\": 90,
    \"ThresholdType\": \"PERCENTAGE\",
    \"NotificationState\": \"ALARM\"
  }" \
  --subscriber "{
    \"SubscriptionType\": \"SNS\",
    \"Address\": \"$TOPIC_ARN\"
  }"

echo "✅ Additional alert added: 90% threshold"
echo "   Alert triggers when forecasted spending exceeds \$45 (90% of \$50)"
echo ""
```

**Expected Output:**
```
Adding additional warning alert (90% threshold)...
✅ Additional alert added: 90% threshold
   Alert triggers when forecasted spending exceeds $45 (90% of $50)
```

---

# Step 9 – Verify Budget Creation

```bash
# List all budgets in the account
echo "Verifying budget creation..."

aws budgets describe-budgets \
  --account-id "$ACCOUNT_ID" \
  --query 'Budgets[*].[BudgetName,BudgetLimit.Amount,BudgetLimit.Unit,TimeUnit]' \
  --output table

echo ""
echo "✅ Budget verification complete"
echo ""
```

**Expected Output:**
```
Verifying budget creation...
---------------------------------------------------------------------------
|                          DescribeBudgets                                 |
+-------------------------------------------------------------------------+
|  MonthlyCostBudget  |  50  |  USD  |  MONTHLY                           |
+-------------------------------------------------------------------------+

✅ Budget verification complete
```

---

# Step 10 – Get Detailed Budget Information

```bash
# Retrieve detailed budget configuration and current status
echo "Retrieving detailed budget information..."

aws budgets describe-budget \
  --account-id "$ACCOUNT_ID" \
  --budget-name "$BUDGET_NAME" \
  --output json | jq '{
    BudgetName: .Budget.BudgetName,
    BudgetLimit: .Budget.BudgetLimit,
    TimeUnit: .Budget.TimeUnit,
    BudgetType: .Budget.BudgetType,
    CalculatedSpend: .Budget.CalculatedSpend
  }'

echo ""
echo "✅ Budget details retrieved"
echo ""
```

**Expected Output:**
```
Retrieving detailed budget information...
{
  "BudgetName": "MonthlyCostBudget",
  "BudgetLimit": {
    "Amount": "50",
    "Unit": "USD"
  },
  "TimeUnit": "MONTHLY",
  "BudgetType": "COST",
  "CalculatedSpend": {
    "ActualSpend": {
      "Amount": "23.45",
      "Unit": "USD"
    },
    "ForecastedSpend": {
      "Amount": "42.30",
      "Unit": "USD"
    }
  }
}

✅ Budget details retrieved
```

---

# Step 11 – List All Notifications

```bash
# List all notifications configured for the budget
echo "Listing all budget notifications..."

aws budgets describe-notifications-for-budget \
  --account-id "$ACCOUNT_ID" \
  --budget-name "$BUDGET_NAME" \
  --query 'Notifications[*].[NotificationType,ComparisonOperator,Threshold,ThresholdType]' \
  --output table

echo ""
echo "✅ Notifications listed"
echo ""
```

**Expected Output:**
```
Listing all budget notifications...
---------------------------------------------------------------------------
|                  DescribeNotificationsForBudget                          |
+-------------------------------------------------------------------------+
|  FORECASTED  |  GREATER_THAN  |  80.0   |  PERCENTAGE                   |
|  ACTUAL      |  GREATER_THAN  |  100.0  |  PERCENTAGE                   |
|  FORECASTED  |  GREATER_THAN  |  90.0   |  PERCENTAGE                   |
+-------------------------------------------------------------------------+

✅ Notifications listed
```

---

# Step 12 – Export Budget Details to JSON

```bash
# Export complete budget configuration to file
echo "Exporting budget details to JSON file..."

aws budgets describe-budget \
  --account-id "$ACCOUNT_ID" \
  --budget-name "$BUDGET_NAME" \
  --output json > /tmp/budget-details.json

echo "✅ Budget details exported to: /tmp/budget-details.json"

# Display file info
echo ""
echo "File size: $(du -h /tmp/budget-details.json | cut -f1)"
echo ""
```

**Expected Output:**
```
Exporting budget details to JSON file...
✅ Budget details exported to: /tmp/budget-details.json

File size: 1.2K
```

---

# Step 13 – Test SNS Notification (Optional)

```bash
# Send test notification to verify email delivery
echo "Sending test notification..."

aws sns publish \
  --topic-arn "$TOPIC_ARN" \
  --subject "AWS Budget Alert - Test Message" \
  --message "This is a test notification from your AWS Budget setup. If you receive this email, your budget alerts are configured correctly." \
  --region "$REGION" \
  --output json > /dev/null

echo "✅ Test notification sent"
echo "   Check your email: $EMAIL"
echo ""
```

**Expected Output:**
```
Sending test notification...
✅ Test notification sent
   Check your email: your-email@example.com
```

---

# Step 14 – Cleanup Resources

```bash
# Clean up all created resources
echo "Starting cleanup process..."
echo ""

# Delete notifications first (must be done before deleting budget)
echo "Deleting budget notifications..."

# Delete 80% forecasted alert
aws budgets delete-notification \
  --account-id "$ACCOUNT_ID" \
  --budget-name "$BUDGET_NAME" \
  --notification "{
    \"NotificationType\": \"FORECASTED\",
    \"ComparisonOperator\": \"GREATER_THAN\",
    \"Threshold\": 80,
    \"ThresholdType\": \"PERCENTAGE\"
  }" 2>/dev/null

echo "  ✓ Deleted 80% forecasted alert"

# Delete 90% forecasted alert
aws budgets delete-notification \
  --account-id "$ACCOUNT_ID" \
  --budget-name "$BUDGET_NAME" \
  --notification "{
    \"NotificationType\": \"FORECASTED\",
    \"ComparisonOperator\": \"GREATER_THAN\",
    \"Threshold\": 90,
    \"ThresholdType\": \"PERCENTAGE\"
  }" 2>/dev/null

echo "  ✓ Deleted 90% forecasted alert"

# Delete 100% actual cost alert
aws budgets delete-notification \
  --account-id "$ACCOUNT_ID" \
  --budget-name "$BUDGET_NAME" \
  --notification "{
    \"NotificationType\": \"ACTUAL\",
    \"ComparisonOperator\": \"GREATER_THAN\",
    \"Threshold\": 100,
    \"ThresholdType\": \"PERCENTAGE\"
  }" 2>/dev/null

echo "  ✓ Deleted 100% actual cost alert"

# Delete the budget
echo ""
echo "Deleting budget..."
aws budgets delete-budget \
  --account-id "$ACCOUNT_ID" \
  --budget-name "$BUDGET_NAME"

echo "✅ Budget deleted: $BUDGET_NAME"

# Delete SNS topic
echo ""
echo "Deleting SNS topic..."
aws sns delete-topic \
  --topic-arn "$TOPIC_ARN" \
  --region "$REGION"

echo "✅ SNS topic deleted: $SNS_TOPIC_NAME"

# Delete local files
echo ""
echo "Cleaning up local files..."
rm -f /tmp/budget-details.json

echo "✅ Local files removed"

echo ""
echo "========================================="
echo "✅ Cleanup completed successfully!"
echo "========================================="
echo ""
echo "All resources have been deleted:"
echo "  ✓ Budget notifications (3)"
echo "  ✓ Budget: $BUDGET_NAME"
echo "  ✓ SNS topic: $SNS_TOPIC_NAME"
echo "  ✓ Local export files"
echo ""
```

**Expected Output:**
```
Starting cleanup process...

Deleting budget notifications...
  ✓ Deleted 80% forecasted alert
  ✓ Deleted 90% forecasted alert
  ✓ Deleted 100% actual cost alert

Deleting budget...
✅ Budget deleted: MonthlyCostBudget

Deleting SNS topic...
✅ SNS topic deleted: budget-alerts

Cleaning up local files...
✅ Local files removed

=========================================
✅ Cleanup completed successfully!
=========================================

All resources have been deleted:
  ✓ Budget notifications (3)
  ✓ Budget: MonthlyCostBudget
  ✓ SNS topic: budget-alerts
  ✓ Local export files
```

---

## Best Practices

### Budget Configuration
- **Set realistic budgets** based on historical spending patterns
- **Create multiple budgets** for different purposes:
  - Overall account budget
  - Service-specific budgets (EC2, RDS, S3, Lambda)
  - Project or team budgets (using cost allocation tags)
  - Environment budgets (dev, staging, production)
- **Use cost allocation tags** to track spending by project, team, or application

### Alert Thresholds
- **Multiple thresholds** provide progressive warnings:
  - 50% - Early awareness
  - 80% - Warning level
  - 90% - Critical warning
  - 100% - Budget exceeded
- **Use both forecasted and actual alerts**:
  - Forecasted alerts provide advance warning
  - Actual alerts confirm spending has exceeded threshold

### Notification Methods
- **Email** for human recipients (developers, managers)
- **SNS** for automated workflows:
  - Lambda functions for automated responses
  - EventBridge for complex workflows
  - Slack/PagerDuty integrations via SNS
- **Multiple subscribers** ensure alerts reach the right people

### Budget Types
- **Cost budgets** - Monitor spending in dollars
- **Usage budgets** - Track specific resource usage (EC2 hours, S3 GB)
- **Savings Plans budgets** - Monitor Savings Plans coverage
- **RI budgets** - Track Reserved Instance utilization

### Cost Optimization
- **Review budgets monthly** and adjust based on actual needs
- **Investigate anomalies** when alerts fire
- **Use AWS Cost Anomaly Detection** alongside budgets
- **Implement automated responses** to budget alerts (stop dev resources, notify teams)
- **Tag all resources** for granular cost tracking

---

## Troubleshooting

### Issue: Email Confirmation Not Received
**Cause**: Email in spam folder or incorrect email address  
**Solution**:
```bash
# Check spam/junk folder
# Verify subscription status
aws sns list-subscriptions-by-topic \
  --topic-arn $TOPIC_ARN \
  --region us-east-1

# Resend confirmation
aws sns subscribe \
  --topic-arn $TOPIC_ARN \
  --protocol email \
  --notification-endpoint your-email@example.com \
  --region us-east-1
```

### Issue: Budget Alerts Not Received
**Cause**: Subscription not confirmed or SNS policy issues  
**Solution**:
```bash
# Verify subscription is confirmed (not PendingConfirmation)
aws sns list-subscriptions-by-topic \
  --topic-arn $TOPIC_ARN \
  --region us-east-1 \
  --query 'Subscriptions[*].[Protocol,Endpoint,SubscriptionArn]'

# Send test message
aws sns publish \
  --topic-arn $TOPIC_ARN \
  --subject "Test Alert" \
  --message "Test notification" \
  --region us-east-1
```

### Issue: AccessDeniedException
**Cause**: Missing IAM permissions  
**Solution**:
```bash
# Required permissions:
# - budgets:CreateBudget
# - budgets:ViewBudget
# - budgets:ModifyBudget
# - budgets:DeleteBudget
# - sns:CreateTopic
# - sns:Subscribe
# - sns:Publish
# - aws-portal:ViewBilling

# Verify current permissions
aws iam get-user-policy --user-name YOUR_USERNAME --policy-name BudgetsAccess
```

### Issue: Budget Not Triggering
**Cause**: Spending hasn't reached threshold or delay in data processing  
**Solution**:
```bash
# Check current spending vs budget
aws budgets describe-budget \
  --account-id $ACCOUNT_ID \
  --budget-name $BUDGET_NAME \
  --query 'Budget.CalculatedSpend'

# Note: Budget data updates several times daily, not real-time
# Forecasted alerts may take time to calculate
```

### Issue: Cannot Delete Budget
**Cause**: Notifications must be deleted first  
**Solution**:
```bash
# List all notifications
aws budgets describe-notifications-for-budget \
  --account-id $ACCOUNT_ID \
  --budget-name $BUDGET_NAME

# Delete each notification before deleting budget
# Then delete budget
aws budgets delete-budget \
  --account-id $ACCOUNT_ID \
  --budget-name $BUDGET_NAME
```

---

## Key Takeaways

1. **AWS Budgets** provide proactive cost monitoring and alerting
2. **Multiple thresholds** enable progressive warnings (80%, 90%, 100%)
3. **Forecasted alerts** provide advance warning before overspending
4. **SNS integration** enables flexible notification delivery
5. **Email confirmation** required for email subscriptions
6. **Account-level budgets** help control overall spending
7. **Service-specific budgets** provide granular cost control
8. **Regular review** of budgets ensures they remain relevant

---

## Summary

In this lab, you:
- ✅ Created Amazon SNS topic for budget notifications
- ✅ Configured email subscription with confirmation
- ✅ Created monthly cost budget with spending limit
- ✅ Added multiple alert thresholds (80%, 90%, 100%)
- ✅ Configured forecasted and actual cost notifications
- ✅ Verified budget creation and status
- ✅ Listed all configured notifications
- ✅ Exported budget details to JSON
- ✅ Tested notification delivery
- ✅ Cleaned up all resources

AWS Budgets is an essential tool for cost management, providing automated alerts that help prevent unexpected charges and enable proactive cost control.

---

## End of Lab 16.C

**Next Lab**: Lab 16.D - AWS Well-Architected Review

---
