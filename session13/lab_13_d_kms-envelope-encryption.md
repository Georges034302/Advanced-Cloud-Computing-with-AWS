# Lab 13.D: AWS KMS - Envelope Encryption with Customer Managed Keys

## Overview
This lab introduces AWS Key Management Service (KMS) and demonstrates envelope encryption, a security pattern where KMS manages master keys (CMKs) that encrypt Data Encryption Keys (DEKs), which in turn encrypt your application data. You'll create KMS keys, implement envelope encryption using Python, securely store encrypted data in S3, and perform decryption workflows.

**💰 Cost**: KMS: $1/month per CMK + $0.03 per 10,000 requests. Minimal cost for short lab.

---

## Objectives
- Create AWS KMS Customer Managed Key (CMK)
- Configure key policies and permissions
- Generate Data Encryption Keys (DEKs)
- Implement envelope encryption pattern
- Encrypt data locally using AES-256
- Store encrypted DEK and ciphertext in S3
- Perform secure decryption workflow
- Enable automatic key rotation
- Understand key lifecycle management

---

## Prerequisites
- AWS CLI configured (`aws configure`)
- IAM permissions for KMS (CreateKey, GenerateDataKey, Decrypt) and S3
- Python 3 installed with pip
- Region: ap-southeast-2
- Basic understanding of encryption concepts

---

## Architecture

```
Envelope Encryption Pattern:

1. Create CMK in KMS
         ↓
2. Generate DEK from CMK
   ├─ Plaintext DEK (for local encryption)
   └─ Encrypted DEK (stored with data)
         ↓
3. Encrypt Data Locally
   - Use Plaintext DEK with AES-256
   - Delete Plaintext DEK from memory
         ↓
4. Store in S3
   - Encrypted Data
   - Encrypted DEK
         ↓
5. Decrypt Workflow
   - Retrieve Encrypted DEK
   - Call KMS to decrypt DEK
   - Use Plaintext DEK to decrypt data
   - Delete Plaintext DEK from memory

Benefits:
- Master key never leaves KMS
- Data encrypted locally (performance)
- Encrypted DEK stored with data (scalable)
- Fine-grained access control via IAM
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

# Set bucket name
BUCKET_NAME="kms-envelope-demo-${ACCOUNT_ID}"
echo "BUCKET_NAME=$BUCKET_NAME"
echo ""
echo "================================================"
echo "AWS KMS ENVELOPE ENCRYPTION LAB"
echo "================================================"
```

---

## Step 2 – Create S3 Bucket for Encrypted Data

```bash
echo ""
echo "Creating S3 bucket for encrypted data storage..."

# Create bucket
aws s3api create-bucket \
  --bucket "$BUCKET_NAME" \
  --region "$REGION" \
  --create-bucket-configuration LocationConstraint="$REGION"

echo "✅ Bucket created: $BUCKET_NAME"

# Enable encryption at rest
echo "Enabling bucket encryption..."

aws s3api put-bucket-encryption \
  --bucket "$BUCKET_NAME" \
  --server-side-encryption-configuration '{
    "Rules": [{
      "ApplyServerSideEncryptionByDefault": {
        "SSEAlgorithm": "AES256"
      },
      "BucketKeyEnabled": true
    }]
  }'

echo "✅ Bucket encryption enabled"
```

---

## Step 3 – Create KMS Customer Managed Key (CMK)

```bash
echo ""
echo "================================================"
echo "CREATING KMS CUSTOMER MANAGED KEY"
echo "================================================"
echo ""

# Create CMK
echo "Creating KMS Customer Managed Key..."

KEY_ID=$(aws kms create-key \
  --description "CMK for envelope encryption demonstration" \
  --key-usage ENCRYPT_DECRYPT \
  --origin AWS_KMS \
  --region "$REGION" \
  --query 'KeyMetadata.KeyId' \
  --output text)

echo "KEY_ID=$KEY_ID"
echo "✅ KMS CMK created"
```

---

## Step 4 – Create Key Alias

```bash
echo ""
echo "Creating key alias for easier reference..."

# Create alias
ALIAS_NAME="alias/envelope-encryption-demo"
echo "ALIAS_NAME=$ALIAS_NAME"

aws kms create-alias \
  --alias-name "$ALIAS_NAME" \
  --target-key-id "$KEY_ID" \
  --region "$REGION"

echo "✅ Alias created: $ALIAS_NAME"
```

---

## Step 5 – View Key Details

```bash
echo ""
echo "Retrieving key details..."

# Describe key
aws kms describe-key \
  --key-id "$KEY_ID" \
  --region "$REGION" \
  --query 'KeyMetadata.{KeyId:KeyId,State:KeyState,CreationDate:CreationDate,Enabled:Enabled}' \
  --output json

echo ""
echo "✅ Key is active and ready for use"
```

---

## Step 6 – Enable Automatic Key Rotation

```bash
echo ""
echo "Enabling automatic key rotation (annual)..."

# Enable rotation
aws kms enable-key-rotation \
  --key-id "$KEY_ID" \
  --region "$REGION"

echo "✅ Key rotation enabled"

# Verify rotation status
ROTATION_STATUS=$(aws kms get-key-rotation-status \
  --key-id "$KEY_ID" \
  --region "$REGION" \
  --query 'KeyRotationEnabled' \
  --output text)

echo "Rotation Status: $ROTATION_STATUS"
```

---

## Step 7 – Generate Data Encryption Key (DEK)

```bash
echo ""
echo "================================================"
echo "GENERATING DATA ENCRYPTION KEY"
echo "================================================"
echo ""

# Generate DEK
echo "Requesting KMS to generate a 256-bit AES data key..."

aws kms generate-data-key \
  --key-id "$KEY_ID" \
  --key-spec AES_256 \
  --region "$REGION" \
  --output json > /tmp/dek.json

echo "✅ Data Encryption Key generated"
echo ""
echo "The response contains:"
echo "  - Plaintext: Base64-encoded plaintext DEK (for local encryption)"
echo "  - CiphertextBlob: Encrypted DEK (to store with encrypted data)"
```

---

## Step 8 – Extract and Save Keys

```bash
echo ""
echo "Extracting plaintext and encrypted DEK..."

# Extract plaintext DEK (base64 encoded)
PLAINTEXT_DEK_B64=$(jq -r '.Plaintext' /tmp/dek.json)
echo "$PLAINTEXT_DEK_B64" | base64 -d > /tmp/plaintext_dek.bin

echo "Plaintext DEK saved: /tmp/plaintext_dek.bin"

# Extract encrypted DEK
ENCRYPTED_DEK_B64=$(jq -r '.CiphertextBlob' /tmp/dek.json)
echo "$ENCRYPTED_DEK_B64" > /tmp/encrypted_dek.b64

echo "Encrypted DEK saved: /tmp/encrypted_dek.b64"
echo ""
echo "✅ Keys extracted and saved"
```

---

## Step 9 – Install Python Cryptography Library

```bash
echo ""
echo "Installing Python cryptography library..."

# Install cryptography
pip3 install cryptography boto3 --quiet

echo "✅ Python libraries installed"
```

---

## Step 10 – Create Sample Sensitive Data

```bash
echo ""
echo "Creating sample sensitive data file..."

# Create data file with sensitive information
cat > /tmp/sensitive_data.txt <<EOF
===========================================
CONFIDENTIAL CUSTOMER DATA
===========================================

Customer ID: 12345
Name: John Doe
SSN: 123-45-6789
Credit Card: 4532-1234-5678-9010
Account Balance: \$50,000

Generated: $(date)
Region: $REGION
Account: $ACCOUNT_ID
===========================================
EOF

echo "Sample data created: /tmp/sensitive_data.txt"
echo ""
cat /tmp/sensitive_data.txt
echo ""
echo "✅ Sensitive data prepared for encryption"
```

---

## Step 11 – Create Python Encryption Script

```bash
echo ""
echo "Creating encryption script..."

# Create encryption script
cat > /tmp/encrypt_data.py <<'EOF'
#!/usr/bin/env python3
import os
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

def encrypt_file(plaintext_dek_path, input_file, output_file):
    """
    Encrypt a file using AES-256-GCM with the plaintext DEK
    """
    # Read the plaintext DEK (32 bytes for AES-256)
    with open(plaintext_dek_path, 'rb') as f:
        key = f.read()
    
    print(f"✓ Loaded plaintext DEK ({len(key)} bytes)")
    
    # Generate random IV (96 bits for GCM)
    iv = os.urandom(12)
    print(f"✓ Generated random IV ({len(iv)} bytes)")
    
    # Read plaintext data
    with open(input_file, 'rb') as f:
        plaintext = f.read()
    
    print(f"✓ Loaded plaintext data ({len(plaintext)} bytes)")
    
    # Create cipher
    cipher = Cipher(
        algorithms.AES(key),
        modes.GCM(iv),
        backend=default_backend()
    )
    encryptor = cipher.encryptor()
    
    # Encrypt data
    ciphertext = encryptor.update(plaintext) + encryptor.finalize()
    
    # Get authentication tag
    tag = encryptor.tag
    
    print(f"✓ Encrypted data ({len(ciphertext)} bytes)")
    
    # Write IV + tag + ciphertext to output file
    with open(output_file, 'wb') as f:
        f.write(iv)
        f.write(tag)
        f.write(ciphertext)
    
    print(f"✓ Saved encrypted data to {output_file}")
    print(f"  - IV: {len(iv)} bytes")
    print(f"  - Tag: {len(tag)} bytes")
    print(f"  - Ciphertext: {len(ciphertext)} bytes")
    
    return True

if __name__ == "__main__":
    plaintext_dek = "/tmp/plaintext_dek.bin"
    input_file = "/tmp/sensitive_data.txt"
    output_file = "/tmp/encrypted_data.bin"
    
    print("\n" + "="*50)
    print("ENCRYPTING DATA WITH PLAINTEXT DEK")
    print("="*50 + "\n")
    
    encrypt_file(plaintext_dek, input_file, output_file)
    
    print("\n✅ Encryption complete!")
    print("⚠️  Plaintext DEK should now be deleted from memory")
EOF

chmod +x /tmp/encrypt_data.py

echo "✅ Encryption script created"
```

---

## Step 12 – Run Encryption

```bash
echo ""
echo "================================================"
echo "ENCRYPTING DATA LOCALLY"
echo "================================================"
echo ""

# Run encryption
python3 /tmp/encrypt_data.py

echo ""
echo "Verifying encrypted file..."
ls -lh /tmp/encrypted_data.bin

echo ""
echo "✅ Data encrypted successfully"
```

---

## Step 13 – Upload Encrypted Data and Encrypted DEK to S3

```bash
echo ""
echo "Uploading encrypted data and encrypted DEK to S3..."

# Upload encrypted data
aws s3 cp /tmp/encrypted_data.bin \
  s3://"$BUCKET_NAME"/encrypted_data.bin \
  --region "$REGION"

echo "✅ Encrypted data uploaded"

# Upload encrypted DEK
aws s3 cp /tmp/encrypted_dek.b64 \
  s3://"$BUCKET_NAME"/encrypted_dek.b64 \
  --region "$REGION"

echo "✅ Encrypted DEK uploaded"
echo ""

# List S3 contents
echo "S3 bucket contents:"
aws s3 ls s3://"$BUCKET_NAME"/ --region "$REGION"

echo ""
echo "✅ All encrypted artifacts stored in S3"
```

---

## Step 14 – Delete Local Plaintext Artifacts

```bash
echo ""
echo "Deleting local plaintext artifacts (security best practice)..."

# Delete plaintext DEK and original data
rm -f /tmp/plaintext_dek.bin
rm -f /tmp/sensitive_data.txt
rm -f /tmp/dek.json

echo "✅ Plaintext artifacts deleted"
echo "   Only encrypted data remains"
```

---

## Step 15 – Create Python Decryption Script

```bash
echo ""
echo "Creating decryption script..."

# Create decryption script
cat > /tmp/decrypt_data.py <<'EOF'
#!/usr/bin/env python3
import base64
import boto3
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

def decrypt_file(encrypted_dek_path, encrypted_file, output_file, region):
    """
    Decrypt a file using envelope encryption pattern:
    1. Call KMS to decrypt the DEK
    2. Use plaintext DEK to decrypt the data
    """
    # Initialize KMS client
    kms = boto3.client('kms', region_name=region)
    
    print("✓ Initialized KMS client")
    
    # Read encrypted DEK (base64 encoded)
    with open(encrypted_dek_path, 'r') as f:
        encrypted_dek_b64 = f.read().strip()
    
    print("✓ Loaded encrypted DEK")
    
    # Call KMS to decrypt the DEK
    print("✓ Calling KMS to decrypt DEK...")
    response = kms.decrypt(
        CiphertextBlob=base64.b64decode(encrypted_dek_b64)
    )
    
    plaintext_dek = response['Plaintext']
    print(f"✓ KMS decrypted DEK ({len(plaintext_dek)} bytes)")
    
    # Read encrypted data (IV + tag + ciphertext)
    with open(encrypted_file, 'rb') as f:
        encrypted_data = f.read()
    
    # Extract IV, tag, and ciphertext
    iv = encrypted_data[:12]  # First 12 bytes
    tag = encrypted_data[12:28]  # Next 16 bytes
    ciphertext = encrypted_data[28:]  # Remaining bytes
    
    print(f"✓ Loaded encrypted data:")
    print(f"  - IV: {len(iv)} bytes")
    print(f"  - Tag: {len(tag)} bytes")
    print(f"  - Ciphertext: {len(ciphertext)} bytes")
    
    # Create cipher for decryption
    cipher = Cipher(
        algorithms.AES(plaintext_dek),
        modes.GCM(iv, tag),
        backend=default_backend()
    )
    decryptor = cipher.decryptor()
    
    # Decrypt data
    plaintext = decryptor.update(ciphertext) + decryptor.finalize()
    
    print(f"✓ Decrypted data ({len(plaintext)} bytes)")
    
    # Write decrypted data to file
    with open(output_file, 'wb') as f:
        f.write(plaintext)
    
    print(f"✓ Saved decrypted data to {output_file}")
    
    return plaintext

if __name__ == "__main__":
    import sys
    import os
    
    region = os.environ.get('AWS_REGION', 'ap-southeast-2')
    encrypted_dek = "/tmp/encrypted_dek.b64"
    encrypted_file = "/tmp/encrypted_data.bin"
    output_file = "/tmp/decrypted_data.txt"
    
    print("\n" + "="*50)
    print("DECRYPTING DATA WITH ENVELOPE ENCRYPTION")
    print("="*50 + "\n")
    
    plaintext = decrypt_file(encrypted_dek, encrypted_file, output_file, region)
    
    print("\n" + "="*50)
    print("DECRYPTED CONTENT:")
    print("="*50 + "\n")
    print(plaintext.decode('utf-8'))
    
    print("\n✅ Decryption complete!")
    print("⚠️  Plaintext DEK deleted from memory")
EOF

chmod +x /tmp/decrypt_data.py

echo "✅ Decryption script created"
```

---

## Step 16 – Download Encrypted Artifacts from S3

```bash
echo ""
echo "Downloading encrypted artifacts from S3..."

# Download encrypted DEK
aws s3 cp s3://"$BUCKET_NAME"/encrypted_dek.b64 \
  /tmp/encrypted_dek.b64 \
  --region "$REGION"

echo "✅ Encrypted DEK downloaded"

# Download encrypted data
aws s3 cp s3://"$BUCKET_NAME"/encrypted_data.bin \
  /tmp/encrypted_data.bin \
  --region "$REGION"

echo "✅ Encrypted data downloaded"
```

---

## Step 17 – Run Decryption

```bash
echo ""
echo "================================================"
echo "DECRYPTING DATA"
echo "================================================"
echo ""

# Run decryption
python3 /tmp/decrypt_data.py

echo ""
echo "✅ Data decrypted successfully!"
```

---

## Step 18 – Verify Decryption Matches Original

```bash
echo ""
echo "Verifying decrypted content..."
echo ""

# Display decrypted file
cat /tmp/decrypted_data.txt

echo ""
echo "✅ Decryption successful - original data recovered"
```

---

## Step 19 – View KMS Key Usage

```bash
echo ""
echo "================================================"
echo "KMS KEY INFORMATION"
echo "================================================"
echo ""

# View key details
echo "Key Details:"
aws kms describe-key \
  --key-id "$KEY_ID" \
  --region "$REGION" \
  --query 'KeyMetadata.{KeyId:KeyId,State:KeyState,Description:Description,CreationDate:CreationDate}' \
  --output table

echo ""

# Check rotation status
echo "Key Rotation Status:"
aws kms get-key-rotation-status \
  --key-id "$KEY_ID" \
  --region "$REGION" \
  --output table

echo ""

# List aliases
echo "Key Aliases:"
aws kms list-aliases \
  --region "$REGION" \
  --query "Aliases[?TargetKeyId=='$KEY_ID']" \
  --output table

echo ""
echo "✅ Key information retrieved"
```

---

## Step 20 – Cleanup

```bash
echo ""
echo "================================================"
echo "CLEANUP"
echo "================================================"
echo ""

echo "Cleaning up resources..."

# Delete S3 bucket contents
echo "Deleting S3 bucket contents..."
aws s3 rm s3://"$BUCKET_NAME" \
  --recursive \
  --region "$REGION"

echo "✅ Bucket contents deleted"

# Delete S3 bucket
aws s3api delete-bucket \
  --bucket "$BUCKET_NAME" \
  --region "$REGION"

echo "✅ Bucket deleted"

# Delete key alias
echo "Deleting key alias..."
aws kms delete-alias \
  --alias-name "$ALIAS_NAME" \
  --region "$REGION"

echo "✅ Alias deleted"

# Schedule key deletion (minimum 7 days)
echo "Scheduling KMS key deletion (7 day waiting period)..."

aws kms schedule-key-deletion \
  --key-id "$KEY_ID" \
  --pending-window-in-days 7 \
  --region "$REGION"

echo "✅ KMS key scheduled for deletion in 7 days"

# Delete local files
echo "Deleting local files..."
rm -f /tmp/encrypted_data.bin
rm -f /tmp/encrypted_dek.b64
rm -f /tmp/decrypted_data.txt
rm -f /tmp/encrypt_data.py
rm -f /tmp/decrypt_data.py

echo "✅ Local files deleted"
echo ""
echo "All resources cleaned up!"
echo ""
echo "Note: KMS key will be deleted after 7-day waiting period"
echo "      Cancel with: aws kms cancel-key-deletion --key-id $KEY_ID"
```

---

## Summary

In this lab, you have:
- Created AWS KMS Customer Managed Key (CMK)
- Configured key alias for easier management
- Enabled automatic annual key rotation
- Generated Data Encryption Key (DEK) from CMK
- Implemented envelope encryption pattern
- Encrypted sensitive data locally using AES-256-GCM
- Stored encrypted DEK with encrypted data in S3
- Deleted plaintext artifacts for security
- Retrieved encrypted data from S3
- Performed decryption using KMS to decrypt DEK
- Verified successful decryption workflow
- Managed key lifecycle and cleanup

**Key Takeaways:**
- **Master Key Protection**: CMK never leaves KMS hardware
- **Local Encryption**: Data encrypted locally for performance
- **Scalability**: Each data object has its own DEK
- **Security**: Plaintext DEK exists only during encryption/decryption
- **Access Control**: IAM policies control who can use keys

---

## Best Practices

**Key Management:**
- Use Customer Managed Keys (CMK) for full control
- Enable automatic key rotation annually
- Use key aliases for easier key management
- Never export or log plaintext keys
- Use separate keys for different applications

**Encryption:**
- Always use authenticated encryption (AES-GCM)
- Generate unique random IVs for each encryption
- Store encrypted DEK with encrypted data
- Delete plaintext DEK immediately after use
- Use secure random number generators

**Access Control:**
- Use IAM policies for key usage permissions
- Enable KMS key policies for additional control
- Use VPC endpoints for private KMS access
- Enable CloudTrail logging for all KMS operations
- Implement least privilege access

**Storage:**
- Store encrypted data and encrypted DEK together
- Use S3 bucket encryption as additional layer
- Enable S3 versioning for encrypted objects
- Use S3 bucket policies for access control
- Consider S3 Object Lock for compliance

**Monitoring:**
- Enable CloudTrail for KMS API calls
- Set up CloudWatch alarms for unusual usage
- Monitor key usage patterns
- Review access logs regularly
- Alert on key policy changes

---

## Troubleshooting

**AccessDeniedException when creating key:**
- Verify IAM permissions include `kms:CreateKey`
- Check account limits (default: 10,000 CMKs)
- Ensure proper service control policies (SCPs)

**GenerateDataKey fails:**
- Verify key state is ENABLED
- Check IAM permissions: `kms:GenerateDataKey`
- Ensure key policy allows your principal
- Verify key is not pending deletion

**Decrypt operation fails:**
- Verify IAM permissions: `kms:Decrypt`
- Ensure encrypted DEK was encrypted with same CMK
- Check if key is in correct region
- Verify key policy allows decryption

**Python encryption script errors:**
- Install cryptography: `pip3 install cryptography boto3`
- Verify Python version (3.6+)
- Check file paths are correct
- Ensure sufficient disk space

**Decrypted data is corrupted:**
- Verify IV is extracted correctly (first 12 bytes)
- Ensure tag is extracted correctly (next 16 bytes)
- Check that ciphertext length matches
- Verify no encoding issues (base64, etc.)

**KMS key deletion fails:**
- Cannot delete key with aliases attached
- Cannot delete key used by AWS services
- Must schedule deletion (7-30 day window)
- Check CloudTrail for key usage

**High KMS costs:**
- Each GenerateDataKey call costs $0.03/10K
- Each Decrypt call costs $0.03/10K
- Cache DEKs when encrypting multiple objects
- Use AWS managed keys for AWS services

---

## Additional Resources

- [AWS KMS Documentation](https://docs.aws.amazon.com/kms/)
- [Envelope Encryption](https://docs.aws.amazon.com/kms/latest/developerguide/concepts.html#enveloping)
- [KMS Best Practices](https://docs.aws.amazon.com/kms/latest/developerguide/best-practices.html)
- [KMS Key Policies](https://docs.aws.amazon.com/kms/latest/developerguide/key-policies.html)
- [KMS Pricing](https://aws.amazon.com/kms/pricing/)
- [Python Cryptography Library](https://cryptography.io/)
- [AWS KMS API Reference](https://docs.aws.amazon.com/kms/latest/APIReference/)
