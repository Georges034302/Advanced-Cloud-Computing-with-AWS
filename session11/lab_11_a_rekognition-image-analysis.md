# Lab 11.A: Amazon Rekognition - Image Analysis and Face Detection

## Overview
This lab introduces Amazon Rekognition for image analysis using machine learning without requiring ML expertise. You'll detect faces, analyze facial attributes, identify objects and scenes, detect text in images, and compare faces across different images.

**💰 Cost**: FREE TIER (5,000 images/month for 12 months)

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
# Set region
REGION="ap-southeast-2"
export AWS_REGION="$REGION"
echo "REGION=$REGION"

# Get account ID
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# Set bucket name
BUCKET_NAME="rekognition-demo-${ACCOUNT_ID}"
echo "BUCKET_NAME=$BUCKET_NAME"

# Create S3 bucket
echo ""
echo "Creating S3 bucket for images..."

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

echo "✅ S3 bucket created: $BUCKET_NAME"
```

---

## Step 2 – Create Test Images Directory

```bash
echo ""
echo "Creating test images directory..."

mkdir -p /tmp/rekognition-images
cd /tmp/rekognition-images

echo "✅ Directory created: $(pwd)"
```

---

## Step 3 – Download Sample Images

```bash
echo ""
echo "Downloading sample images for testing..."

# Download sample images (free stock photos)
curl -s -o person1.jpg "https://images.pexels.com/photos/220453/pexels-photo-220453.jpeg?w=500"
curl -s -o person2.jpg "https://images.pexels.com/photos/774909/pexels-photo-774909.jpeg?w=500"
curl -s -o group.jpg "https://images.pexels.com/photos/1270171/pexels-photo-1270171.jpeg?w=500"
curl -s -o street.jpg "https://images.pexels.com/photos/2253879/pexels-photo-2253879.jpeg?w=500"
curl -s -o text-sign.jpg "https://images.pexels.com/photos/262470/pexels-photo-262470.jpeg?w=500"

echo "✅ Sample images downloaded"
echo ""
ls -lh *.jpg
```

---

## Step 4 – Upload Images to S3

```bash
echo ""
echo "Uploading images to S3..."

# Upload all images
for img in *.jpg; do
    aws s3 cp "$img" s3://"$BUCKET_NAME"/ \
      --region "$REGION"
    echo "Uploaded: $img"
done

echo ""
echo "✅ All images uploaded to S3"

# List uploaded images
aws s3 ls s3://"$BUCKET_NAME"/ --region "$REGION"
```

---

## Step 5 – Detect Faces in Image

```bash
echo ""
echo "================================================"
echo "FACE DETECTION - Analyzing person1.jpg"
echo "================================================"
echo ""

# Detect faces with attributes
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

echo ""
echo "✅ Face attributes detected"
```

---

## Step 6 – Analyze All Emotions

```bash
echo ""
echo "Analyzing emotions in detail..."

aws rekognition detect-faces \
  --image "{\"S3Object\":{\"Bucket\":\"${BUCKET_NAME}\",\"Name\":\"person1.jpg\"}}" \
  --attributes "ALL" \
  --region "$REGION" \
  --query 'FaceDetails[0].Emotions[*].{Emotion:Type,Confidence:Confidence}' \
  --output table

echo ""
echo "✅ Emotion analysis complete"
```

---

## Step 7 – Detect Multiple Faces in Group Photo

```bash
echo ""
echo "================================================"
echo "MULTIPLE FACE DETECTION - Analyzing group.jpg"
echo "================================================"
echo ""

# Detect all faces in group photo
FACE_COUNT=$(aws rekognition detect-faces \
  --image "{\"S3Object\":{\"Bucket\":\"${BUCKET_NAME}\",\"Name\":\"group.jpg\"}}" \
  --region "$REGION" \
  --query 'length(FaceDetails)' \
  --output text)

echo "Number of faces detected: $FACE_COUNT"
echo ""

# Show details for each face
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

echo ""
echo "✅ Multiple faces analyzed"
```

---

## Step 8 – Detect Labels (Objects and Scenes)

```bash
echo ""
echo "================================================"
echo "LABEL DETECTION - Analyzing street.jpg"
echo "================================================"
echo ""

# Detect labels (objects, scenes, activities)
aws rekognition detect-labels \
  --image "{\"S3Object\":{\"Bucket\":\"${BUCKET_NAME}\",\"Name\":\"street.jpg\"}}" \
  --max-labels 10 \
  --min-confidence 75 \
  --region "$REGION" \
  --query 'Labels[*].{Label:Name,Confidence:Confidence,Parents:Parents[*].Name}' \
  --output table

echo ""
echo "✅ Labels detected with confidence scores"
```

---

## Step 9 – Detect Text in Images (OCR)

```bash
echo ""
echo "================================================"
echo "TEXT DETECTION - Analyzing text-sign.jpg"
echo "================================================"
echo ""

# Detect text in image
aws rekognition detect-text \
  --image "{\"S3Object\":{\"Bucket\":\"${BUCKET_NAME}\",\"Name\":\"text-sign.jpg\"}}" \
  --region "$REGION" \
  --query 'TextDetections[?Type==`LINE`].{Text:DetectedText,Confidence:Confidence}' \
  --output table

echo ""
echo "✅ Text extracted from image (OCR)"
```

---

## Step 10 – Compare Two Faces

```bash
echo ""
echo "================================================"
echo "FACE COMPARISON - Comparing person1.jpg vs person2.jpg"
echo "================================================"
echo ""

# Compare two faces
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
echo ""
echo "✅ Face comparison complete"
```

---

## Step 11 – Create Collection for Face Storage

```bash
echo ""
echo "================================================"
echo "CREATING FACE COLLECTION"
echo "================================================"
echo ""

COLLECTION_ID="employees-collection"
echo "COLLECTION_ID=$COLLECTION_ID"

# Create collection
aws rekognition create-collection \
  --collection-id "$COLLECTION_ID" \
  --region "$REGION"

echo ""
echo "✅ Face collection created"

# List collections
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

# Index face with external ID
FACE_ID=$(aws rekognition index-faces \
  --collection-id "$COLLECTION_ID" \
  --image "{\"S3Object\":{\"Bucket\":\"${BUCKET_NAME}\",\"Name\":\"person1.jpg\"}}" \
  --external-image-id "employee-001" \
  --detection-attributes "ALL" \
  --region "$REGION" \
  --query 'FaceRecords[0].Face.FaceId' \
  --output text)

echo "FACE_ID=$FACE_ID"
echo ""
echo "✅ Face indexed in collection"

# List faces in collection
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

# Search for face by image
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

echo ""
echo "✅ Face search complete"
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

# Detect image quality
aws rekognition detect-faces \
  --image "{\"S3Object\":{\"Bucket\":\"${BUCKET_NAME}\",\"Name\":\"person1.jpg\"}}" \
  --attributes "ALL" \
  --region "$REGION" \
  --query 'FaceDetails[0].Quality.{Brightness:Brightness,Sharpness:Sharpness}' \
  --output table

echo ""
echo "✅ Image quality metrics retrieved"
```

---

## Step 16 – Create Python Script for Batch Analysis

```bash
echo ""
echo "Creating Python script for batch image analysis..."

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

echo "✅ Python script created: batch_analyze.py"
```

---

## Step 17 – Run Batch Analysis

```bash
echo ""
echo "Running batch analysis on all images..."

python3 batch_analyze.py "$BUCKET_NAME" \
  person1.jpg \
  person2.jpg \
  group.jpg \
  street.jpg \
  text-sign.jpg

echo ""
echo "✅ Batch analysis complete"
```

---

## Step 18 – Get Rekognition Usage Statistics

```bash
echo ""
echo "Checking Rekognition API usage..."

echo ""
echo "Note: Usage statistics are available in AWS Cost Explorer"
echo "Free tier includes 5,000 images/month for 12 months"
echo ""
echo "Services used in this lab:"
echo "  - DetectFaces: Face detection and attributes"
echo "  - DetectLabels: Object and scene detection"
echo "  - DetectText: Text extraction (OCR)"
echo "  - CompareFaces: Face comparison"
echo "  - IndexFaces: Store faces in collection"
echo "  - SearchFacesByImage: Search for faces"
echo "  - DetectModerationLabels: Content moderation"
```

---

## Step 19 – Cleanup

```bash
echo ""
echo "Cleaning up resources..."

# Delete all faces from collection
echo "Deleting faces from collection..."

FACE_IDS=$(aws rekognition list-faces \
  --collection-id "$COLLECTION_ID" \
  --region "$REGION" \
  --query 'Faces[*].FaceId' \
  --output text)

if [ ! -z "$FACE_IDS" ]; then
    for face_id in $FACE_IDS; do
        aws rekognition delete-faces \
          --collection-id "$COLLECTION_ID" \
          --face-ids "$face_id" \
          --region "$REGION" >/dev/null 2>&1
    done
    echo "✅ Faces deleted from collection"
fi

# Delete collection
aws rekognition delete-collection \
  --collection-id "$COLLECTION_ID" \
  --region "$REGION"

echo "✅ Collection deleted"

# Empty and delete S3 bucket
aws s3 rm s3://"$BUCKET_NAME" --recursive --region "$REGION"
aws s3api delete-bucket --bucket "$BUCKET_NAME" --region "$REGION"

echo "✅ S3 bucket deleted"
echo ""
echo "All resources cleaned up!"
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
