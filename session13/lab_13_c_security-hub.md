# Lab 13.C: AWS Security Hub - Centralized Security and Compliance Management

## Overview
This lab introduces AWS Security Hub, a unified security and compliance service that aggregates findings from multiple AWS security services. You'll enable Security Hub, activate industry security standards (CIS, FSBP), integrate multiple data sources, analyze compliance posture, remediate findings, and configure automated alerting.

**💰 Cost**: Security Hub: $0.0010 per finding + $0.10 per compliance check. Minimal cost for short lab.

---

## Objectives
- Enable AWS Security Hub with centralized dashboard
- Activate CIS AWS Foundations Benchmark
- Activate AWS Foundational Security Best Practices (FSBP)
- Integrate GuardDuty, AWS Config, IAM Access Analyzer
- Generate and analyze security findings
- Filter findings by severity and compliance status
- View failed security controls
- Remediate common security issues
- Export findings for reporting
- Set up automated remediation with EventBridge

---

## Prerequisites
- AWS CLI configured (`aws configure`)
- IAM permissions for Security Hub, GuardDuty, Config, IAM
- Region: ap-southeast-2
- AWS Config enabled (from Lab 13.A)
- GuardDuty enabled (from Lab 13.B)

---

## Architecture

```
AWS Security Services
├─ GuardDuty (Threat Detection)
├─ AWS Config (Compliance)
├─ IAM Access Analyzer (Permissions)
├─ Inspector (Vulnerability Scanning)
└─ Macie (Data Protection)
          ↓
    AWS Security Hub
    (Centralized Dashboard)
          ↓
  Security Standards
  ├─ CIS Benchmark
  ├─ FSBP
  └─ PCI DSS
          ↓
  Unified Findings
  ├─ Severity Scoring
  ├─ Compliance Status
  └─ Remediation Steps
          ↓
  EventBridge → Automated Response
  SNS → Notifications
```

---

## Step 1 – Set Variables

```bash
# Set region
REGION="ap-southeast-2"
export AWS_REGION="$REGION"
echo "REGION=$REGION"

# Get account ID
ACCOUNT_ID=$(aws sts get-caller-identity \
  --query Account \
  --output text)

echo "ACCOUNT_ID=$ACCOUNT_ID"
echo ""
echo "================================================"
echo "SETTING UP SECURITY HUB"
echo "================================================"
```

---

## Step 2 – Enable Security Hub

```bash
echo ""
echo "Enabling AWS Security Hub..."

# Enable Security Hub
aws securityhub enable-security-hub \
  --region "$REGION" \
  --enable-default-standards

echo ""
echo "✅ Security Hub enabled"
echo "   Default standards automatically enabled"
```

---

## Step 3 – Verify Security Hub Status

```bash
echo ""
echo "Verifying Security Hub configuration..."

# Get Security Hub details
aws securityhub describe-hub \
  --region "$REGION" \
  --query '{HubArn:HubArn,SubscribedAt:SubscribedAt,AutoEnableControls:AutoEnableControls}' \
  --output json

echo ""
echo "✅ Security Hub is active"
```

---

## Step 4 – Enable CIS AWS Foundations Benchmark

```bash
echo ""
echo "================================================"
echo "ENABLING SECURITY STANDARDS"
echo "================================================"
echo ""

# Get CIS standard ARN for region
CIS_STANDARD_ARN="arn:aws:securityhub:${REGION}::standards/cis-aws-foundations-benchmark/v/1.2.0"
echo "CIS_STANDARD_ARN=$CIS_STANDARD_ARN"
echo ""

# Enable CIS benchmark
echo "Enabling CIS AWS Foundations Benchmark v1.2.0..."

aws securityhub batch-enable-standards \
  --standards-subscription-requests "[
    {
      \"StandardsArn\": \"${CIS_STANDARD_ARN}\"
    }
  ]" \
  --region "$REGION"

echo "✅ CIS Benchmark enabled"
echo "   This standard includes 43 automated security checks"
```

---

## Step 5 – Enable AWS Foundational Security Best Practices

```bash
echo ""
echo "Enabling AWS Foundational Security Best Practices (FSBP)..."

# Get FSBP standard ARN
FSBP_STANDARD_ARN="arn:aws:securityhub:${REGION}::standards/aws-foundational-security-best-practices/v/1.0.0"
echo "FSBP_STANDARD_ARN=$FSBP_STANDARD_ARN"
echo ""

# Enable FSBP
aws securityhub batch-enable-standards \
  --standards-subscription-requests "[
    {
      \"StandardsArn\": \"${FSBP_STANDARD_ARN}\"
    }
  ]" \
  --region "$REGION"

echo "✅ FSBP enabled"
echo "   This standard includes 200+ security checks"
echo ""
echo "⏱️  Standards will begin evaluating in 2-5 minutes..."
```

---

## Step 6 – List All Enabled Standards

```bash
echo ""
echo "Listing all enabled security standards..."

# List enabled standards
aws securityhub get-enabled-standards \
  --region "$REGION" \
  --query 'StandardsSubscriptions[*].[StandardsArn,StandardsStatus]' \
  --output table

echo ""
echo "✅ Security standards active"
```

---

## Step 7 – Integrate GuardDuty Findings

```bash
echo ""
echo "================================================"
echo "INTEGRATING SECURITY SERVICES"
echo "================================================"
echo ""

echo "Integrating GuardDuty with Security Hub..."

# Enable GuardDuty product integration
aws securityhub enable-import-findings-for-product \
  --product-arn "arn:aws:securityhub:${REGION}::product/aws/guardduty" \
  --region "$REGION" 2>/dev/null \
  && echo "✅ GuardDuty integration enabled" \
  || echo "GuardDuty integration already enabled"
```

---

## Step 8 – Integrate IAM Access Analyzer

```bash
echo ""
echo "Integrating IAM Access Analyzer..."

# Check if Access Analyzer exists, create if needed
ANALYZER_ARN=$(aws accessanalyzer list-analyzers \
  --region "$REGION" \
  --query 'analyzers[0].arn' \
  --output text 2>/dev/null)

if [ "$ANALYZER_ARN" == "None" ] || [ -z "$ANALYZER_ARN" ]; then
  echo "Creating IAM Access Analyzer..."
  
  aws accessanalyzer create-analyzer \
    --analyzer-name default-analyzer \
    --type ACCOUNT \
    --region "$REGION"
  
  echo "✅ IAM Access Analyzer created"
else
  echo "IAM Access Analyzer already exists"
  echo "ANALYZER_ARN=$ANALYZER_ARN"
fi

echo ""

# Enable Access Analyzer product integration
aws securityhub enable-import-findings-for-product \
  --product-arn "arn:aws:securityhub:${REGION}::product/aws/access-analyzer" \
  --region "$REGION" 2>/dev/null \
  && echo "✅ IAM Access Analyzer integration enabled" \
  || echo "Access Analyzer integration already enabled"
```

---

## Step 9 – Integrate AWS Config

```bash
echo ""
echo "Integrating AWS Config..."

# Enable AWS Config product integration
aws securityhub enable-import-findings-for-product \
  --product-arn "arn:aws:securityhub:${REGION}::product/aws/config" \
  --region "$REGION" 2>/dev/null \
  && echo "✅ AWS Config integration enabled" \
  || echo "Config integration already enabled"

echo ""
echo "All security service integrations complete!"
```

---

## Step 10 – Wait for Initial Assessment

```bash
echo ""
echo "Waiting for Security Hub to perform initial assessment..."
echo "(This takes 2-5 minutes for standards to evaluate controls)"
echo ""

# Wait 2 minutes
sleep 120

echo "✅ Initial assessment period complete"
```

---

## Step 11 – View All Findings

```bash
echo ""
echo "================================================"
echo "ANALYZING SECURITY FINDINGS"
echo "================================================"
echo ""

echo "Retrieving all Security Hub findings..."

# Get all findings
FINDINGS=$(aws securityhub get-findings \
  --region "$REGION" \
  --max-results 50 \
  --query 'Findings[*].[Title,Severity.Label,Compliance.Status,WorkflowState]' \
  --output table)

echo "$FINDINGS"
echo ""
echo "✅ Findings retrieved (showing first 50)"
```

---

## Step 12 – Filter Findings by Severity

```bash
echo ""
echo "================================================"
echo "FILTERING FINDINGS BY SEVERITY"
echo "================================================"
echo ""

# Critical severity
echo "CRITICAL Severity Findings:"
CRITICAL_COUNT=$(aws securityhub get-findings \
  --region "$REGION" \
  --filters '{
    "SeverityLabel": [{"Value": "CRITICAL", "Comparison": "EQUALS"}],
    "WorkflowStatus": [{"Value": "NEW", "Comparison": "EQUALS"}]
  }' \
  --query 'length(Findings)' \
  --output text)

echo "Count: $CRITICAL_COUNT"
echo ""

# High severity
echo "HIGH Severity Findings:"
HIGH_FINDINGS=$(aws securityhub get-findings \
  --region "$REGION" \
  --filters '{
    "SeverityLabel": [{"Value": "HIGH", "Comparison": "EQUALS"}],
    "WorkflowStatus": [{"Value": "NEW", "Comparison": "EQUALS"}]
  }' \
  --query 'Findings[*].[Title,ProductName]' \
  --output table)

HIGH_COUNT=$(aws securityhub get-findings \
  --region "$REGION" \
  --filters '{
    "SeverityLabel": [{"Value": "HIGH", "Comparison": "EQUALS"}],
    "WorkflowStatus": [{"Value": "NEW", "Comparison": "EQUALS"}]
  }' \
  --query 'length(Findings)' \
  --output text)

echo "Count: $HIGH_COUNT"
echo "$HIGH_FINDINGS"
echo ""

# Medium severity
echo "MEDIUM Severity Findings:"
MEDIUM_COUNT=$(aws securityhub get-findings \
  --region "$REGION" \
  --filters '{
    "SeverityLabel": [{"Value": "MEDIUM", "Comparison": "EQUALS"}],
    "WorkflowStatus": [{"Value": "NEW", "Comparison": "EQUALS"}]
  }' \
  --query 'length(Findings)' \
  --output text)

echo "Count: $MEDIUM_COUNT"
echo ""

# Low severity
echo "LOW Severity Findings:"
LOW_COUNT=$(aws securityhub get-findings \
  --region "$REGION" \
  --filters '{
    "SeverityLabel": [{"Value": "LOW", "Comparison": "EQUALS"}],
    "WorkflowStatus": [{"Value": "NEW", "Comparison": "EQUALS"}]
  }' \
  --query 'length(Findings)' \
  --output text)

echo "Count: $LOW_COUNT"
echo ""
echo "✅ Severity breakdown complete"
```

---

## Step 13 – View Failed CIS Controls

```bash
echo ""
echo "================================================"
echo "ANALYZING FAILED CONTROLS"
echo "================================================"
echo ""

echo "CIS AWS Foundations Benchmark - Failed Controls:"
echo ""

# Get subscription ARN
CIS_SUB_ARN=$(aws securityhub get-enabled-standards \
  --region "$REGION" \
  --query 'StandardsSubscriptions[?contains(StandardsArn, `cis-aws-foundations-benchmark`)].StandardsSubscriptionArn' \
  --output text)

if [ ! -z "$CIS_SUB_ARN" ]; then
  echo "CIS_SUB_ARN=$CIS_SUB_ARN"
  echo ""
  
  # List failed controls
  aws securityhub describe-standards-controls \
    --standards-subscription-arn "$CIS_SUB_ARN" \
    --region "$REGION" \
    --query 'Controls[?ControlStatus==`DISABLED` || ControlStatus==`ENABLED`].[ControlId,Title,ControlStatus]' \
    --output table | head -30
  
  echo ""
  echo "✅ CIS controls displayed (first 20)"
else
  echo "CIS standard not fully initialized yet"
fi
```

---

## Step 14 – View Failed FSBP Controls

```bash
echo ""
echo "AWS Foundational Security Best Practices - Failed Controls:"
echo ""

# Get FSBP subscription ARN
FSBP_SUB_ARN=$(aws securityhub get-enabled-standards \
  --region "$REGION" \
  --query 'StandardsSubscriptions[?contains(StandardsArn, `aws-foundational-security-best-practices`)].StandardsSubscriptionArn' \
  --output text)

if [ ! -z "$FSBP_SUB_ARN" ]; then
  echo "FSBP_SUB_ARN=$FSBP_SUB_ARN"
  echo ""
  
  # List failed controls
  aws securityhub describe-standards-controls \
    --standards-subscription-arn "$FSBP_SUB_ARN" \
    --region "$REGION" \
    --query 'Controls[?ControlStatus==`DISABLED` || ControlStatus==`ENABLED`].[ControlId,Title,ControlStatus]' \
    --output table | head -30
  
  echo ""
  echo "✅ FSBP controls displayed (first 20)"
else
  echo "FSBP standard not fully initialized yet"
fi
```

---

## Step 15 – Get Security Score

```bash
echo ""
echo "================================================"
echo "SECURITY POSTURE SUMMARY"
echo "================================================"
echo ""

# Get summary of findings by workflow status
echo "Findings by Workflow Status:"
aws securityhub get-findings \
  --region "$REGION" \
  --query 'Findings[*].WorkflowState' \
  --output text | sort | uniq -c

echo ""

# Get compliance status summary
echo "Findings by Compliance Status:"
aws securityhub get-findings \
  --region "$REGION" \
  --query 'Findings[*].Compliance.Status' \
  --output text | sort | uniq -c

echo ""
echo "✅ Security posture summary complete"
```

---

## Step 16 – Export Findings to JSON

```bash
echo ""
echo "================================================"
echo "EXPORTING FINDINGS"
echo "================================================"
echo ""

# Export all findings to JSON file
echo "Exporting all findings to JSON..."

aws securityhub get-findings \
  --region "$REGION" \
  --max-results 100 \
  --output json > /tmp/securityhub-findings.json

echo "EXPORTED_FILE=/tmp/securityhub-findings.json"
echo ""
echo "Finding summary:"
jq -r '.Findings | group_by(.Severity.Label) | map({severity: .[0].Severity.Label, count: length})' /tmp/securityhub-findings.json 2>/dev/null \
  || echo "Findings exported (install jq for summary)"

echo ""
echo "✅ Findings exported to /tmp/securityhub-findings.json"
```

---

## Step 17 – Remediate Common Security Issues

```bash
echo ""
echo "================================================"
echo "REMEDIATING SECURITY FINDINGS"
echo "================================================"
echo ""

# Example 1: Enable S3 bucket encryption for all buckets
echo "Example Remediation 1: Enabling S3 bucket encryption..."
echo ""

BUCKETS=$(aws s3api list-buckets \
  --region "$REGION" \
  --query 'Buckets[*].Name' \
  --output text)

for BUCKET in $BUCKETS; do
  echo "Checking bucket: $BUCKET"
  
  # Enable encryption
  aws s3api put-bucket-encryption \
    --bucket "$BUCKET" \
    --server-side-encryption-configuration '{
      "Rules": [{
        "ApplyServerSideEncryptionByDefault": {
          "SSEAlgorithm": "AES256"
        },
        "BucketKeyEnabled": true
      }]
    }' \
    --region "$REGION" 2>/dev/null \
    && echo "  ✅ Encryption enabled on $BUCKET" \
    || echo "  ⚠️  Could not enable encryption on $BUCKET (may be in different region)"
done

echo ""
echo "S3 bucket encryption remediation complete"
```

---

## Step 18 – Create EventBridge Rule for Critical Findings

```bash
echo ""
echo "Setting up automated alerting for critical findings..."

# Create EventBridge rule for critical severity findings
aws events put-rule \
  --name security-hub-critical-findings \
  --description "Alert on critical severity Security Hub findings" \
  --event-pattern '{
    "source": ["aws.securityhub"],
    "detail-type": ["Security Hub Findings - Imported"],
    "detail": {
      "findings": {
        "Severity": {
          "Label": ["CRITICAL"]
        }
      }
    }
  }' \
  --region "$REGION"

echo "✅ EventBridge rule created"
echo ""
echo "Note: Add SNS topic or Lambda target to receive alerts"
```

---

## Step 19 – View Security Hub Dashboard URL

```bash
echo ""
echo "================================================"
echo "VIEW SECURITY HUB CONSOLE"
echo "================================================"
echo ""

echo "Access Security Hub dashboard:"
echo ""
echo "https://${REGION}.console.aws.amazon.com/securityhub/home?region=${REGION}#/summary"
echo ""
echo "Key sections to review:"
echo "  - Summary: Overall security posture"
echo "  - Findings: All security issues"
echo "  - Insights: Grouped and analyzed findings"
echo "  - Standards: CIS and FSBP compliance status"
echo "  - Integrations: Connected security services"
```

---

## Step 20 – Cleanup

```bash
echo ""
echo "================================================"
echo "CLEANUP"
echo "================================================"
echo ""

echo "Cleaning up Security Hub resources..."

# Disable all product integrations
echo "Disabling product integrations..."

# List and disable integrations
INTEGRATIONS=$(aws securityhub list-enabled-products-for-import \
  --region "$REGION" \
  --query 'ProductSubscriptions' \
  --output text 2>/dev/null)

if [ ! -z "$INTEGRATIONS" ]; then
  for PRODUCT_ARN in $INTEGRATIONS; do
    aws securityhub disable-import-findings-for-product \
      --product-subscription-arn "$PRODUCT_ARN" \
      --region "$REGION" 2>/dev/null
    echo "  ✅ Disabled: $PRODUCT_ARN"
  done
else
  echo "  No integrations to disable"
fi

echo ""

# Disable security standards
echo "Disabling security standards..."

STANDARD_ARNS=$(aws securityhub get-enabled-standards \
  --region "$REGION" \
  --query 'StandardsSubscriptions[*].StandardsSubscriptionArn' \
  --output text 2>/dev/null)

if [ ! -z "$STANDARD_ARNS" ]; then
  aws securityhub batch-disable-standards \
    --standards-subscription-arns $STANDARD_ARNS \
    --region "$REGION"
  
  echo "✅ Security standards disabled"
else
  echo "No standards to disable"
fi

echo ""

# Delete EventBridge rule
echo "Deleting EventBridge rule..."
aws events remove-targets \
  --rule security-hub-critical-findings \
  --ids "1" \
  --region "$REGION" 2>/dev/null

aws events delete-rule \
  --name security-hub-critical-findings \
  --region "$REGION" 2>/dev/null

echo "✅ EventBridge rule deleted"
echo ""

# Delete IAM Access Analyzer (optional - uncomment to delete)
# echo "Deleting IAM Access Analyzer..."
# ANALYZER_NAME=$(aws accessanalyzer list-analyzers \
#   --region "$REGION" \
#   --query 'analyzers[0].name' \
#   --output text 2>/dev/null)
# 
# if [ "$ANALYZER_NAME" != "None" ] && [ ! -z "$ANALYZER_NAME" ]; then
#   aws accessanalyzer delete-analyzer \
#     --analyzer-name "$ANALYZER_NAME" \
#     --region "$REGION"
#   echo "✅ IAM Access Analyzer deleted"
# fi

# Disable Security Hub
echo "Disabling Security Hub..."
aws securityhub disable-security-hub \
  --region "$REGION"

echo "✅ Security Hub disabled"

# Remove exported files
rm -f /tmp/securityhub-findings.json

echo ""
echo "All Security Hub resources cleaned up!"
```

---

## Summary

In this lab, you have:
- Enabled AWS Security Hub as centralized security dashboard
- Activated CIS AWS Foundations Benchmark (43 checks)
- Activated AWS Foundational Security Best Practices (200+ checks)
- Integrated GuardDuty, AWS Config, and IAM Access Analyzer
- Analyzed security findings by severity and compliance status
- Viewed failed security controls across multiple standards
- Exported findings to JSON for reporting
- Remediated common security issues (S3 encryption)
- Created EventBridge rules for automated alerting
- Generated comprehensive security posture reports

**Key Takeaways:**
- **Unified Dashboard**: Single view for all security findings
- **Multiple Standards**: CIS, FSBP, PCI DSS, HIPAA compliance
- **Automated Collection**: Findings from 40+ AWS and partner services
- **Prioritized Remediation**: Severity-based and compliance-driven
- **Automated Response**: EventBridge integration for real-time action

---

## Best Practices

**Deployment:**
- Enable Security Hub in all accounts and regions
- Use AWS Organizations for centralized management
- Enable all relevant security standards for your industry
- Integrate all available security services

**Monitoring:**
- Review critical and high findings daily
- Set up SNS notifications for critical findings
- Use Security Hub Insights for trend analysis
- Create custom insights for your environment

**Remediation:**
- Prioritize findings by severity and exploitability
- Automate remediation with EventBridge + Lambda
- Document remediation procedures
- Track remediation metrics over time

**Compliance:**
- Map findings to compliance frameworks
- Generate compliance reports regularly
- Suppress accepted risks with proper documentation
- Review control effectiveness quarterly

**Cost Optimization:**
- Disable unnecessary security standards
- Archive old findings (90+ days)
- Use CloudWatch Logs Insights instead of exporting all findings
- Monitor Security Hub costs in Cost Explorer

---

## Troubleshooting

**No findings appear:**
- Wait 5-10 minutes for initial assessment
- Verify AWS Config is enabled and recording
- Check if security standards are enabled
- Ensure product integrations are active

**Standards show NOT_AVAILABLE:**
- Wait for standard initialization (2-5 minutes)
- Verify region supports the standard
- Check IAM permissions for Security Hub
- Ensure dependent services (Config) are enabled

**Controls show DISABLED:**
- Some controls disabled by default for cost
- Enable specific controls if needed
- Review control requirements (may need other services)

**High costs:**
- Review number of findings ingested
- Disable unused security standards
- Archive old findings
- Use finding aggregation for multi-region

**Integration failures:**
- Verify source service is enabled (GuardDuty, Config)
- Check IAM service-linked roles exist
- Ensure region consistency
- Review product subscription ARN format

**Cannot disable Security Hub:**
- First disable all security standards
- Then disable all product integrations
- Finally disable Security Hub
- May need to wait 30 seconds between steps

---

## Additional Resources

- [AWS Security Hub Documentation](https://docs.aws.amazon.com/securityhub/)
- [Security Hub Best Practices](https://docs.aws.amazon.com/securityhub/latest/userguide/securityhub-best-practices.html)
- [CIS AWS Foundations Benchmark](https://docs.aws.amazon.com/securityhub/latest/userguide/securityhub-cis-controls.html)
- [FSBP Standard](https://docs.aws.amazon.com/securityhub/latest/userguide/securityhub-standards-fsbp.html)
- [Automated Response and Remediation](https://docs.aws.amazon.com/securityhub/latest/userguide/securityhub-cloudwatch-events.html)
- [Security Hub Pricing](https://aws.amazon.com/security-hub/pricing/)
