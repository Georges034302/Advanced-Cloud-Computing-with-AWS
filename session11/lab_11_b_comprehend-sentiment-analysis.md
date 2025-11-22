# Lab 11.B: Amazon Comprehend - Text Sentiment Analysis

## Overview
This lab introduces Amazon Comprehend for natural language processing (NLP) without requiring ML expertise. You'll analyze text sentiment, detect entities (people, places, organizations), identify key phrases, detect language, perform syntax analysis, and extract insights from customer reviews and social media posts.

---

## Objectives
- Analyze sentiment in text (positive, negative, neutral, mixed)
- Detect named entities (people, places, organizations, dates)
- Extract key phrases from text
- Detect dominant language automatically
- Perform syntax analysis (parts of speech)
- Analyze customer reviews at scale
- Test batch text analysis

---

## Prerequisites
- AWS CLI configured (`aws configure`)
- IAM permissions for Comprehend, S3
- Region: ap-southeast-2
- Python 3.x installed

---

## Architecture

```
Text Input (Reviews, Social Media, Documents)
             ↓
    Amazon Comprehend API
             ↓
        NLP Analysis
   - Sentiment
   - Entities
   - Key Phrases
   - Language Detection
   - Syntax
```

---

## Step 1 – Set Variables

```bash
# Set region
REGION="ap-southeast-2"
export AWS_REGION="$REGION"
echo "REGION=$REGION"

# Get account ID
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo "ACCOUNT_ID=$ACCOUNT_ID"
```

---

## Step 2 – Analyze Sentiment - Positive Review

```bash
echo ""
echo "================================================"
echo "SENTIMENT ANALYSIS - Positive Review"
echo "================================================"
echo ""

POSITIVE_TEXT="I absolutely love this product! The quality is excellent and the customer service was outstanding. Highly recommend to everyone. Best purchase I've made this year!"

echo "Text: $POSITIVE_TEXT"
echo ""

# Analyze sentiment
aws comprehend detect-sentiment \
  --text "$POSITIVE_TEXT" \
  --language-code en \
  --region "$REGION" \
  --query '{
    Sentiment:Sentiment,
    Positive:SentimentScore.Positive,
    Negative:SentimentScore.Negative,
    Neutral:SentimentScore.Neutral,
    Mixed:SentimentScore.Mixed
  }' \
  --output table

echo ""
echo "✅ Sentiment: POSITIVE detected"
```

---

## Step 3 – Analyze Sentiment - Negative Review

```bash
echo ""
echo "================================================"
echo "SENTIMENT ANALYSIS - Negative Review"
echo "================================================"
echo ""

NEGATIVE_TEXT="This is the worst product I've ever purchased. Poor quality, terrible customer service, and completely overpriced. Total waste of money. Very disappointed!"

echo "Text: $NEGATIVE_TEXT"
echo ""

# Analyze sentiment
aws comprehend detect-sentiment \
  --text "$NEGATIVE_TEXT" \
  --language-code en \
  --region "$REGION" \
  --query '{
    Sentiment:Sentiment,
    Positive:SentimentScore.Positive,
    Negative:SentimentScore.Negative,
    Neutral:SentimentScore.Neutral,
    Mixed:SentimentScore.Mixed
  }' \
  --output table

echo ""
echo "✅ Sentiment: NEGATIVE detected"
```

---

## Step 4 – Analyze Sentiment - Mixed Review

```bash
echo ""
echo "================================================"
echo "SENTIMENT ANALYSIS - Mixed Review"
echo "================================================"
echo ""

MIXED_TEXT="The product has some great features and works well most of the time. However, the price is too high and customer support could be better. Overall, it's okay but not perfect."

echo "Text: $MIXED_TEXT"
echo ""

# Analyze sentiment
aws comprehend detect-sentiment \
  --text "$MIXED_TEXT" \
  --language-code en \
  --region "$REGION" \
  --query '{
    Sentiment:Sentiment,
    Positive:SentimentScore.Positive,
    Negative:SentimentScore.Negative,
    Neutral:SentimentScore.Neutral,
    Mixed:SentimentScore.Mixed
  }' \
  --output table

echo ""
echo "✅ Sentiment: MIXED detected"
```

---

## Step 5 – Detect Entities (Named Entity Recognition)

```bash
echo ""
echo "================================================"
echo "ENTITY DETECTION"
echo "================================================"
echo ""

ENTITY_TEXT="Amazon Web Services was founded by Jeff Bezos in Seattle, Washington in 2006. The company's headquarters is located in Arlington, Virginia. AWS offers over 200 services including Amazon S3, Lambda, and EC2."

echo "Text: $ENTITY_TEXT"
echo ""

# Detect entities
aws comprehend detect-entities \
  --text "$ENTITY_TEXT" \
  --language-code en \
  --region "$REGION" \
  --query 'Entities[*].{Entity:Text,Type:Type,Score:Score}' \
  --output table

echo ""
echo "✅ Entities detected: PERSON, LOCATION, ORGANIZATION, DATE"
```

---

## Step 6 – Extract Key Phrases

```bash
echo ""
echo "================================================"
echo "KEY PHRASE EXTRACTION"
echo "================================================"
echo ""

KEYPHRASE_TEXT="Machine learning and artificial intelligence are transforming the technology industry. Companies are investing heavily in cloud computing and data analytics to gain competitive advantages in the digital economy."

echo "Text: $KEYPHRASE_TEXT"
echo ""

# Extract key phrases
aws comprehend detect-key-phrases \
  --text "$KEYPHRASE_TEXT" \
  --language-code en \
  --region "$REGION" \
  --query 'KeyPhrases[*].{Phrase:Text,Score:Score}' \
  --output table

echo ""
echo "✅ Key phrases extracted"
```

---

## Step 7 – Detect Dominant Language

```bash
echo ""
echo "================================================"
echo "LANGUAGE DETECTION"
echo "================================================"
echo ""

# English text
ENGLISH_TEXT="This is a sample text in English to test language detection."

# French text
FRENCH_TEXT="Ceci est un exemple de texte en français pour tester la détection de langue."

# Spanish text
SPANISH_TEXT="Este es un texto de ejemplo en español para probar la detección de idioma."

echo "Testing multiple languages..."
echo ""

# Detect English
echo "Text 1: $ENGLISH_TEXT"
aws comprehend detect-dominant-language \
  --text "$ENGLISH_TEXT" \
  --region "$REGION" \
  --query 'Languages[0].{Language:LanguageCode,Score:Score}' \
  --output table

echo ""

# Detect French
echo "Text 2: $FRENCH_TEXT"
aws comprehend detect-dominant-language \
  --text "$FRENCH_TEXT" \
  --region "$REGION" \
  --query 'Languages[0].{Language:LanguageCode,Score:Score}' \
  --output table

echo ""

# Detect Spanish
echo "Text 3: $SPANISH_TEXT"
aws comprehend detect-dominant-language \
  --text "$SPANISH_TEXT" \
  --region "$REGION" \
  --query 'Languages[0].{Language:LanguageCode,Score:Score}' \
  --output table

echo ""
echo "✅ Languages detected: en (English), fr (French), es (Spanish)"
```

---

## Step 8 – Perform Syntax Analysis

```bash
echo ""
echo "================================================"
echo "SYNTAX ANALYSIS (Parts of Speech)"
echo "================================================"
echo ""

SYNTAX_TEXT="The quick brown fox jumps over the lazy dog."

echo "Text: $SYNTAX_TEXT"
echo ""

# Detect syntax (parts of speech)
aws comprehend detect-syntax \
  --text "$SYNTAX_TEXT" \
  --language-code en \
  --region "$REGION" \
  --query 'SyntaxTokens[*].{Word:Text,PartOfSpeech:PartOfSpeech.Tag}' \
  --output table

echo ""
echo "✅ Syntax analysis complete (DET=Determiner, ADJ=Adjective, NOUN=Noun, VERB=Verb)"
```

---

## Step 9 – Create Sample Customer Reviews File

```bash
echo ""
echo "Creating sample customer reviews..."

# Get repository root directory
REPO_DIR=$(git rev-parse --show-toplevel)

# Create comprehend directory in repository
mkdir -p "$REPO_DIR/comprehend-demo"
cd "$REPO_DIR/comprehend-demo"

cat > reviews.json <<'EOF'
[
  {
    "id": 1,
    "text": "Excellent product! Works perfectly and exceeded my expectations. Fast shipping too!"
  },
  {
    "id": 2,
    "text": "Terrible quality. Broke after one week. Customer service was unhelpful. Do not buy!"
  },
  {
    "id": 3,
    "text": "It's okay. Does the job but nothing special. Price is reasonable."
  },
  {
    "id": 4,
    "text": "Amazing! Best purchase ever. Highly recommend to everyone. Five stars!"
  },
  {
    "id": 5,
    "text": "Very disappointed. Product doesn't match description. Requesting a refund."
  },
  {
    "id": 6,
    "text": "Good value for money. Some minor issues but overall satisfied with the purchase."
  },
  {
    "id": 7,
    "text": "Outstanding quality and great customer support. Will definitely buy again!"
  },
  {
    "id": 8,
    "text": "Worst experience ever. Product arrived damaged and support ignored my emails."
  }
]
EOF

echo "✅ Customer reviews file created: reviews.json"
```

---

## Step 10 – Create Python Script for Batch Analysis

```bash
echo ""
echo "Creating Python script for batch sentiment analysis..."

# Navigate to comprehend directory
cd "$REPO_DIR/comprehend-demo"

cat > analyze_reviews.py <<'EOF'
#!/usr/bin/env python3
import boto3
import json
from collections import Counter

comprehend = boto3.client('comprehend')

def analyze_review(review_text):
    """Analyze sentiment of a single review"""
    response = comprehend.detect_sentiment(
        Text=review_text,
        LanguageCode='en'
    )
    return {
        'sentiment': response['Sentiment'],
        'scores': response['SentimentScore']
    }

def main():
    # Load reviews
    with open('reviews.json', 'r') as f:
        reviews = json.load(f)
    
    print("="*60)
    print("CUSTOMER REVIEW SENTIMENT ANALYSIS")
    print("="*60)
    print()
    
    results = []
    sentiment_counts = Counter()
    
    for review in reviews:
        review_id = review['id']
        text = review['text']
        
        # Analyze sentiment
        analysis = analyze_review(text)
        sentiment = analysis['sentiment']
        scores = analysis['scores']
        
        sentiment_counts[sentiment] += 1
        
        # Print individual review analysis
        print(f"Review #{review_id}")
        print(f"Text: {text[:80]}...")
        print(f"Sentiment: {sentiment}")
        print(f"Confidence: {scores[sentiment]:.2%}")
        print("-" * 60)
        
        results.append({
            'id': review_id,
            'sentiment': sentiment,
            'confidence': scores[sentiment]
        })
    
    # Print summary
    print()
    print("="*60)
    print("SUMMARY")
    print("="*60)
    print(f"Total Reviews: {len(reviews)}")
    print(f"Positive: {sentiment_counts['POSITIVE']}")
    print(f"Negative: {sentiment_counts['NEGATIVE']}")
    print(f"Neutral: {sentiment_counts['NEUTRAL']}")
    print(f"Mixed: {sentiment_counts['MIXED']}")
    print()
    
    # Calculate overall sentiment
    positive_pct = (sentiment_counts['POSITIVE'] / len(reviews)) * 100
    negative_pct = (sentiment_counts['NEGATIVE'] / len(reviews)) * 100
    
    print(f"Positive Rate: {positive_pct:.1f}%")
    print(f"Negative Rate: {negative_pct:.1f}%")
    print()
    
    if positive_pct > 60:
        print("✅ Overall customer satisfaction: HIGH")
    elif negative_pct > 40:
        print("❌ Overall customer satisfaction: LOW")
    else:
        print("⚠️  Overall customer satisfaction: MODERATE")

if __name__ == '__main__':
    main()
EOF

chmod +x analyze_reviews.py

echo "✅ Python script created: analyze_reviews.py"
```

---

## Step 11 – Run Batch Review Analysis

```bash
echo ""
echo "Running batch sentiment analysis on customer reviews..."
echo ""

# Navigate to comprehend directory and run analysis
cd "$REPO_DIR/comprehend-demo"

python3 analyze_reviews.py

echo ""
echo "✅ Batch analysis complete"
```

---

## Step 12 – Detect PII (Personally Identifiable Information)

```bash
echo ""
echo "================================================"
echo "PII DETECTION"
echo "================================================"
echo ""

PII_TEXT="My name is John Smith and my email is john.smith@example.com. My phone number is 555-123-4567 and I live at 123 Main Street, Seattle, WA. My SSN is 123-45-6789."

echo "Text: $PII_TEXT"
echo ""

# Detect PII entities
aws comprehend detect-pii-entities \
  --text "$PII_TEXT" \
  --language-code en \
  --region "$REGION" \
  --query 'Entities[*].{Type:Type,Score:Score}' \
  --output table

echo ""
echo "✅ PII entities detected: NAME, EMAIL, PHONE, ADDRESS, SSN"
```

---

## Step 13 – Create S3 Bucket for Batch Jobs

```bash
echo ""
echo "Creating S3 bucket for batch processing..."

BUCKET_NAME="comprehend-batch-${ACCOUNT_ID}"
echo "BUCKET_NAME=$BUCKET_NAME"

if [ "$REGION" = "us-east-1" ]; then
    aws s3api create-bucket \
      --bucket "$BUCKET_NAME" \
      --region "$REGION"
else
    aws s3api create-bucket \
      --bucket "$BUCKET_NAME" \
      --region "$REGION" \
      --create-bucket-configuration LocationConstraint="$REGION"
fi

echo "✅ S3 bucket created"
```

---

## Step 14 – Prepare Data for Batch Processing

```bash
echo ""
echo "Preparing batch input file..."

# Navigate to comprehend directory
cd "$REPO_DIR/comprehend-demo"

# Create batch input file (one document per line)
cat > batch_input.txt <<'EOF'
This product is amazing! Best purchase I ever made.
Terrible quality. Very disappointed with this purchase.
It works as expected. Nothing special but does the job.
Outstanding customer service and excellent product quality!
Worst experience ever. Would not recommend to anyone.
EOF

# Upload to S3
aws s3 cp batch_input.txt s3://"$BUCKET_NAME"/input/ \
  --region "$REGION"

echo "✅ Batch input file uploaded to S3"
```

---

## Step 15 – Create IAM Role for Batch Jobs

```bash
echo ""
echo "Creating IAM role for Comprehend batch jobs..."

# Navigate to comprehend directory
cd "$REPO_DIR/comprehend-demo"

# Create trust policy
cat > comprehend-trust-policy.json <<'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "comprehend.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

# Create role
aws iam create-role \
  --role-name ComprehendBatchRole \
  --assume-role-policy-document file://comprehend-trust-policy.json

# Create permissions policy
cat > comprehend-permissions.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::${BUCKET_NAME}",
        "arn:aws:s3:::${BUCKET_NAME}/*"
      ]
    }
  ]
}
EOF

# Attach policy
aws iam put-role-policy \
  --role-name ComprehendBatchRole \
  --policy-name ComprehendS3Access \
  --policy-document file://comprehend-permissions.json

echo "✅ IAM role created"
sleep 10

# Get role ARN
ROLE_ARN=$(aws iam get-role \
  --role-name ComprehendBatchRole \
  --query 'Role.Arn' \
  --output text)

echo "Role ARN: $ROLE_ARN"
```

---

## Step 16 – Start Batch Sentiment Analysis Job

```bash
echo ""
echo "================================================"
echo "STARTING BATCH SENTIMENT ANALYSIS JOB"
echo "================================================"
echo ""

# Start batch job
JOB_ID=$(aws comprehend start-sentiment-detection-job \
  --input-data-config "S3Uri=s3://${BUCKET_NAME}/input/" \
  --output-data-config "S3Uri=s3://${BUCKET_NAME}/output/" \
  --data-access-role-arn "$ROLE_ARN" \
  --language-code en \
  --region "$REGION" \
  --query 'JobId' \
  --output text)

echo "JOB_ID=$JOB_ID"
echo ""
echo "Batch job started! Monitoring status..."

# Poll job status
while true; do
    STATUS=$(aws comprehend describe-sentiment-detection-job \
      --job-id "$JOB_ID" \
      --region "$REGION" \
      --query 'SentimentDetectionJobProperties.JobStatus' \
      --output text)
    
    echo "Job status: $STATUS"
    
    if [ "$STATUS" = "COMPLETED" ]; then
        echo ""
        echo "✅ Batch job completed!"
        break
    elif [ "$STATUS" = "FAILED" ]; then
        echo ""
        echo "❌ Batch job failed"
        break
    fi
    
    sleep 15
done
```

---

## Step 17 – Retrieve Batch Results

```bash
echo ""
echo "Retrieving batch analysis results..."

# Navigate to comprehend directory
cd "$REPO_DIR/comprehend-demo"

# Download output
aws s3 sync s3://"$BUCKET_NAME"/output/ ./output/ \
  --region "$REGION"

echo ""
echo "Output files downloaded to: ./output/"
echo ""

# Display results
if [ -f ./output/output.tar.gz ]; then
    tar -xzf ./output/output.tar.gz -C ./output/
    echo "Results extracted:"
    ls -lh ./output/
    
    # Show sample results
    if [ -f ./output/output ]; then
        echo ""
        echo "Sample results:"
        head -5 ./output/output | jq .
    fi
fi

echo ""
echo "✅ Batch results retrieved"
```

---

## Step 18 – Create Social Media Analysis Script

```bash
echo ""
echo "Creating social media sentiment tracker..."

# Navigate to comprehend directory
cd "$REPO_DIR/comprehend-demo"

cat > social_media_analysis.py <<'EOF'
#!/usr/bin/env python3
import boto3

comprehend = boto3.client('comprehend')

# Simulated social media posts
posts = [
    "Just tried the new @CompanyXYZ product and I'm blown away! 🎉 #Amazing",
    "Seriously disappointed with @CompanyXYZ service. Never again! 😤 #Frustrated",
    "@CompanyXYZ your app keeps crashing. Please fix this ASAP! 😠",
    "Loving my new purchase from @CompanyXYZ! Excellent quality 👍 #HappyCustomer",
    "Meh. @CompanyXYZ is okay I guess. Nothing special. 🤷",
]

print("="*60)
print("SOCIAL MEDIA SENTIMENT MONITORING")
print("="*60)
print()

sentiments = {'POSITIVE': 0, 'NEGATIVE': 0, 'NEUTRAL': 0, 'MIXED': 0}

for idx, post in enumerate(posts, 1):
    response = comprehend.detect_sentiment(
        Text=post,
        LanguageCode='en'
    )
    
    sentiment = response['Sentiment']
    score = response['SentimentScore'][sentiment]
    sentiments[sentiment] += 1
    
    # Emoji indicators
    emoji = {
        'POSITIVE': '😊',
        'NEGATIVE': '😞',
        'NEUTRAL': '😐',
        'MIXED': '🤔'
    }
    
    print(f"Post {idx}: {emoji[sentiment]} {sentiment}")
    print(f"Text: {post}")
    print(f"Confidence: {score:.2%}")
    print("-" * 60)

print()
print("SENTIMENT DISTRIBUTION:")
for sentiment, count in sentiments.items():
    print(f"  {sentiment}: {count} posts")

print()
total = len(posts)
positive_rate = (sentiments['POSITIVE'] / total) * 100
negative_rate = (sentiments['NEGATIVE'] / total) * 100

print(f"Positive sentiment: {positive_rate:.0f}%")
print(f"Negative sentiment: {negative_rate:.0f}%")

if negative_rate > 40:
    print("\n⚠️  ALERT: High negative sentiment detected!")
    print("Action: Review customer complaints immediately")
EOF

chmod +x social_media_analysis.py

echo "✅ Social media analysis script created"
```

---

## Step 19 – Run Social Media Analysis

```bash
echo ""
echo "Running social media sentiment analysis..."
echo ""

# Navigate to comprehend directory and run analysis
cd "$REPO_DIR/comprehend-demo"

python3 social_media_analysis.py

echo ""
echo "✅ Social media analysis complete"
```

---

## Step 20 – Cleanup

```bash
echo ""
echo "Cleaning up resources..."

# Empty and delete S3 bucket
aws s3 rm s3://"$BUCKET_NAME" --recursive --region "$REGION"
aws s3api delete-bucket --bucket "$BUCKET_NAME" --region "$REGION"

echo "✅ S3 bucket deleted"

# Delete IAM role
aws iam delete-role-policy \
  --role-name ComprehendBatchRole \
  --policy-name ComprehendS3Access

aws iam delete-role --role-name ComprehendBatchRole

echo "✅ IAM role deleted"

# Remove local comprehend directory
cd "$REPO_DIR"
rm -rf comprehend-demo

echo "✅ Local files deleted"
echo ""
echo "All resources cleaned up!"
```

---

## Summary

In this lab, you have:
- Analyzed sentiment in text (positive, negative, neutral, mixed)
- Detected named entities (people, places, organizations, dates)
- Extracted key phrases from documents
- Detected dominant language automatically
- Performed syntax analysis (parts of speech)
- Detected PII (Personally Identifiable Information)
- Created batch analysis pipeline for customer reviews
- Analyzed social media sentiment at scale
- Used Python SDK for automation

**Key Takeaways:**
- **No ML Expertise Required**: Simple API calls for NLP tasks
- **Sentiment Analysis**: Understand customer satisfaction from text
- **Entity Detection**: Extract structured data from unstructured text
- **Language Detection**: Automatic language identification (100+ languages)
- **Batch Processing**: Analyze thousands of documents efficiently
- **Real-Time Analysis**: Instant insights from text streams

**Common Use Cases:**
- **Customer Feedback**: Analyze reviews, surveys, support tickets
- **Social Media Monitoring**: Track brand sentiment on Twitter, Facebook
- **Content Moderation**: Detect toxic or inappropriate content
- **Document Classification**: Categorize emails, articles, documents
- **Voice of Customer**: Extract insights from customer interactions

---

## Best Practices

**Text Preparation:**
- Use UTF-8 encoding for text
- Minimum 3 characters for analysis
- Maximum 5,000 bytes per API call
- Clean HTML/markup before analysis

**Performance:**
- Use batch jobs for large datasets (>1000 documents)
- Implement async processing for real-time applications
- Cache results to reduce API calls
- Use appropriate language codes

**Cost Optimization:**
- Monitor free tier usage (50K units/month)
- Use batch processing for cost efficiency
- Implement text preprocessing to reduce size
- Cache frequently analyzed content

**Security:**
- Use IAM roles with least privilege
- Redact PII before storing results
- Encrypt sensitive data
- Enable CloudTrail for audit logging

**Accuracy:**
- Provide sufficient context (min 10 words for sentiment)
- Use correct language codes
- Validate results for critical decisions
- Monitor confidence scores

---

## Production Enhancements

1. **Real-Time Dashboard**
   ```python
   # Stream reviews to dashboard
   def process_review_stream(review):
       sentiment = comprehend.detect_sentiment(...)
       publish_to_dashboard(sentiment)
   ```

2. **Alerting System**
   ```python
   # Alert on negative sentiment spike
   if negative_rate > 0.5:
       sns.publish(Message="High negative sentiment detected!")
   ```

3. **Lambda Integration**
   ```python
   # Auto-process new reviews
   def lambda_handler(event, context):
       review = event['review_text']
       sentiment = comprehend.detect_sentiment(Text=review, LanguageCode='en')
       store_in_dynamodb(sentiment)
   ```

4. **Custom Classification**
   ```bash
   # Train custom classifier
   aws comprehend create-document-classifier \
     --document-classifier-name my-classifier
   ```

---

## Troubleshooting

**Unsupported language error:**
- Check language code is correct (en, es, fr, etc.)
- Verify language is supported by Comprehend
- Use detect-dominant-language first

**Low confidence scores:**
- Provide more context (longer text)
- Check for mixed languages in text
- Ensure text is clean and well-formed

**Batch job fails:**
- Verify IAM role permissions
- Check S3 paths are correct
- Ensure input format is valid
- Review job error messages

**Rate limiting:**
- Implement exponential backoff
- Use batch processing instead of individual calls
- Request limit increase if needed

---

## Additional Resources

- [Amazon Comprehend Documentation](https://docs.aws.amazon.com/comprehend/)
- [Comprehend API Reference](https://docs.aws.amazon.com/comprehend/latest/dg/API_Reference.html)
- [Supported Languages](https://docs.aws.amazon.com/comprehend/latest/dg/supported-languages.html)
- [Comprehend Pricing](https://aws.amazon.com/comprehend/pricing/)
- [Best Practices Guide](https://docs.aws.amazon.com/comprehend/latest/dg/best-practices.html)
