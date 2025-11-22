# Lab 11.A: Amazon Rekognition - Image Analysis and Face Detection
<img width="1536" height="724" alt="IMG" src="https://github.com/user-attachments/assets/f58ffa85-d64c-4b4f-abb8-dc5c02ea5eeb" />

## Overview
This lab introduces Amazon Rekognition for image analysis using machine learning without requiring ML expertise. You'll detect faces, analyze facial attributes, identify objects and scenes, detect text in images, and compare faces across different images.

---

## Objectives
- Upload images to S3 for analysis
- Detect faces and analyze facial attributes (age, emotions, gender)
- Identify objects, scenes, and activities in images
- Detect and extract text from images (OCR)
- Compare faces across different images
- Detect labels with confidence scores
- Test celebrity recognition

---

## Prerequisites
- AWS CLI configured (`aws configure`)
- IAM permissions for Rekognition, S3
- Region: ap-southeast-2
- Basic image files for testing

---

## Architecture

```
Images in S3 Bucket
      ↓
Amazon Rekognition API
      ↓
Analysis Results (JSON)
  - Face Detection
  - Label Detection
  - Text Detection
  - Face Comparison
```

---

## Step 1 – Set Variables and Create S3 Bucket

```bash
# Set AWS region for all operations
REGION="ap-southeast-2"
export AWS_REGION="$REGION"

# Get AWS account ID for unique bucket naming
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# Create unique S3 bucket name
BUCKET_NAME="rekognition-demo-${ACCOUNT_ID}"

echo "Region: $REGION"
echo "Bucket: $BUCKET_NAME"

# Create S3 bucket for storing images (region-specific configuration)
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
```

---

## Step 2 – Create Test Images Directory

```bash
# Get repository root directory
REPO_DIR=$(git rev-parse --show-toplevel)

# Create images directory in repository
mkdir -p "$REPO_DIR/rekognition-images"
cd "$REPO_DIR/rekognition-images"
```

---

## Step 3 – Download Sample Images

```bash
# Download sample images from Pexels (free stock photos)
curl -s -o person1.jpg "https://images.pexels.com/photos/220453/pexels-photo-220453.jpeg?w=500"
curl -s -o person2.jpg "https://images.pexels.com/photos/774909/pexels-photo-774909.jpeg?w=500"
curl -s -o group.jpg "https://images.pexels.com/photos/2253879/pexels-photo-2253879.jpeg?w=500"
curl -s -o street.jpg "https://images.pexels.com/photos/1270171/pexels-photo-1270171.jpeg?w=500"
curl -s -o text-sign.jpg "https://images.pexels.com/photos/262470/pexels-photo-262470.jpeg?w=500"

# List downloaded images
ls -lh *.jpg
```

---

## Step 4 – Upload Images to S3

```bash
# Upload all JPG images to S3 bucket
for img in *.jpg; do
    aws s3 cp "$img" s3://"$BUCKET_NAME"/ --region "$REGION"
    echo "Uploaded: $img"
done

# Verify uploaded images in S3
aws s3 ls s3://"$BUCKET_NAME"/  --region "$REGION"
```

---

## Step 5 – Detect Faces in Image

```bash
echo ""
echo "================================================"
echo "FACE DETECTION - Analyzing person1.jpg"
echo "================================================"

# Detect faces and analyze attributes (age, gender, emotions, smile, eyes)
aws rekognition detect-faces \
  --image "{\"S3Object\":{\"Bucket\":\"${BUCKET_NAME}\",\"Name\":\"person1.jpg\"}}" \
  --attributes "ALL" \
  --region "$REGION" \
  --query 'FaceDetails[0].{
    AgeRange:AgeRange,
    Gender:Gender.Value,
    Emotions:Emotions[0].Type,
    Smile:Smile.Value,
    EyesOpen:EyesOpen.Value,
    Confidence:Confidence
  }' \
  --output table
```

---

## Step 6 – Analyze All Emotions

```bash
echo ""
echo "Analyzing emotions in detail..."

# Detect all emotions with confidence scores (happy, sad, angry, etc.)
aws rekognition detect-faces \
  --image "{\"S3Object\":{\"Bucket\":\"${BUCKET_NAME}\",\"Name\":\"person1.jpg\"}}" \
  --attributes "ALL" \
  --region "$REGION" \
  --query 'FaceDetails[0].Emotions[*].{Emotion:Type,Confidence:Confidence}' \
  --output table
```

---

## Step 7 – Detect Multiple Faces in Group Photo

```bash
echo ""
echo "================================================"
echo "MULTIPLE FACE DETECTION - Analyzing group.jpg"
echo "================================================"

# Count total faces detected in group photo
FACE_COUNT=$(aws rekognition detect-faces \
  --image "{\"S3Object\":{\"Bucket\":\"${BUCKET_NAME}\",\"Name\":\"group.jpg\"}}" \
  --region "$REGION" \
  --query 'length(FaceDetails)' \
  --output text)

echo "Faces detected: $FACE_COUNT"
echo ""

# Analyze attributes for each detected face
aws rekognition detect-faces \
  --image "{\"S3Object\":{\"Bucket\":\"${BUCKET_NAME}\",\"Name\":\"group.jpg\"}}" \
  --attributes "ALL" \
  --region "$REGION" \
  --query 'FaceDetails[*].{
    AgeRange:AgeRange,
    Gender:Gender.Value,
    Smile:Smile.Value,
    Confidence:Confidence
  }' \
  --output table
```

---

## Step 8 – Detect Labels (Objects and Scenes)

```bash
echo ""
echo "================================================"
echo "LABEL DETECTION - Analyzing street.jpg"
echo "================================================"

# Detect objects, scenes, and activities with confidence threshold
aws rekognition detect-labels \
  --image "{\"S3Object\":{\"Bucket\":\"${BUCKET_NAME}\",\"Name\":\"street.jpg\"}}" \
  --max-labels 10 \
  --min-confidence 75 \
  --region "$REGION" \
  --query 'Labels[*].{Label:Name,Confidence:Confidence,Parents:Parents[*].Name}' \
  --output table
```

---

## Step 9 – Detect Text in Images (OCR)

```bash
echo ""
echo "================================================"
echo "TEXT DETECTION - Analyzing text-sign.jpg"
echo "================================================"

# Extract text from image using OCR (Optical Character Recognition)
aws rekognition detect-text \
  --image "{\"S3Object\":{\"Bucket\":\"${BUCKET_NAME}\",\"Name\":\"text-sign.jpg\"}}" \
  --region "$REGION" \
  --query 'TextDetections[?Type==`LINE`].{Text:DetectedText,Confidence:Confidence}' \
  --output table
```

---

## Step 10 – Compare Two Faces

```bash
echo ""
echo "================================================"
echo "FACE COMPARISON - Comparing person1.jpg vs person2.jpg"
echo "================================================"

# Compare source face against target face with similarity threshold
aws rekognition compare-faces \
  --source-image "{\"S3Object\":{\"Bucket\":\"${BUCKET_NAME}\",\"Name\":\"person1.jpg\"}}" \
  --target-image "{\"S3Object\":{\"Bucket\":\"${BUCKET_NAME}\",\"Name\":\"person2.jpg\"}}" \
  --similarity-threshold 80 \
  --region "$REGION" \
  --query '{
    Match:length(FaceMatches[]),
    Similarity:FaceMatches[0].Similarity,
    UnmatchedFaces:length(UnmatchedFaces)
  }' \
  --output table

echo ""
echo "Similarity threshold: 80% (faces above this are considered a match)"
```

---

## Step 11 – Create Collection for Face Storage

```bash
echo ""
echo "================================================"
echo "CREATING FACE COLLECTION"
echo "================================================"

# Create collection ID for storing indexed faces
COLLECTION_ID="employees-collection"
echo "Collection ID: $COLLECTION_ID"
echo ""

# Create face collection (searchable database of faces)
aws rekognition create-collection \
  --collection-id "$COLLECTION_ID" \
  --region "$REGION"

# List all collections in current region
aws rekognition list-collections \
  --region "$REGION" \
  --query 'CollectionIds' \
  --output table
```

---

## Step 12 – Index Faces into Collection

```bash
echo ""
echo "Indexing faces from person1.jpg into collection..."

# Index face into collection with external ID for identification
FACE_ID=$(aws rekognition index-faces \
  --collection-id "$COLLECTION_ID" \
  --image "{\"S3Object\":{\"Bucket\":\"${BUCKET_NAME}\",\"Name\":\"person1.jpg\"}}" \
  --external-image-id "employee-001" \
  --detection-attributes "ALL" \
  --region "$REGION" \
  --query 'FaceRecords[0].Face.FaceId' \
  --output text)

echo "Face ID: $FACE_ID"
echo ""

# List all indexed faces in collection
aws rekognition list-faces \
  --collection-id "$COLLECTION_ID" \
  --region "$REGION" \
  --query 'Faces[*].{FaceId:FaceId,ExternalImageId:ExternalImageId}' \
  --output table
```

---

## Step 13 – Search Face in Collection

```bash
echo ""
echo "Searching for matching face in collection using person2.jpg..."

# Search collection for matching faces with similarity threshold
aws rekognition search-faces-by-image \
  --collection-id "$COLLECTION_ID" \
  --image "{\"S3Object\":{\"Bucket\":\"${BUCKET_NAME}\",\"Name\":\"person2.jpg\"}}" \
  --max-faces 1 \
  --face-match-threshold 80 \
  --region "$REGION" \
  --query '{
    SearchedFace:SearchedFaceConfidence,
    Matches:FaceMatches[*].{Similarity:Similarity,FaceId:Face.FaceId,ExternalId:Face.ExternalImageId}
  }' \
  --output json | jq .
```

---

## Step 14 – Analyze Image Content Moderation

```bash
echo ""
echo "================================================"
echo "CONTENT MODERATION - Analyzing street.jpg"
echo "================================================"
echo ""

# Detect inappropriate content
aws rekognition detect-moderation-labels \
  --image "{\"S3Object\":{\"Bucket\":\"${BUCKET_NAME}\",\"Name\":\"street.jpg\"}}" \
  --min-confidence 60 \
  --region "$REGION" \
  --query 'ModerationLabels[*].{Label:Name,Confidence:Confidence,ParentLabel:ParentName}' \
  --output table

echo ""
echo "✅ Content moderation analysis complete"
echo "(Empty result means no inappropriate content detected)"
```

---

## Step 15 – Analyze Image Properties

```bash
echo ""
echo "Getting image properties and quality..."

# Analyze image quality metrics (brightness and sharpness)
aws rekognition detect-faces \
  --image "{\"S3Object\":{\"Bucket\":\"${BUCKET_NAME}\",\"Name\":\"person1.jpg\"}}" \
  --attributes "ALL" \
  --region "$REGION" \
  --query 'FaceDetails[0].Quality.{Brightness:Brightness,Sharpness:Sharpness}' \
  --output table
```

---

## Step 16 – Create Python Script for Batch Analysis

```bash
echo ""
echo "Creating Python script for batch image analysis..."

# Create Python script in images directory
cd "$REPO_DIR/rekognition-images"

cat > batch_analyze.py <<'EOF'
import boto3
import sys

rekognition = boto3.client('rekognition')

def analyze_image(bucket, image_name):
    """Analyze single image with Rekognition"""
    print(f"\n{'='*50}")
    print(f"Analyzing: {image_name}")
    print('='*50)
    
    # Detect labels
    response = rekognition.detect_labels(
        Image={'S3Object': {'Bucket': bucket, 'Name': image_name}},
        MaxLabels=5,
        MinConfidence=75
    )
    
    print(f"\n📋 Top Labels:")
    for label in response['Labels']:
        print(f"  - {label['Name']}: {label['Confidence']:.2f}%")
    
    # Detect faces
    try:
        face_response = rekognition.detect_faces(
            Image={'S3Object': {'Bucket': bucket, 'Name': image_name}},
            Attributes=['ALL']
        )
        
        if face_response['FaceDetails']:
            print(f"\n👤 Faces Detected: {len(face_response['FaceDetails'])}")
            for idx, face in enumerate(face_response['FaceDetails'], 1):
                age = face['AgeRange']
                gender = face['Gender']['Value']
                emotions = sorted(face['Emotions'], 
                                key=lambda x: x['Confidence'], 
                                reverse=True)
                print(f"  Face {idx}:")
                print(f"    Age: {age['Low']}-{age['High']} years")
                print(f"    Gender: {gender}")
                print(f"    Emotion: {emotions[0]['Type']}")
    except Exception as e:
        print(f"\n👤 No faces detected")

if __name__ == '__main__':
    bucket = sys.argv[1]
    images = sys.argv[2:]
    
    for image in images:
        analyze_image(bucket, image)
EOF

```

---

## Step 17 – Run Batch Analysis

```bash
echo ""
echo "Running batch analysis on all images..."
echo ""

# Navigate to images directory and run Python script
cd "$REPO_DIR/rekognition-images"

python3 batch_analyze.py "$BUCKET_NAME" \
  person1.jpg \
  person2.jpg \
  group.jpg \
  street.jpg \
  text-sign.jpg
```

---

## Step 18 – Cleanup

```bash
echo ""
echo "Cleaning up resources..."

# Get all face IDs from collection
FACE_IDS=$(aws rekognition list-faces \
  --collection-id "$COLLECTION_ID" \
  --region "$REGION" \
  --query 'Faces[*].FaceId' \
  --output text)

# Delete each face from collection
if [ ! -z "$FACE_IDS" ]; then
    for face_id in $FACE_IDS; do
        aws rekognition delete-faces \
          --collection-id "$COLLECTION_ID" \
          --face-ids "$face_id" \
          --region "$REGION" >/dev/null 2>&1
    done
fi

# Delete face collection
aws rekognition delete-collection \
  --collection-id "$COLLECTION_ID" \
  --region "$REGION"

# Delete all images from S3 bucket
aws s3 rm s3://"$BUCKET_NAME" --recursive --region "$REGION"

# Delete S3 bucket
aws s3api delete-bucket --bucket "$BUCKET_NAME" --region "$REGION"

# Remove local images directory and Python script
cd "$REPO_DIR"
rm -rf rekognition-images

echo ""
echo "✅ Lab 11.A cleanup complete!"
```

---

## Summary

In this lab, you have:
- Created S3 bucket and uploaded test images
- Detected faces with detailed attributes (age, gender, emotions)
- Analyzed multiple faces in group photos
- Detected objects, scenes, and activities with labels
- Extracted text from images using OCR
- Compared faces across different images
- Created face collection for searchable face database
- Indexed and searched faces in collection
- Performed content moderation analysis
- Analyzed image quality properties
- Created Python script for batch analysis

**Key Takeaways:**
- **No ML Expertise Required**: Simple API calls for complex ML tasks
- **Face Detection**: Age, gender, emotions, facial features
- **Label Detection**: Objects, scenes, activities with confidence scores
- **Text Detection**: OCR for extracting text from images
- **Face Collections**: Store and search faces at scale
- **Content Moderation**: Detect inappropriate content automatically

**Common Use Cases:**
- **Security**: Face-based access control and verification
- **Media**: Auto-tagging photos, content moderation
- **Retail**: Customer demographics, sentiment analysis
- **Documents**: Text extraction from scanned documents
- **Social Media**: Photo organization, celebrity recognition

---

## Best Practices

**Image Quality:**
- Use high-resolution images (minimum 80x80 pixels)
- Ensure good lighting and contrast
- Face detection works best with frontal faces
- Supported formats: JPEG, PNG

**Performance:**
- Batch process multiple images for efficiency
- Use S3 for large-scale processing
- Implement caching for repeated analysis
- Use async operations for video analysis

**Cost Optimization:**
- Monitor free tier usage (5,000 images/month)
- Use minimum confidence thresholds to reduce false positives
- Cache results to avoid duplicate analysis
- Consider batch pricing for high volume

**Security:**
- Use IAM roles with least privilege
- Encrypt images in S3
- Use VPC endpoints for private access
- Enable CloudTrail for audit logging

**Face Collections:**
- Use descriptive ExternalImageIds
- Implement face deduplication logic
- Regular cleanup of stale faces
- Monitor collection limits (20M faces/collection)

---

## Production Enhancements

1. **Lambda Integration**
   ```python
   # Trigger Rekognition on S3 upload
   def lambda_handler(event, context):
       bucket = event['Records'][0]['s3']['bucket']['name']
       key = event['Records'][0]['s3']['object']['key']
       
       response = rekognition.detect_labels(
           Image={'S3Object': {'Bucket': bucket, 'Name': key}}
       )
       # Store results in DynamoDB
   ```

2. **Real-Time Video Analysis**
   ```bash
   # Analyze video streams
   aws rekognition start-stream-processor \
     --name my-stream-processor
   ```

3. **Custom Labels**
   ```bash
   # Train custom models for specific objects
   aws rekognition create-project \
     --project-name my-custom-model
   ```

4. **SNS Notifications**
   ```bash
   # Alert on specific detections
   aws sns publish \
     --topic-arn $SNS_TOPIC \
     --message "Face detected with confidence 99%"
   ```

---

## Troubleshooting

**Access denied errors:**
- Check IAM permissions for Rekognition and S3
- Verify bucket policy allows Rekognition access
- Ensure images are in correct region

**No faces detected:**
- Check image quality and resolution
- Verify face is clearly visible and frontal
- Adjust minimum confidence threshold
- Ensure image format is supported

**Low confidence scores:**
- Improve image quality (lighting, resolution)
- Use clearer, higher-quality images
- Check for occlusions (sunglasses, masks)
- Adjust confidence thresholds

**Collection errors:**
- Collection must be in same region as API calls
- Check collection limits (20M faces max)
- Verify unique ExternalImageIds
- Ensure faces are indexed before searching

---

## Additional Resources

- [Amazon Rekognition Documentation](https://docs.aws.amazon.com/rekognition/)
- [Rekognition API Reference](https://docs.aws.amazon.com/rekognition/latest/dg/API_Reference.html)
- [Best Practices Guide](https://docs.aws.amazon.com/rekognition/latest/dg/best-practices.html)
- [Rekognition Pricing](https://aws.amazon.com/rekognition/pricing/)
- [Face Detection Guidelines](https://docs.aws.amazon.com/rekognition/latest/dg/faces-detect-images.html)
