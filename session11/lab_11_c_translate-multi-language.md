# Lab 11.C: Amazon Translate - Multi-Language Translation API

## Overview
This lab introduces Amazon Translate for real-time language translation supporting 75+ languages. You'll translate text, documents, and web content, implement auto-language detection, perform batch translations, create a multi-language chatbot, and handle custom terminology for accurate domain-specific translations.

---

## Objectives
- Translate text between multiple languages in real-time
- Auto-detect source language
- Translate full documents and web pages
- Use custom terminology for domain-specific translations
- Implement batch translation jobs
- Create multi-language customer support bot
- Handle bidirectional translation

---

## Prerequisites
- AWS CLI configured (`aws configure`)
- IAM permissions for Translate, S3
- Region: ap-southeast-2
- Python 3.x installed

---

## Architecture

```
Source Text (Any Language)
          ↓
   Amazon Translate API
   - Auto-detect source
   - Neural MT models
   - Custom terminology
          ↓
    Target Language(s)
```

---

## Step 1 – Set Variables

```bash
# Set AWS region for all operations
REGION="ap-southeast-2"
export AWS_REGION="$REGION"

# Get AWS account ID for unique bucket naming
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

echo "Region: $REGION"
echo "Account ID: $ACCOUNT_ID"
```

---

## Step 2 – Translate English to Spanish

```bash
echo ""
echo "================================================"
echo "BASIC TRANSLATION: English → Spanish"
echo "================================================"
echo ""

SOURCE_TEXT="Hello! Welcome to our cloud computing course. Today we will learn about machine learning and artificial intelligence."

echo "Source (English):"
echo "$SOURCE_TEXT"
echo ""

# Translate English text to Spanish using Translate API
TRANSLATION=$(aws translate translate-text \
  --text "$SOURCE_TEXT" \
  --source-language-code en \
  --target-language-code es \
  --region "$REGION" \
  --query 'TranslatedText' \
  --output text)

echo "Translation (Spanish):"
echo "$TRANSLATION"
```

---

## Step 3 – Translate to Multiple Languages

```bash
echo ""
echo "================================================"
echo "MULTI-LANGUAGE TRANSLATION"
echo "================================================"
echo ""

TEXT="Good morning! How can I help you today?"
echo "Original: $TEXT"
echo ""

# Translate to French
FRENCH=$(aws translate translate-text \
  --text "$TEXT" \
  --source-language-code en \
  --target-language-code fr \
  --region "$REGION" \
  --query 'TranslatedText' \
  --output text)

echo "French: $FRENCH"

# Translate to German
GERMAN=$(aws translate translate-text \
  --text "$TEXT" \
  --source-language-code en \
  --target-language-code de \
  --region "$REGION" \
  --query 'TranslatedText' \
  --output text)

echo "German: $GERMAN"

# Translate to Italian
ITALIAN=$(aws translate translate-text \
  --text "$TEXT" \
  --source-language-code en \
  --target-language-code it \
  --region "$REGION" \
  --query 'TranslatedText' \
  --output text)

echo "Italian: $ITALIAN"

# Translate to Portuguese
PORTUGUESE=$(aws translate translate-text \
  --text "$TEXT" \
  --source-language-code en \
  --target-language-code pt \
  --region "$REGION" \
  --query 'TranslatedText' \
  --output text)

echo "Portuguese: $PORTUGUESE"

# Translate to Japanese
JAPANESE=$(aws translate translate-text \
  --text "$TEXT" \
  --source-language-code en \
  --target-language-code ja \
  --region "$REGION" \
  --query 'TranslatedText' \
  --output text)

echo "Japanese: $JAPANESE"

# Translate to Chinese (Simplified)
CHINESE=$(aws translate translate-text \
  --text "$TEXT" \
  --source-language-code en \
  --target-language-code zh \
  --region "$REGION" \
  --query 'TranslatedText' \
  --output text)

echo "Chinese: $CHINESE"
```

---

## Step 4 – Auto-Detect Source Language

```bash
echo ""
echo "================================================"
echo "AUTO-DETECT SOURCE LANGUAGE"
echo "================================================"
echo ""

# Test text in French (pretend source language is unknown)
MYSTERY_TEXT="Bonjour! Comment allez-vous aujourd'hui?"

echo "Mystery text: $MYSTERY_TEXT"
echo ""

# Translate with auto-detection using 'auto' as source language code
RESULT=$(aws translate translate-text \
  --text "$MYSTERY_TEXT" \
  --source-language-code auto \
  --target-language-code en \
  --region "$REGION" \
  --output json)

echo "Detected language: $(echo "$RESULT" | jq -r '.SourceLanguageCode')"
echo "Translation to English: $(echo "$RESULT" | jq -r '.TranslatedText')"
echo ""

# Spanish text
SPANISH_TEXT="¿Cómo está el tiempo hoy?"
echo "Mystery text: $SPANISH_TEXT"

RESULT=$(aws translate translate-text \
  --text "$SPANISH_TEXT" \
  --source-language-code auto \
  --target-language-code en \
  --region "$REGION" \
  --output json)

echo "Detected language: $(echo "$RESULT" | jq -r '.SourceLanguageCode')"
echo "Translation to English: $(echo "$RESULT" | jq -r '.TranslatedText')"
```

---

## Step 5 – Bidirectional Translation

```bash
echo ""
echo "================================================"
echo "BIDIRECTIONAL TRANSLATION"
echo "================================================"
echo ""

ORIGINAL="The quick brown fox jumps over the lazy dog."
echo "Original English: $ORIGINAL"
echo ""

# Translate English to Japanese
JAPANESE=$(aws translate translate-text \
  --text "$ORIGINAL" \
  --source-language-code en \
  --target-language-code ja \
  --region "$REGION" \
  --query 'TranslatedText' \
  --output text)

echo "Japanese: $JAPANESE"
echo ""

# Translate Japanese back to English to verify quality
BACK_TRANSLATION=$(aws translate translate-text \
  --text "$JAPANESE" \
  --source-language-code ja \
  --target-language-code en \
  --region "$REGION" \
  --query 'TranslatedText' \
  --output text)

echo "Back to English: $BACK_TRANSLATION"
```

---

## Step 6 – Create Multi-Language Customer Support Bot

```bash
echo ""
echo "Creating multi-language support bot..."

# Get repository root directory
REPO_DIR=$(git rev-parse --show-toplevel)

# Create translate directory in repository
mkdir -p "$REPO_DIR/translate-demo"
cd "$REPO_DIR/translate-demo"

# Create Python script for multi-language customer support bot
cat > support_bot.py <<'EOF'
#!/usr/bin/env python3
import boto3

translate = boto3.client('translate')

# Customer inquiries in different languages
inquiries = [
    ("Hello, I need help with my order.", "en"),
    ("Bonjour, j'ai un problème avec ma commande.", "fr"),
    ("Hola, necesito ayuda con mi pedido.", "es"),
    ("Ciao, ho bisogno di aiuto con il mio ordine.", "it"),
    ("こんにちは、注文について助けが必要です。", "ja"),
]

# Support response template (English)
support_response = "Thank you for contacting us! Our team will review your order and respond within 24 hours. Is there anything else I can help you with?"

print("="*70)
print("MULTI-LANGUAGE CUSTOMER SUPPORT BOT")
print("="*70)
print()

for idx, (inquiry, lang_code) in enumerate(inquiries, 1):
    print(f"{'='*70}")
    print(f"Customer #{idx} ({lang_code.upper()})")
    print(f"{'='*70}")
    
    # Display customer inquiry
    print(f"Customer: {inquiry}")
    
    # Translate inquiry to English for processing
    if lang_code != 'en':
        translated_inquiry = translate.translate_text(
            Text=inquiry,
            SourceLanguageCode=lang_code,
            TargetLanguageCode='en'
        )['TranslatedText']
        print(f"[Translated to English]: {translated_inquiry}")
    
    # Translate support response back to customer's language
    if lang_code != 'en':
        localized_response = translate.translate_text(
            Text=support_response,
            SourceLanguageCode='en',
            TargetLanguageCode=lang_code
        )['TranslatedText']
    else:
        localized_response = support_response
    
    print(f"Support Bot: {localized_response}")
    print()

print("✅ All customer inquiries handled in their native language")
EOF

chmod +x support_bot.py
```

---

## Step 7 – Run Multi-Language Support Bot

```bash
echo ""
echo "Running multi-language support bot..."
echo ""

# Navigate to translate directory and run support bot
cd "$REPO_DIR/translate-demo"

python3 support_bot.py
```

---

## Step 8 – Create Custom Terminology

```bash
echo ""
echo "================================================"
echo "CUSTOM TERMINOLOGY"
echo "================================================"
echo ""

# Navigate to translate directory
cd "$REPO_DIR/translate-demo"

# Create custom terminology CSV file with technical terms
cat > custom_terms.csv <<'EOF'
en,es,fr
AWS,AWS,AWS
Amazon S3,Amazon S3,Amazon S3
Lambda,Lambda,Lambda
EC2,EC2,EC2
CloudFormation,CloudFormation,CloudFormation
Machine Learning,Aprendizaje Automático,Apprentissage Automatique
Serverless,Sin Servidor,Sans Serveur
EOF

echo "Custom terminology file created"
cat custom_terms.csv
echo ""

# Create unique S3 bucket name for terminology files
BUCKET_NAME="translate-terminology-${ACCOUNT_ID}"
echo "Bucket: $BUCKET_NAME"

# Create S3 bucket (region-specific configuration)
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

# Upload custom terminology CSV to S3
aws s3 cp custom_terms.csv s3://"$BUCKET_NAME"/custom_terms.csv \
  --region "$REGION"

# Import custom terminology into Translate service (base64 encoded)
aws translate import-terminology \
  --name AWSTerminology \
  --merge-strategy OVERWRITE \
  --terminology-data "Format=CSV,File=$(base64 -w 0 < custom_terms.csv)" \
  --region "$REGION"
```

---

## Step 9 – Translate with Custom Terminology

```bash
echo ""
echo "Testing translation with custom terminology..."
echo ""

TECH_TEXT="AWS Lambda is a serverless compute service. You can deploy machine learning models using Amazon S3 and EC2 instances."

echo "Original: $TECH_TEXT"
echo ""

# Translate without custom terminology (default behavior)
echo "Without terminology:"
TRANSLATION_NORMAL=$(aws translate translate-text \
  --text "$TECH_TEXT" \
  --source-language-code en \
  --target-language-code es \
  --region "$REGION" \
  --query 'TranslatedText' \
  --output text)

echo "$TRANSLATION_NORMAL"
echo ""

# Translate with custom terminology to preserve technical terms
echo "With custom terminology:"
TRANSLATION_CUSTOM=$(aws translate translate-text \
  --text "$TECH_TEXT" \
  --source-language-code en \
  --target-language-code es \
  --terminology-names AWSTerminology \
  --region "$REGION" \
  --query 'TranslatedText' \
  --output text)

echo "$TRANSLATION_CUSTOM"
echo ""
echo "Notice: Technical terms (AWS, Lambda, S3, EC2) preserved correctly"
```

---

## Step 10 – Create Website Localizer

```bash
echo ""
echo "Creating website localizer..."

# Navigate to translate directory
cd "$REPO_DIR/translate-demo"

# Create Python script for website localization
cat > localize_website.py <<'EOF'
#!/usr/bin/env python3
import boto3

translate = boto3.client('translate')

# Website content (English)
website_content = {
    'header': 'Welcome to Our Company',
    'tagline': 'Innovation at your fingertips',
    'about': 'We provide cutting-edge cloud computing solutions to businesses worldwide.',
    'cta': 'Get Started Today',
    'contact': 'Contact Us',
    'footer': 'Copyright 2024. All rights reserved.'
}

# Languages to localize
languages = {
    'es': 'Spanish',
    'fr': 'French',
    'de': 'German',
    'ja': 'Japanese',
    'zh': 'Chinese'
}

print("="*70)
print("WEBSITE LOCALIZATION")
print("="*70)
print()

for lang_code, lang_name in languages.items():
    print(f"{'='*70}")
    print(f"{lang_name.upper()} ({lang_code})")
    print(f"{'='*70}")
    
    localized = {}
    
    for key, text in website_content.items():
        translated = translate.translate_text(
            Text=text,
            SourceLanguageCode='en',
            TargetLanguageCode=lang_code
        )['TranslatedText']
        
        localized[key] = translated
        print(f"{key.capitalize()}: {translated}")
    
    print()

print("✅ Website localized to 5 languages")
EOF

chmod +x localize_website.py
```

---

## Step 11 – Run Website Localizer

```bash
echo ""
echo "Running website localizer..."
echo ""

# Navigate to translate directory and run localizer
cd "$REPO_DIR/translate-demo"

python3 localize_website.py
```

---

## Step 12 – Prepare Batch Translation Input

```bash
echo ""
echo "================================================"
echo "BATCH TRANSLATION"
echo "================================================"
echo ""

# Navigate to translate directory
cd "$REPO_DIR/translate-demo"

# Create directory for batch input documents
mkdir -p batch_input

# Create sample document 1
cat > batch_input/doc1.txt <<'EOF'
Our company is committed to delivering exceptional customer service.
We value innovation, integrity, and excellence in everything we do.
EOF

# Create sample document 2
cat > batch_input/doc2.txt <<'EOF'
Thank you for choosing our products. Your satisfaction is our priority.
Please contact support if you have any questions or concerns.
EOF

# Create sample document 3
cat > batch_input/doc3.txt <<'EOF'
New features are now available in the latest version of our software.
Upgrade today to experience improved performance and security.
EOF

echo "Created 3 documents for batch translation"
ls -lh batch_input/

# Upload all batch input documents to S3
aws s3 sync batch_input/ s3://"$BUCKET_NAME"/batch_input/ \
  --region "$REGION"
```

---

## Step 13 – Create IAM Role for Batch Jobs

```bash
echo ""
echo "Creating IAM role for batch translation..."

# Navigate to translate directory
cd "$REPO_DIR/translate-demo"

# Create trust policy allowing Translate service to assume role
cat > translate-trust-policy.json <<'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "translate.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

# Create IAM role with trust policy
aws iam create-role \
  --role-name TranslateBatchRole \
  --assume-role-policy-document file://translate-trust-policy.json

# Create permissions policy for S3 access (separate statements for object vs bucket)
cat > translate-permissions.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::${BUCKET_NAME}/*"
    },
    {
      "Effect": "Allow",
      "Action": "s3:PutObject",
      "Resource": "arn:aws:s3:::${BUCKET_NAME}/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:ListBucket",
        "s3:GetBucketLocation"
      ],
      "Resource": "arn:aws:s3:::${BUCKET_NAME}"
    }
  ]
}
EOF

# Attach permissions policy to role
aws iam put-role-policy \
  --role-name TranslateBatchRole \
  --policy-name TranslateS3Access \
  --policy-document file://translate-permissions.json

echo "Waiting for IAM propagation..."
sleep 30

# Get role ARN for batch job
ROLE_ARN=$(aws iam get-role \
  --role-name TranslateBatchRole \
  --query 'Role.Arn' \
  --output text)

echo "Role ARN: $ROLE_ARN"
```

---

## Step 14 – Start Batch Translation Job

```bash
echo ""
echo "Starting batch translation job..."

# Start batch translation job (English to Spanish, French, German)
JOB_ID=$(aws translate start-text-translation-job \
  --input-data-config "S3Uri=s3://${BUCKET_NAME}/batch_input/,ContentType=text/plain" \
  --output-data-config "S3Uri=s3://${BUCKET_NAME}/batch_output/" \
  --data-access-role-arn "$ROLE_ARN" \
  --source-language-code en \
  --target-language-codes es fr de \
  --region "$REGION" \
  --query 'JobId' \
  --output text)

echo "Job ID: $JOB_ID"
echo ""
echo "Batch translation job started! Monitoring status..."

# Poll job status every 15 seconds
while true; do
    STATUS=$(aws translate describe-text-translation-job \
      --job-id "$JOB_ID" \
      --region "$REGION" \
      --query 'TextTranslationJobProperties.JobStatus' \
      --output text)
    
    echo "Job status: $STATUS"
    
    if [ "$STATUS" = "COMPLETED" ]; then
        echo ""
        echo "✅ Batch translation completed!"
        break
    elif [ "$STATUS" = "FAILED" ]; then
        echo ""
        echo "❌ Batch translation failed"
        break
    fi
    
    sleep 15
done
```

---

## Step 15 – Retrieve Batch Translation Results

```bash
echo ""
echo "Retrieving batch translation results..."

# Navigate to translate directory
cd "$REPO_DIR/translate-demo"

# Download batch translation output from S3
aws s3 sync s3://"$BUCKET_NAME"/batch_output/ ./batch_output/ \
  --region "$REGION"

echo ""
echo "Output files downloaded to: ./batch_output/"
echo ""

# Display translated files
find ./batch_output -type f -name "*.txt" | while read file; do
    echo "File: $file"
    echo "Content:"
    head -5 "$file"
    echo "---"
done
```

---

## Step 16 – Create Real-Time Translation Chat

```bash
echo ""
echo "Creating real-time translation chat simulator..."

# Navigate to translate directory
cd "$REPO_DIR/translate-demo"

# Create Python script for real-time bilingual chat
cat > translation_chat.py <<'EOF'
#!/usr/bin/env python3
import boto3

translate = boto3.client('translate')

# Simulated conversation between English and Spanish speakers
conversation = [
    ("Alice (EN)", "Hello! How are you doing today?", "en", "es"),
    ("Bob (ES)", "¡Hola! Estoy bien, gracias. ¿Y tú?", "es", "en"),
    ("Alice (EN)", "I'm great! Are you ready for our meeting?", "en", "es"),
    ("Bob (ES)", "Sí, estoy listo. ¿Qué vamos a discutir?", "es", "en"),
    ("Alice (EN)", "We'll discuss the new project timeline.", "en", "es"),
    ("Bob (ES)", "Perfecto, tengo algunas preguntas sobre eso.", "es", "en"),
]

print("="*70)
print("REAL-TIME TRANSLATION CHAT")
print("="*70)
print()

for speaker, message, source_lang, target_lang in conversation:
    print(f"{speaker}: {message}")
    
    # Translate message
    translation = translate.translate_text(
        Text=message,
        SourceLanguageCode=source_lang,
        TargetLanguageCode=target_lang
    )['TranslatedText']
    
    target_speaker = "Bob (ES)" if speaker.startswith("Alice") else "Alice (EN)"
    print(f"[{target_speaker} sees]: {translation}")
    print()

print("✅ Real-time translation enables seamless communication")
EOF

chmod +x translation_chat.py
```

---

## Step 17 – Run Translation Chat

```bash
echo ""
echo "Running translation chat simulator..."
echo ""

# Navigate to translate directory and run chat simulator
cd "$REPO_DIR/translate-demo"

python3 translation_chat.py
```

---

## Step 18 – List Supported Languages

```bash
echo ""
echo "================================================"
echo "SUPPORTED LANGUAGES"
echo "================================================"
echo ""

# List all supported languages (filtering languages starting with 'A' for sample)
aws translate list-languages \
  --region "$REGION" \
  --query 'Languages[?starts_with(LanguageName, `A`)].[LanguageCode, LanguageName]' \
  --output table | head -20

echo ""
echo "Sample languages shown (75+ total supported)"
echo "Use 'aws translate list-languages' to see all supported languages"
```

---

## Step 19 – Create Production Translation Pipeline

```bash
echo ""
echo "Creating production translation pipeline..."

# Navigate to translate directory
cd "$REPO_DIR/translate-demo"

# Create Python script demonstrating translation caching
cat > translation_pipeline.py <<'EOF'
#!/usr/bin/env python3
import boto3
import json

translate = boto3.client('translate')
s3 = boto3.client('s3')

def translate_and_cache(text, source_lang, target_lang, cache_bucket):
    """Translate text with S3 caching"""
    
    # Create cache key
    cache_key = f"cache/{source_lang}-{target_lang}/{hash(text)}.json"
    
    try:
        # Check cache first
        response = s3.get_object(Bucket=cache_bucket, Key=cache_key)
        cached = json.loads(response['Body'].read())
        print(f"[CACHE HIT] {source_lang} → {target_lang}")
        return cached['translation']
    except s3.exceptions.NoSuchKey:
        # Cache miss - translate and cache result
        translation = translate.translate_text(
            Text=text,
            SourceLanguageCode=source_lang,
            TargetLanguageCode=target_lang
        )['TranslatedText']
        
        # Cache result
        s3.put_object(
            Bucket=cache_bucket,
            Key=cache_key,
            Body=json.dumps({
                'source': text,
                'translation': translation,
                'source_lang': source_lang,
                'target_lang': target_lang
            })
        )
        
        print(f"[CACHE MISS] {source_lang} → {target_lang} (cached)")
        return translation

# Example usage
print("="*70)
print("PRODUCTION TRANSLATION PIPELINE")
print("="*70)
print()

text = "Welcome to our service"
bucket = "translate-terminology-" + boto3.client('sts').get_caller_identity()['Account']

for target in ['es', 'fr', 'de']:
    result = translate_and_cache(text, 'en', target, bucket)
    print(f"{target.upper()}: {result}")
    print()

# Repeat same translations (should hit cache)
print("Repeating translations (should use cache):")
print()
for target in ['es', 'fr', 'de']:
    result = translate_and_cache(text, 'en', target, bucket)
    print(f"{target.upper()}: {result}")
    print()

print("✅ Translation pipeline with caching demonstrated")
EOF

chmod +x translation_pipeline.py
```

---

## Step 20 – Cleanup

```bash
echo ""
echo "Cleaning up resources..."

# Delete custom terminology from Translate service
echo "Deleting custom terminology..."
aws translate delete-terminology \
  --name AWSTerminology \
  --region "$REGION" 2>/dev/null

echo "✅ Custom terminology deleted"

# Empty and delete S3 bucket
echo "Deleting S3 bucket and contents..."
aws s3 rm s3://"$BUCKET_NAME" --recursive --region "$REGION"
aws s3api delete-bucket --bucket "$BUCKET_NAME" --region "$REGION"

echo "✅ S3 bucket deleted"

# Delete IAM role policy and role
echo "Deleting IAM role..."
aws iam delete-role-policy \
  --role-name TranslateBatchRole \
  --policy-name TranslateS3Access 2>/dev/null

aws iam delete-role --role-name TranslateBatchRole 2>/dev/null

echo "✅ IAM role deleted"

# Remove local translate directory
echo "Removing local files..."
cd "$REPO_DIR"
rm -rf translate-demo

echo "✅ Local files deleted"
echo ""
echo "✅ Lab 11.C cleanup complete!"
```

---

## Summary

In this lab, you have:
- Translated text between 75+ languages in real-time
- Implemented auto-detection of source language
- Used custom terminology for domain-specific translations
- Created batch translation jobs for large document sets
- Built multi-language customer support bot
- Implemented website localization
- Created real-time translation chat
- Developed production pipeline with caching

**Key Takeaways:**
- **Neural Machine Translation**: High-quality translations using deep learning
- **Real-Time**: Instant translations via simple API calls
- **Auto-Detection**: Automatic source language identification
- **Custom Terminology**: Preserve brand names and technical terms
- **Batch Processing**: Translate thousands of documents efficiently
- **Cost-Effective**: 2M characters/month free tier

**Common Use Cases:**
- **Customer Support**: Multi-language help desk
- **Website Localization**: Global e-commerce sites
- **Content Publishing**: Translate articles, blogs, documentation
- **Real-Time Chat**: International team communication
- **Document Translation**: Legal, technical, marketing materials
- **Social Media**: Engage global audiences

---

## Best Practices

**Translation Quality:**
- Provide context (full sentences, not single words)
- Use custom terminology for technical/brand terms
- Review translations for critical content
- Consider cultural nuances

**Performance:**
- Cache frequent translations
- Use batch jobs for large volumes
- Implement request throttling
- Monitor API quotas

**Cost Optimization:**
- Cache translations to avoid duplicates
- Use batch processing for efficiency
- Monitor character usage
- Implement content length limits

**Security:**
- Use IAM roles with least privilege
- Don't translate sensitive PII without review
- Encrypt data in transit and at rest
- Enable CloudTrail for audit logging

**Production Readiness:**
- Implement retry logic with exponential backoff
- Handle rate limiting gracefully
- Monitor translation quality
- Provide fallback for unsupported languages

---

## Production Enhancements

1. **Translation Memory**
   ```python
   # Store and reuse translations
   def get_translation(text, target):
       cached = check_translation_memory(text, target)
       if cached:
           return cached
       return translate_and_store(text, target)
   ```

2. **Quality Assurance**
   ```python
   # Back-translate to verify quality
   def verify_translation(original, translated, source, target):
       back = translate(translated, target, source)
       similarity = calculate_similarity(original, back)
       return similarity > 0.8
   ```

3. **Content Filtering**
   ```python
   # Skip translating certain content
   def should_translate(text):
       if is_code(text) or is_url(text):
           return False
       return True
   ```

4. **Lambda Integration**
   ```python
   # Auto-translate new content
   def lambda_handler(event, context):
       content = event['content']
       for lang in ['es', 'fr', 'de']:
           translated = translate(content, 'en', lang)
           publish_to_cdn(translated, lang)
   ```

---

## Troubleshooting

**Unsupported language pair error:**
- Check supported languages with `list-languages`
- Some language pairs require intermediate translation
- Use English as intermediate language

**Poor translation quality:**
- Provide more context (complete sentences)
- Use custom terminology for technical terms
- Check for typos in source text
- Consider professional human review for critical content

**Batch job fails:**
- Verify IAM role permissions
- Check S3 paths and file formats
- Ensure input files are UTF-8 encoded
- Review job error messages

**Rate limiting:**
- Implement exponential backoff
- Use batch processing for large volumes
- Request limit increase if needed
- Cache frequently translated content

---

## Additional Resources

- [Amazon Translate Documentation](https://docs.aws.amazon.com/translate/)
- [Translate API Reference](https://docs.aws.amazon.com/translate/latest/dg/API_Reference.html)
- [Supported Languages](https://docs.aws.amazon.com/translate/latest/dg/what-is-languages.html)
- [Custom Terminology Guide](https://docs.aws.amazon.com/translate/latest/dg/how-custom-terminology.html)
- [Translate Pricing](https://aws.amazon.com/translate/pricing/)
- [Best Practices](https://docs.aws.amazon.com/translate/latest/dg/best-practices.html)
