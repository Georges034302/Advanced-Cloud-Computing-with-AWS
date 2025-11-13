# Lab 16.A: AWS Cost Explorer – Analyze Cloud Spending

## Overview
AWS Cost Explorer helps you visualize, understand, and manage AWS costs over time. This lab demonstrates how to analyze spending patterns, identify cost drivers, and generate reports using the Cost Explorer API via AWS CLI.

---

## Objectives
- Enable AWS Cost Explorer
- Analyze daily and monthly costs
- Break down costs by service and region
- Identify top cost contributors
- Generate cost forecasts
- Export cost data for analysis

---

## Prerequisites
- AWS CLI configured with billing access
- IAM permissions: `ce:*`, `aws-portal:ViewBilling`, `aws-portal:ViewUsage`
- Note: Cost Explorer is a **global service** (not region-specific)
- Cost data may take 24 hours to appear for new accounts

---

## Architecture

```
┌─────────────────────────────────────────────────┐
│         AWS Cost & Usage Data                   │
│  (Collected from all AWS services and regions)  │
└─────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────┐
│         AWS Cost Explorer API                   │
│  - Query historical costs                       │
│  - Filter by service, region, tags              │
│  - Aggregate by day, month, or year             │
│  - Generate forecasts                           │
└─────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────┐
│         Cost Analysis & Reports                 │
│  • Total costs by time period                   │
│  • Breakdown by service (EC2, S3, Lambda, etc)  │
│  • Breakdown by region                          │
│  • Usage type analysis                          │
│  • Top cost contributors                        │
│  • Future cost forecasts                        │
└─────────────────────────────────────────────────┘
```

---

# Step 1 – Set Environment Variables

```bash
# Set date ranges for cost analysis
# Last 7 days for daily analysis
START_DATE=$(date -u -d '7 days ago' +%Y-%m-%d)
END_DATE=$(date -u +%Y-%m-%d)

# Last 90 days for monthly analysis
START_DATE_90=$(date -u -d '90 days ago' +%Y-%m-%d)

# Next 7 days for forecasting
FORECAST_END=$(date -u -d '7 days' +%Y-%m-%d)

# Echo variables for verification
echo "=== Date Configuration ==="
echo "Daily Analysis Period:"
echo "  Start: $START_DATE"
echo "  End: $END_DATE"
echo ""
echo "Monthly Analysis Period:"
echo "  Start: $START_DATE_90"
echo "  End: $END_DATE"
echo ""
echo "Forecast Period:"
echo "  Start: $END_DATE"
echo "  End: $FORECAST_END"
echo "=========================="
echo ""
```

**Expected Output:**
```
=== Date Configuration ===
Daily Analysis Period:
  Start: 2025-11-06
  End: 2025-11-13

Monthly Analysis Period:
  Start: 2025-08-15
  End: 2025-11-13

Forecast Period:
  Start: 2025-11-13
  End: 2025-11-20
==========================
```

---

# Step 2 – Enable Cost Explorer (If Not Already Enabled)

```bash
# Enable Cost Explorer (only needs to be done once)
echo "Enabling Cost Explorer..."

aws ce get-cost-and-usage \
  --time-period Start="$START_DATE",End="$END_DATE" \
  --granularity DAILY \
  --metrics "UnblendedCost" \
  --query 'ResultsByTime[0]' \
  --output json > /dev/null 2>&1

if [[ $? -eq 0 ]]; then
  echo "✅ Cost Explorer is enabled and accessible"
else
  echo "⚠️  Cost Explorer may need to be enabled via AWS Console"
  echo "   Go to: Billing Dashboard → Cost Explorer → Enable Cost Explorer"
  echo "   Note: Data may take 24 hours to populate for new accounts"
fi

echo ""
```

**Expected Output:**
```
Enabling Cost Explorer...
✅ Cost Explorer is enabled and accessible
```

---

# Step 3 – Get Daily Costs (Last 7 Days)

```bash
# Retrieve daily cost breakdown
echo "Retrieving daily costs for the last 7 days..."

aws ce get-cost-and-usage \
  --time-period Start="$START_DATE",End="$END_DATE" \
  --granularity DAILY \
  --metrics "UnblendedCost" \
  --query 'ResultsByTime[*].[TimePeriod.Start,Total.UnblendedCost.Amount,Total.UnblendedCost.Unit]' \
  --output table

echo ""
echo "✅ Daily cost analysis complete"
echo ""
```

**Expected Output:**
```
Retrieving daily costs for the last 7 days...
---------------------------------------------------------
|                  GetCostAndUsage                       |
+-------------------------------------------------------+
|  2025-11-06  |  12.45  |  USD                         |
|  2025-11-07  |  14.23  |  USD                         |
|  2025-11-08  |  13.87  |  USD                         |
|  2025-11-09  |  15.62  |  USD                         |
|  2025-11-10  |  11.98  |  USD                         |
|  2025-11-11  |  16.34  |  USD                         |
|  2025-11-12  |  14.76  |  USD                         |
+-------------------------------------------------------+

✅ Daily cost analysis complete
```

---

# Step 4 – Get Monthly Costs (Last 3 Months)

```bash
# Retrieve monthly cost breakdown
echo "Retrieving monthly costs for the last 3 months..."

aws ce get-cost-and-usage \
  --time-period Start="$START_DATE_90",End="$END_DATE" \
  --granularity MONTHLY \
  --metrics "UnblendedCost" \
  --query 'ResultsByTime[*].[TimePeriod.Start,Total.UnblendedCost.Amount,Total.UnblendedCost.Unit]' \
  --output table

echo ""
echo "✅ Monthly cost analysis complete"
echo ""
```

**Expected Output:**
```
Retrieving monthly costs for the last 3 months...
---------------------------------------------------------
|                  GetCostAndUsage                       |
+-------------------------------------------------------+
|  2025-09-01  |  345.67  |  USD                        |
|  2025-10-01  |  412.89  |  USD                        |
|  2025-11-01  |  398.45  |  USD                        |
+-------------------------------------------------------+

✅ Monthly cost analysis complete
```

---

# Step 5 – Break Down Costs by Service

```bash
# Get cost breakdown by AWS service
echo "Analyzing costs by service..."

aws ce get-cost-and-usage \
  --time-period Start="$START_DATE",End="$END_DATE" \
  --granularity MONTHLY \
  --metrics "UnblendedCost" \
  --group-by Type=DIMENSION,Key=SERVICE \
  --query 'ResultsByTime[0].Groups[*].[Keys[0],Metrics.UnblendedCost.Amount]' \
  --output table

echo ""
echo "✅ Service breakdown complete"
echo ""
```

**Expected Output:**
```
Analyzing costs by service...
---------------------------------------------------------
|                  GetCostAndUsage                       |
+-------------------------------------------------------+
|  Amazon Elastic Compute Cloud - Compute  |  156.23   |
|  Amazon Simple Storage Service           |   45.67   |
|  Amazon Relational Database Service      |   89.34   |
|  AWS Lambda                              |   12.45   |
|  Amazon DynamoDB                         |   23.56   |
|  Amazon CloudFront                       |   18.90   |
|  AWS Data Transfer                       |   34.12   |
+-------------------------------------------------------+

✅ Service breakdown complete
```

---

# Step 6 – Identify Top 5 Most Expensive Services

```bash
# Find the top 5 services by cost
echo "Identifying top 5 most expensive services..."

aws ce get-cost-and-usage \
  --time-period Start="$START_DATE",End="$END_DATE" \
  --granularity MONTHLY \
  --metrics "UnblendedCost" \
  --group-by Type=DIMENSION,Key=SERVICE \
  --query 'ResultsByTime[0].Groups | sort_by(@, &Metrics.UnblendedCost.Amount) | reverse(@)[0:5].[Keys[0],Metrics.UnblendedCost.Amount]' \
  --output table

echo ""
echo "✅ Top 5 services identified"
echo ""
```

**Expected Output:**
```
Identifying top 5 most expensive services...
---------------------------------------------------------
|                  GetCostAndUsage                       |
+-------------------------------------------------------+
|  Amazon Elastic Compute Cloud - Compute  |  156.23   |
|  Amazon Relational Database Service      |   89.34   |
|  Amazon Simple Storage Service           |   45.67   |
|  AWS Data Transfer                       |   34.12   |
|  Amazon DynamoDB                         |   23.56   |
+-------------------------------------------------------+

✅ Top 5 services identified
```

---

# Step 7 – Break Down Costs by Region

```bash
# Get cost breakdown by AWS region
echo "Analyzing costs by region..."

aws ce get-cost-and-usage \
  --time-period Start="$START_DATE",End="$END_DATE" \
  --granularity MONTHLY \
  --metrics "UnblendedCost" \
  --group-by Type=DIMENSION,Key=REGION \
  --query 'ResultsByTime[0].Groups[*].[Keys[0],Metrics.UnblendedCost.Amount]' \
  --output table

echo ""
echo "✅ Region breakdown complete"
echo ""
```

**Expected Output:**
```
Analyzing costs by region...
---------------------------------------------------------
|                  GetCostAndUsage                       |
+-------------------------------------------------------+
|  ap-southeast-2                          |  245.67   |
|  us-east-1                               |  123.45   |
|  eu-west-1                               |   67.89   |
|  global                                  |   45.23   |
+-------------------------------------------------------+

✅ Region breakdown complete
```

---

# Step 8 – Analyze Costs by Usage Type

```bash
# Get detailed usage type breakdown
echo "Analyzing costs by usage type..."

aws ce get-cost-and-usage \
  --time-period Start="$START_DATE",End="$END_DATE" \
  --granularity MONTHLY \
  --metrics "UnblendedCost" \
  --group-by Type=DIMENSION,Key=USAGE_TYPE \
  --query 'ResultsByTime[0].Groups | sort_by(@, &Metrics.UnblendedCost.Amount) | reverse(@)[0:10].[Keys[0],Metrics.UnblendedCost.Amount]' \
  --output table

echo ""
echo "✅ Usage type analysis complete"
echo ""
```

**Expected Output:**
```
Analyzing costs by usage type...
---------------------------------------------------------
|                  GetCostAndUsage                       |
+-------------------------------------------------------+
|  APS2-BoxUsage:t3.medium                 |   78.45   |
|  APS2-EBS:VolumeUsage.gp3                |   34.56   |
|  APS2-DataTransfer-Out-Bytes             |   23.12   |
|  APS2-Lambda-GB-Second                   |   12.34   |
|  APS2-Requests-Tier1                     |    8.90   |
+-------------------------------------------------------+

✅ Usage type analysis complete
```

---

# Step 9 – Generate Cost Forecast (Next 7 Days)

```bash
# Get cost forecast for the next 7 days
echo "Generating cost forecast for the next 7 days..."

aws ce get-cost-forecast \
  --time-period Start="$END_DATE",End="$FORECAST_END" \
  --metric UNBLENDED_COST \
  --granularity DAILY \
  --query '[MeanValue,PredictionIntervalLowerBound,PredictionIntervalUpperBound]' \
  --output table

echo ""
echo "Note: Forecast is based on historical spending patterns"
echo "✅ Cost forecast generated"
echo ""
```

**Expected Output:**
```
Generating cost forecast for the next 7 days...
---------------------------------------------------------
|                  GetCostForecast                       |
+-------------------------------------------------------+
|  Mean Value: 98.45 USD                                |
|  Lower Bound: 85.23 USD                               |
|  Upper Bound: 112.67 USD                              |
+-------------------------------------------------------+

Note: Forecast is based on historical spending patterns
✅ Cost forecast generated
```

---

# Step 10 – Export Cost Data to JSON

```bash
# Export daily cost data to JSON file
echo "Exporting daily cost data to JSON..."

aws ce get-cost-and-usage \
  --time-period Start="$START_DATE",End="$END_DATE" \
  --granularity DAILY \
  --metrics "UnblendedCost" \
  --output json > /tmp/daily-costs.json

echo "✅ Data exported to: /tmp/daily-costs.json"

# Display file info
echo ""
echo "File size: $(du -h /tmp/daily-costs.json | cut -f1)"
echo "Records: $(jq '.ResultsByTime | length' /tmp/daily-costs.json)"
echo ""
```

**Expected Output:**
```
Exporting daily cost data to JSON...
✅ Data exported to: /tmp/daily-costs.json

File size: 2.3K
Records: 7
```

---

# Step 11 – Convert JSON to CSV Format

```bash
# Convert JSON to CSV for spreadsheet analysis
echo "Converting cost data to CSV format..."

echo "Date,Cost (USD)" > /tmp/daily-costs.csv

jq -r '.ResultsByTime[] | [.TimePeriod.Start, .Total.UnblendedCost.Amount] | @csv' \
  /tmp/daily-costs.json >> /tmp/daily-costs.csv

echo "✅ CSV file created: /tmp/daily-costs.csv"

# Display CSV contents
echo ""
echo "=== CSV Preview ==="
head -5 /tmp/daily-costs.csv
echo "==================="
echo ""
```

**Expected Output:**
```
Converting cost data to CSV format...
✅ CSV file created: /tmp/daily-costs.csv

=== CSV Preview ===
Date,Cost (USD)
"2025-11-06","12.45"
"2025-11-07","14.23"
"2025-11-08","13.87"
"2025-11-09","15.62"
===================
```

---

# Step 12 – Get Cost Summary Report

```bash
# Generate comprehensive cost summary
echo "Generating cost summary report..."
echo ""

# Get total cost for the period
TOTAL_COST=$(aws ce get-cost-and-usage \
  --time-period Start="$START_DATE",End="$END_DATE" \
  --granularity MONTHLY \
  --metrics "UnblendedCost" \
  --query 'ResultsByTime[0].Total.UnblendedCost.Amount' \
  --output text)

# Get average daily cost
DAILY_COSTS=$(aws ce get-cost-and-usage \
  --time-period Start="$START_DATE",End="$END_DATE" \
  --granularity DAILY \
  --metrics "UnblendedCost" \
  --query 'ResultsByTime[*].Total.UnblendedCost.Amount' \
  --output text)

# Calculate average
TOTAL=0
COUNT=0
for cost in $DAILY_COSTS; do
  TOTAL=$(echo "$TOTAL + $cost" | bc)
  COUNT=$((COUNT + 1))
done
AVG_DAILY=$(echo "scale=2; $TOTAL / $COUNT" | bc)

# Display summary
echo "======================================="
echo "       AWS COST SUMMARY REPORT         "
echo "======================================="
echo ""
echo "Analysis Period: $START_DATE to $END_DATE"
echo ""
echo "Total Cost: \$${TOTAL_COST} USD"
echo "Average Daily Cost: \$${AVG_DAILY} USD"
echo "Number of Days: $COUNT"
echo ""
echo "======================================="
echo ""
echo "✅ Summary report generated"
echo ""
```

**Expected Output:**
```
Generating cost summary report...

=======================================
       AWS COST SUMMARY REPORT         
=======================================

Analysis Period: 2025-11-06 to 2025-11-13

Total Cost: $99.25 USD
Average Daily Cost: $14.18 USD
Number of Days: 7

=======================================

✅ Summary report generated
```

---

# Step 13 – Cleanup

```bash
# Clean up temporary files
echo "Cleaning up temporary files..."

rm -f /tmp/daily-costs.json
rm -f /tmp/daily-costs.csv

echo "✅ Temporary files removed"
echo ""
echo "Note: Cost Explorer data is retained in AWS and not deleted"
echo ""
```

**Expected Output:**
```
Cleaning up temporary files...
✅ Temporary files removed

Note: Cost Explorer data is retained in AWS and not deleted
```

---

## Best Practices

### Cost Optimization
- **Tag resources** for detailed cost allocation and tracking
- **Use Cost Categories** to organize costs by department, project, or environment
- **Enable anomaly detection** to identify unexpected cost spikes
- **Set up AWS Budgets** with alerts for cost thresholds
- **Review recommendations** from AWS Trusted Advisor

### Reserved Instances & Savings Plans
- Purchase **Reserved Instances** for predictable EC2/RDS workloads
- Use **Savings Plans** for flexible compute savings
- Regularly review and adjust commitments based on usage patterns

### Resource Management
- **Right-size** instances based on actual utilization
- **Stop or terminate** unused resources (EC2 instances, RDS databases)
- **Use S3 lifecycle policies** to move data to cheaper storage classes
- **Enable S3 Intelligent-Tiering** for automatic cost optimization
- **Delete unused EBS volumes** and old snapshots

### Monitoring & Reporting
- Schedule regular cost reviews (weekly/monthly)
- Create custom cost reports for stakeholders
- Use Cost Explorer filters to drill down into specific services
- Set up CloudWatch billing alarms for proactive monitoring

---

## Troubleshooting

### Issue: AccessDeniedException
**Cause**: Missing IAM permissions for Cost Explorer or billing  
**Solution**:
```bash
# Verify IAM permissions
aws iam get-user --query 'User.Arn'

# Required permissions:
# - ce:GetCostAndUsage
# - ce:GetCostForecast
# - aws-portal:ViewBilling
# - aws-portal:ViewUsage
```

### Issue: No Data Returned
**Cause**: Cost Explorer not enabled or no usage data available  
**Solution**:
- Enable Cost Explorer via AWS Console (Billing Dashboard → Cost Explorer)
- Wait 24 hours for data to populate (for new accounts)
- Verify you have actual AWS resource usage generating costs

### Issue: Forecast Returns Error
**Cause**: Insufficient historical data (requires at least 32 days)  
**Solution**:
```bash
# Check if you have enough historical data
aws ce get-cost-and-usage \
  --time-period Start=$(date -u -d '32 days ago' +%Y-%m-%d),End=$(date -u +%Y-%m-%d) \
  --granularity MONTHLY \
  --metrics "UnblendedCost"
```

### Issue: date Command Fails on macOS
**Cause**: Different date command syntax on macOS vs Linux  
**Solution**:
```bash
# For macOS, use -v flag:
START_DATE=$(date -v-7d +%Y-%m-%d)

# For Linux, use -d flag:
START_DATE=$(date -d '7 days ago' +%Y-%m-%d)
```

---

## Key Takeaways

1. **Cost Explorer** provides comprehensive visibility into AWS spending
2. **Daily granularity** helps identify day-to-day cost patterns
3. **Service breakdown** shows which AWS services cost the most
4. **Regional analysis** helps optimize data transfer and service placement
5. **Forecasting** enables proactive budget management
6. **Export capabilities** allow integration with external analysis tools
7. **Regular monitoring** is essential for cost control and optimization

---

## Summary

In this lab, you:
- ✅ Enabled and accessed AWS Cost Explorer
- ✅ Analyzed daily and monthly cost trends
- ✅ Identified cost breakdown by service, region, and usage type
- ✅ Found top cost contributors
- ✅ Generated cost forecasts for future planning
- ✅ Exported cost data for external analysis

AWS Cost Explorer is essential for understanding and managing cloud spending, enabling informed decisions about resource usage and optimization opportunities.

---

