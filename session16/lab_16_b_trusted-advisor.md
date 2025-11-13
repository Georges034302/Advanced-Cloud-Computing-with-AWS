# Lab 16.B: AWS Trusted Advisor – Best Practice Recommendations

## Overview
AWS Trusted Advisor provides real-time guidance to help optimize your AWS infrastructure, improve security and performance, reduce costs, and monitor service quotas. This lab demonstrates how to access Trusted Advisor checks and recommendations using the AWS CLI.

---

## Objectives
- Access AWS Trusted Advisor programmatically
- List all available Trusted Advisor checks
- Retrieve check results and recommendations
- Filter checks by category (security, cost, performance, etc.)
- Identify actionable recommendations
- Export findings for analysis

---

## Prerequisites
- AWS CLI configured
- Region: **us-east-1** (Trusted Advisor API is only available in us-east-1)
- IAM permissions: `support:*`, `trustedadvisor:*`
- **Note**: Full Trusted Advisor requires **Business** or **Enterprise** Support plan
- Basic Support plan has limited checks (7 core checks)

---

## Architecture

```
┌─────────────────────────────────────────────────┐
│         AWS Account Resources                   │
│  (EC2, S3, RDS, IAM, Security Groups, etc.)     │
└─────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────┐
│         AWS Trusted Advisor                     │
│  Automated Best Practice Analysis               │
│                                                 │
│  Five Categories:                               │
│  • Cost Optimization                            │
│  • Performance                                  │
│  • Security                                     │
│  • Fault Tolerance                              │
│  • Service Limits (Service Quotas)             │
└─────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────┐
│         Check Results & Recommendations         │
│                                                 │
│  Status Colors:                                 │
│  🔴 Red (Error) - Action recommended            │
│  🟡 Yellow (Warning) - Investigation suggested  │
│  🟢 Green (OK) - No issues detected             │
└─────────────────────────────────────────────────┘
```

---

# Step 1 – Set Environment Variables

```bash
# Trusted Advisor only works in us-east-1
REGION="us-east-1"
export AWS_REGION="$REGION"

echo "=== Configuration ==="
echo "Region: $REGION"
echo "Note: Trusted Advisor API only available in us-east-1"
echo "====================="
echo ""
```

**Expected Output:**
```
=== Configuration ===
Region: us-east-1
Note: Trusted Advisor API only available in us-east-1
=====================
```

---

# Step 2 – List All Available Trusted Advisor Checks

```bash
# Get all available Trusted Advisor checks
echo "Retrieving all Trusted Advisor checks..."

aws support describe-trusted-advisor-checks \
  --language en \
  --region "$REGION" \
  --query 'checks[*].[name,category,id]' \
  --output table

echo ""
echo "✅ Check list retrieved"
echo ""
```

**Expected Output:**
```
Retrieving all Trusted Advisor checks...
-------------------------------------------------------------------------------------
|                        DescribeTrustedAdvisorChecks                                |
+-----------------------------------------------------------------------------------+
|  Amazon S3 Bucket Permissions                      |  security       |  abc123... |
|  Security Groups - Unrestricted Access             |  security       |  def456... |
|  IAM Use                                           |  security       |  ghi789... |
|  MFA on Root Account                               |  security       |  jkl012... |
|  Low Utilization Amazon EC2 Instances              |  cost           |  mno345... |
|  Underutilized Amazon EBS Volumes                  |  cost           |  pqr678... |
|  Idle Load Balancers                               |  cost           |  stu901... |
|  Amazon RDS Idle DB Instances                      |  cost           |  vwx234... |
|  Amazon EC2 Reserved Instance Optimization         |  cost           |  yza567... |
|  Amazon Route 53 Hosted Zones                      |  cost           |  bcd890... |
+-----------------------------------------------------------------------------------+

✅ Check list retrieved
```

---

# Step 3 – Get Summary of All Checks

```bash
# Retrieve summary status of all checks
echo "Getting summary of all Trusted Advisor checks..."

aws support describe-trusted-advisor-check-summaries \
  --check-ids $(aws support describe-trusted-advisor-checks \
    --language en \
    --region "$REGION" \
    --query 'checks[*].id' \
    --output text) \
  --region "$REGION" \
  --query 'summaries[*].[checkId,status,category]' \
  --output table

echo ""
echo "✅ Check summaries retrieved"
echo ""
```

**Expected Output:**
```
Getting summary of all Trusted Advisor checks...
-------------------------------------------------------------------------------------
|                    DescribeTrustedAdvisorCheckSummaries                            |
+-----------------------------------------------------------------------------------+
|  abc123...  |  ok       |  security                                                |
|  def456...  |  warning  |  security                                                |
|  ghi789...  |  ok       |  security                                                |
|  jkl012...  |  error    |  security                                                |
|  mno345...  |  warning  |  cost_optimizing                                         |
|  pqr678...  |  ok       |  cost_optimizing                                         |
+-----------------------------------------------------------------------------------+

✅ Check summaries retrieved
```

---

# Step 4 – Filter Checks by Category (Security)

```bash
# Get all security-related checks
echo "Filtering security checks..."

aws support describe-trusted-advisor-checks \
  --language en \
  --region "$REGION" \
  --query 'checks[?category==`security`].[name,id]' \
  --output table

echo ""
echo "✅ Security checks filtered"
echo ""
```

**Expected Output:**
```
Filtering security checks...
-------------------------------------------------------------------------------------
|                        DescribeTrustedAdvisorChecks                                |
+-----------------------------------------------------------------------------------+
|  Amazon S3 Bucket Permissions                      |  abc123...                   |
|  Security Groups - Unrestricted Access             |  def456...                   |
|  IAM Use                                           |  ghi789...                   |
|  MFA on Root Account                               |  jkl012...                   |
|  Amazon RDS Security Group Access Risk             |  mno345...                   |
|  IAM Password Policy                               |  pqr678...                   |
|  CloudTrail Logging                                |  stu901...                   |
+-----------------------------------------------------------------------------------+

✅ Security checks filtered
```

---

# Step 5 – Filter Checks by Category (Cost Optimization)

```bash
# Get all cost optimization checks
echo "Filtering cost optimization checks..."

aws support describe-trusted-advisor-checks \
  --language en \
  --region "$REGION" \
  --query 'checks[?category==`cost_optimizing`].[name,id]' \
  --output table

echo ""
echo "✅ Cost optimization checks filtered"
echo ""
```

**Expected Output:**
```
Filtering cost optimization checks...
-------------------------------------------------------------------------------------
|                        DescribeTrustedAdvisorChecks                                |
+-----------------------------------------------------------------------------------+
|  Low Utilization Amazon EC2 Instances              |  mno345...                   |
|  Underutilized Amazon EBS Volumes                  |  pqr678...                   |
|  Idle Load Balancers                               |  stu901...                   |
|  Unassociated Elastic IP Addresses                 |  vwx234...                   |
|  Amazon RDS Idle DB Instances                      |  yza567...                   |
|  Amazon EC2 Reserved Instance Optimization         |  bcd890...                   |
+-----------------------------------------------------------------------------------+

✅ Cost optimization checks filtered
```

---

# Step 6 – Identify Checks with Warnings or Errors

```bash
# Get only checks that have warnings or errors
echo "Identifying checks with warnings or errors..."

aws support describe-trusted-advisor-check-summaries \
  --check-ids $(aws support describe-trusted-advisor-checks \
    --language en \
    --region "$REGION" \
    --query 'checks[*].id' \
    --output text) \
  --region "$REGION" \
  --query 'summaries[?status!=`ok`].[checkId,status,category]' \
  --output table

echo ""
echo "✅ Issues identified"
echo ""
```

**Expected Output:**
```
Identifying checks with warnings or errors...
-------------------------------------------------------------------------------------
|                    DescribeTrustedAdvisorCheckSummaries                            |
+-----------------------------------------------------------------------------------+
|  def456...  |  warning  |  security                                                |
|  jkl012...  |  error    |  security                                                |
|  mno345...  |  warning  |  cost_optimizing                                         |
|  stu901...  |  warning  |  cost_optimizing                                         |
+-----------------------------------------------------------------------------------+

✅ Issues identified
```

---

# Step 7 – Get Detailed Results for a Specific Check

```bash
# Get detailed information for a specific check
# Example: MFA on Root Account check
echo "Getting detailed check results..."

# First, get the check ID for MFA on Root Account
MFA_CHECK_ID=$(aws support describe-trusted-advisor-checks \
  --language en \
  --region "$REGION" \
  --query 'checks[?contains(name, `MFA`) && contains(name, `Root`)].id' \
  --output text)

echo "Check ID: $MFA_CHECK_ID"
echo ""

# Get the detailed results
if [[ -n "$MFA_CHECK_ID" ]]; then
  aws support describe-trusted-advisor-check-result \
    --check-id "$MFA_CHECK_ID" \
    --language en \
    --region "$REGION" \
    --query 'result.[checkId,status,timestamp,flaggedResources]' \
    --output json
  
  echo ""
  echo "✅ Detailed results retrieved"
else
  echo "⚠️  MFA check not available (requires Business/Enterprise support)"
fi

echo ""
```

**Expected Output:**
```
Getting detailed check results...
Check ID: jkl012mno345pqr678

[
  "jkl012mno345pqr678",
  "error",
  "2025-11-13T10:30:00Z",
  [
    {
      "status": "error",
      "region": "us-east-1",
      "resourceId": "root-account",
      "isSuppressed": false,
      "metadata": [
        "Root account",
        "MFA not enabled"
      ]
    }
  ]
]

✅ Detailed results retrieved
```

---

# Step 8 – Refresh a Specific Check

```bash
# Manually refresh a Trusted Advisor check
echo "Refreshing Trusted Advisor checks..."

# Get first check ID
CHECK_ID=$(aws support describe-trusted-advisor-checks \
  --language en \
  --region "$REGION" \
  --query 'checks[0].id' \
  --output text)

echo "Refreshing check: $CHECK_ID"

# Refresh the check
aws support refresh-trusted-advisor-check \
  --check-id "$CHECK_ID" \
  --region "$REGION" \
  --output json

echo ""
echo "✅ Check refresh initiated"
echo "Note: Results may take a few minutes to update"
echo ""
```

**Expected Output:**
```
Refreshing Trusted Advisor checks...
Refreshing check: abc123def456ghi789

{
    "status": {
        "checkId": "abc123def456ghi789",
        "status": "enqueued",
        "millisUntilNextRefreshable": 3600000
    }
}

✅ Check refresh initiated
Note: Results may take a few minutes to update
```

---

# Step 9 – Export All Findings to JSON

```bash
# Export complete Trusted Advisor summary to JSON
echo "Exporting Trusted Advisor findings to JSON..."

aws support describe-trusted-advisor-check-summaries \
  --check-ids $(aws support describe-trusted-advisor-checks \
    --language en \
    --region "$REGION" \
    --query 'checks[*].id' \
    --output text) \
  --region "$REGION" \
  --output json > /tmp/trusted-advisor-summary.json

echo "✅ Data exported to: /tmp/trusted-advisor-summary.json"

# Display file info
echo ""
echo "File size: $(du -h /tmp/trusted-advisor-summary.json | cut -f1)"
echo "Total checks: $(jq '.summaries | length' /tmp/trusted-advisor-summary.json)"
echo ""
```

**Expected Output:**
```
Exporting Trusted Advisor findings to JSON...
✅ Data exported to: /tmp/trusted-advisor-summary.json

File size: 8.5K
Total checks: 47
```

---

# Step 10 – Convert JSON to CSV Format

```bash
# Convert JSON findings to CSV format
echo "Converting findings to CSV format..."

# Create CSV header
echo "CheckID,Status,Category,ResourcesProcessed,ResourcesFlagged,ResourcesIgnored" \
  > /tmp/trusted-advisor-summary.csv

# Extract data and append to CSV
jq -r '.summaries[] | [.checkId, .status, .categorySpecificSummary.cost_optimizing.estimatedMonthlySavings // "N/A", .resourcesSummary.resourcesProcessed // 0, .resourcesSummary.resourcesFlagged // 0, .resourcesSummary.resourcesIgnored // 0] | @csv' \
  /tmp/trusted-advisor-summary.json >> /tmp/trusted-advisor-summary.csv 2>/dev/null || \
jq -r '.summaries[] | [.checkId, .status] | @csv' \
  /tmp/trusted-advisor-summary.json >> /tmp/trusted-advisor-summary.csv

echo "✅ CSV file created: /tmp/trusted-advisor-summary.csv"

# Display CSV preview
echo ""
echo "=== CSV Preview ==="
head -5 /tmp/trusted-advisor-summary.csv
echo "==================="
echo ""
```

**Expected Output:**
```
Converting findings to CSV format...
✅ CSV file created: /tmp/trusted-advisor-summary.csv

=== CSV Preview ===
CheckID,Status,Category,ResourcesProcessed,ResourcesFlagged,ResourcesIgnored
"abc123...","ok"
"def456...","warning"
"ghi789...","ok"
"jkl012...","error"
===================
```

---

# Step 11 – Generate Human-Readable Report

```bash
# Create a formatted text report
echo "Generating human-readable report..."

cat > /tmp/trusted-advisor-report.txt << 'EOF'
============================================
    AWS TRUSTED ADVISOR - STATUS REPORT
============================================

Generated: $(date)

EOF

# Add summary statistics
echo "" >> /tmp/trusted-advisor-report.txt
echo "SUMMARY STATISTICS" >> /tmp/trusted-advisor-report.txt
echo "==================" >> /tmp/trusted-advisor-report.txt

TOTAL_CHECKS=$(jq '.summaries | length' /tmp/trusted-advisor-summary.json)
OK_CHECKS=$(jq '[.summaries[] | select(.status=="ok")] | length' /tmp/trusted-advisor-summary.json)
WARNING_CHECKS=$(jq '[.summaries[] | select(.status=="warning")] | length' /tmp/trusted-advisor-summary.json)
ERROR_CHECKS=$(jq '[.summaries[] | select(.status=="error")] | length' /tmp/trusted-advisor-summary.json)

echo "Total Checks: $TOTAL_CHECKS" >> /tmp/trusted-advisor-report.txt
echo "✅ OK: $OK_CHECKS" >> /tmp/trusted-advisor-report.txt
echo "⚠️  Warnings: $WARNING_CHECKS" >> /tmp/trusted-advisor-report.txt
echo "🔴 Errors: $ERROR_CHECKS" >> /tmp/trusted-advisor-report.txt
echo "" >> /tmp/trusted-advisor-report.txt

# Add issues requiring attention
echo "ISSUES REQUIRING ATTENTION" >> /tmp/trusted-advisor-report.txt
echo "==========================" >> /tmp/trusted-advisor-report.txt
echo "" >> /tmp/trusted-advisor-report.txt

jq -r '.summaries[] | select(.status != "ok") | "Status: \(.status | ascii_upcase)\nCheck ID: \(.checkId)\n---"' \
  /tmp/trusted-advisor-summary.json >> /tmp/trusted-advisor-report.txt

echo "✅ Report generated: /tmp/trusted-advisor-report.txt"

# Display report
echo ""
echo "=== Report Preview ==="
cat /tmp/trusted-advisor-report.txt
echo "======================"
echo ""
```

**Expected Output:**
```
Generating human-readable report...
✅ Report generated: /tmp/trusted-advisor-report.txt

=== Report Preview ===
============================================
    AWS TRUSTED ADVISOR - STATUS REPORT
============================================

Generated: Wed Nov 13 10:30:00 UTC 2025

SUMMARY STATISTICS
==================
Total Checks: 47
✅ OK: 38
⚠️  Warnings: 6
🔴 Errors: 3

ISSUES REQUIRING ATTENTION
==========================

Status: WARNING
Check ID: def456...
---
Status: ERROR
Check ID: jkl012...
---
Status: WARNING
Check ID: mno345...
---
======================
```

---

# Step 12 – Cleanup

```bash
# Clean up temporary files
echo "Cleaning up temporary files..."

rm -f /tmp/trusted-advisor-summary.json
rm -f /tmp/trusted-advisor-summary.csv
rm -f /tmp/trusted-advisor-report.txt

echo "✅ Temporary files removed"
echo ""
echo "Note: Trusted Advisor data is retained in AWS and not deleted"
echo ""
```

**Expected Output:**
```
Cleaning up temporary files...
✅ Temporary files removed

Note: Trusted Advisor data is retained in AWS and not deleted
```

---

## Best Practices

### Security Recommendations
- **Enable MFA** on root account and all IAM users
- **Review security groups** - remove unrestricted access (0.0.0.0/0)
- **Check S3 bucket permissions** - ensure buckets are not publicly accessible
- **Enable CloudTrail** in all regions for audit logging
- **Use IAM password policies** with strong requirements
- **Review IAM roles** for least privilege access

### Cost Optimization Recommendations
- **Terminate idle resources** - EC2 instances, RDS databases, load balancers
- **Delete unattached EBS volumes** to reduce storage costs
- **Release unused Elastic IPs** to avoid charges
- **Right-size EC2 instances** based on utilization metrics
- **Use Reserved Instances** or Savings Plans for predictable workloads
- **Enable S3 lifecycle policies** to transition data to cheaper storage classes

### Performance Recommendations
- **Use CloudFront** for content delivery and caching
- **Enable EBS optimization** for high I/O workloads
- **Use Provisioned IOPS** for database workloads requiring consistent performance
- **Implement Auto Scaling** for variable workloads

### Fault Tolerance Recommendations
- **Enable Multi-AZ** for RDS databases
- **Distribute ELB** across multiple availability zones
- **Use Amazon Aurora** for high-availability database workloads
- **Configure RDS backups** with appropriate retention periods
- **Enable versioning** on critical S3 buckets

### Service Limits/Quotas
- **Monitor service quotas** to avoid hitting limits
- **Request limit increases** proactively for growing workloads
- **Set up CloudWatch alarms** for quota utilization

---

## Troubleshooting

### Issue: SubscriptionRequiredException
**Cause**: Trusted Advisor full access requires Business or Enterprise Support plan  
**Solution**:
```bash
# Basic support includes only 7 core checks:
# - Service limits (all services)
# - Security group - specific ports unrestricted
# - IAM Use
# - MFA on Root Account
# - EBS public snapshots
# - RDS public snapshots
# - S3 bucket permissions

# For full access, upgrade support plan:
# Business Support: $100+/month
# Enterprise Support: $15,000+/month
```

### Issue: AccessDeniedException
**Cause**: Missing IAM permissions  
**Solution**:
```bash
# Required permissions:
# - support:DescribeTrustedAdvisorChecks
# - support:DescribeTrustedAdvisorCheckResult
# - support:DescribeTrustedAdvisorCheckSummaries
# - support:RefreshTrustedAdvisorCheck

# Verify permissions:
aws iam get-user-policy --user-name YOUR_USERNAME --policy-name TrustedAdvisorAccess
```

### Issue: Check Refresh Rate Limit
**Cause**: Checks can only be refreshed once per hour  
**Solution**:
```bash
# Wait for the refresh cooldown period
# Check when next refresh is available:
aws support describe-trusted-advisor-check-refresh-statuses \
  --check-ids CHECK_ID \
  --region us-east-1
```

### Issue: jq Command Not Found
**Cause**: jq not installed  
**Solution**:
```bash
# Ubuntu/Debian:
sudo apt-get update && sudo apt-get install -y jq

# macOS:
brew install jq

# Amazon Linux/RHEL/CentOS:
sudo yum install -y jq
```

---

## Key Takeaways

1. **Trusted Advisor** provides automated best practice recommendations
2. **Five categories** cover security, cost, performance, fault tolerance, and service limits
3. **Business/Enterprise Support** required for full access to all checks
4. **Regular reviews** help maintain optimal AWS environment
5. **API access** enables automation and integration with monitoring tools
6. **Immediate value** from identifying quick wins (idle resources, security issues)
7. **Proactive monitoring** prevents issues before they impact operations

---

## Summary

In this lab, you:
- ✅ Accessed AWS Trusted Advisor programmatically via CLI
- ✅ Listed all available Trusted Advisor checks
- ✅ Retrieved check summaries and detailed results
- ✅ Filtered checks by category (security, cost, performance)
- ✅ Identified checks with warnings or errors
- ✅ Refreshed specific checks for latest data
- ✅ Exported findings to JSON and CSV formats
- ✅ Generated human-readable reports for analysis

AWS Trusted Advisor is a valuable tool for maintaining a well-architected AWS environment, providing actionable recommendations to optimize costs, improve security, and enhance performance.

---

## End of Lab 16.B

**Next Lab**: Lab 16.C - AWS Budgets

---
