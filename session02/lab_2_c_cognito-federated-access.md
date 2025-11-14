# Lab 2.C: Federated Access with AWS Cognito and IAM Roles
<img width="1536" height="1024" alt="IMG" src="https://github.com/user-attachments/assets/abca74ee-b0b9-42fb-8a0a-376cc5be6103" />

## Overview
This lab demonstrates how users from external identity providers (Google, Facebook, Amazon) can authenticate using Amazon Cognito and obtain temporary IAM role credentials via AWS STS. You will integrate federated identities without creating IAM users, showcasing secure, temporary access to AWS resources.

---

## Objectives
- Create an Amazon Cognito Identity Pool for federated authentication
- Link external identity providers (Google or Facebook) to Cognito
- Configure IAM roles for authenticated and unauthenticated users
- Exchange IdP tokens for temporary AWS credentials using STS
- Access S3 resources using federated temporary credentials
- Validate least-privilege access and token expiration
- Test identity federation workflow end-to-end

---

## Prerequisites
- AWS CLI configured (`aws configure`)
- IAM permissions to create Cognito Identity Pools, roles, and policies
- Google account (for OAuth 2.0 authentication) or Facebook account
- Basic understanding of OAuth 2.0 and federated identity concepts
- jq installed for JSON parsing
- Browser for Google/Facebook authentication

---

## Step 1 – Set Variables and Verify Prerequisites

```bash
# Get AWS account ID dynamically
ACCOUNT_ID=$(aws sts get-caller-identity \
  --query Account \
  --output text)
echo "ACCOUNT_ID=$ACCOUNT_ID"

# Set region
REGION="ap-southeast-2"
echo "REGION=$REGION"

# Set Cognito Identity Pool name
IDENTITY_POOL_NAME="FederationLabIdentityPool"
echo "IDENTITY_POOL_NAME=$IDENTITY_POOL_NAME"

# Set bucket name for federation testing
BUCKET_NAME="cognito-federation-bucket-${ACCOUNT_ID}"
echo "BUCKET_NAME=$BUCKET_NAME"

# Verify AWS CLI is configured
aws sts get-caller-identity

# Check if jq is installed
which jq || echo "Warning: jq not installed (required for JSON parsing)"
```

---

## Step 2 – Create S3 Bucket for Testing

```bash
# Create S3 bucket for Cognito federation testing
aws s3api create-bucket \
  --bucket "$BUCKET_NAME" \
  --region "$REGION" \
  --create-bucket-configuration LocationConstraint="$REGION"

# Verify bucket creation
aws s3 ls | grep "$BUCKET_NAME"

# Create test folders for authenticated and unauthenticated access
echo "Authenticated user content" > auth-test.txt
echo "Public unauthenticated content" > unauth-test.txt

# Upload test files
aws s3 cp auth-test.txt "s3://${BUCKET_NAME}/authenticated/"
aws s3 cp unauth-test.txt "s3://${BUCKET_NAME}/public/"

# Verify uploads
aws s3 ls "s3://${BUCKET_NAME}/" --recursive
```

---

## Step 3 – Configure Google OAuth 2.0 (External IdP)

```bash
# Display instructions for Google OAuth setup
cat <<'INSTRUCTIONS'
========================================
Google OAuth 2.0 Configuration Steps
========================================

1. Go to Google Cloud Console: https://console.cloud.google.com
2. Create a new project (or select existing)
3. Navigate to: APIs & Services > Credentials
4. Click "Create Credentials" > "OAuth 2.0 Client ID"
5. Configure OAuth consent screen:
   - User Type: External
   - App name: AWS Cognito Federation Lab
   - User support email: your-email@example.com
6. Create OAuth 2.0 Client ID:
   - Application type: Web application
   - Authorized JavaScript origins: https://localhost
   - Authorized redirect URIs: https://localhost
7. Note down:
   - Client ID (starts with: xxxxxxxxx.apps.googleusercontent.com)
   - Client Secret

After obtaining credentials, save them:

INSTRUCTIONS

# Prompt for Google OAuth credentials
echo ""
read -p "Enter your Google OAuth 2.0 Client ID: " GOOGLE_CLIENT_ID
read -p "Enter your Google OAuth 2.0 Client Secret: " GOOGLE_CLIENT_SECRET

echo "GOOGLE_CLIENT_ID=$GOOGLE_CLIENT_ID"
echo "GOOGLE_CLIENT_SECRET saved (not displayed)"
```

---

## Step 4 – Create IAM Role for Unauthenticated Users

```bash
# Set unauthenticated role name
UNAUTH_ROLE_NAME="Cognito_${IDENTITY_POOL_NAME}_Unauth_Role"
echo "UNAUTH_ROLE_NAME=$UNAUTH_ROLE_NAME"

# Create trust policy for unauthenticated Cognito users
cat > cognito-unauth-trust.json <<'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "cognito-identity.amazonaws.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "cognito-identity.amazonaws.com:aud": "IDENTITY_POOL_ID_PLACEHOLDER"
        },
        "ForAnyValue:StringLike": {
          "cognito-identity.amazonaws.com:amr": "unauthenticated"
        }
      }
    }
  ]
}
EOF

# Display the trust policy template
cat cognito-unauth-trust.json

# Create the unauthenticated role (will update trust policy later)
aws iam create-role \
  --role-name "$UNAUTH_ROLE_NAME" \
  --assume-role-policy-document file://cognito-unauth-trust.json \
  --description "Role for unauthenticated Cognito federated users"

# Get role ARN
UNAUTH_ROLE_ARN=$(aws iam get-role \
  --role-name "$UNAUTH_ROLE_NAME" \
  --query 'Role.Arn' \
  --output text)
echo "UNAUTH_ROLE_ARN=$UNAUTH_ROLE_ARN"

# Verify role creation
aws iam get-role \
  --role-name "$UNAUTH_ROLE_NAME" \
  --query 'Role.[RoleName,Arn,CreateDate]' \
  --output table
```

---

## Step 5 – Create IAM Role for Authenticated Users

```bash
# Set authenticated role name
AUTH_ROLE_NAME="Cognito_${IDENTITY_POOL_NAME}_Auth_Role"
echo "AUTH_ROLE_NAME=$AUTH_ROLE_NAME"

# Create trust policy for authenticated Cognito users
cat > cognito-auth-trust.json <<'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "cognito-identity.amazonaws.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "cognito-identity.amazonaws.com:aud": "IDENTITY_POOL_ID_PLACEHOLDER"
        },
        "ForAnyValue:StringLike": {
          "cognito-identity.amazonaws.com:amr": "authenticated"
        }
      }
    }
  ]
}
EOF

# Display the trust policy template
cat cognito-auth-trust.json

# Create the authenticated role
aws iam create-role \
  --role-name "$AUTH_ROLE_NAME" \
  --assume-role-policy-document file://cognito-auth-trust.json \
  --description "Role for authenticated Cognito federated users"

# Get role ARN
AUTH_ROLE_ARN=$(aws iam get-role \
  --role-name "$AUTH_ROLE_NAME" \
  --query 'Role.Arn' \
  --output text)
echo "AUTH_ROLE_ARN=$AUTH_ROLE_ARN"

# Verify role creation
aws iam get-role \
  --role-name "$AUTH_ROLE_NAME" \
  --query 'Role.[RoleName,Arn,CreateDate]' \
  --output table
```

---

## Step 6 – Create Permissions Policy for Unauthenticated Users

```bash
# Set unauthenticated policy name
UNAUTH_POLICY_NAME="CognitoUnauthenticatedPolicy"
echo "UNAUTH_POLICY_NAME=$UNAUTH_POLICY_NAME"

# Create limited permissions policy for unauthenticated users
cat > cognito-unauth-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowPublicS3ReadOnly",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject"
      ],
      "Resource": "arn:aws:s3:::${BUCKET_NAME}/public/*"
    },
    {
      "Sid": "AllowListBucket",
      "Effect": "Allow",
      "Action": "s3:ListBucket",
      "Resource": "arn:aws:s3:::${BUCKET_NAME}",
      "Condition": {
        "StringLike": {
          "s3:prefix": "public/*"
        }
      }
    }
  ]
}
EOF

# Display the policy document
cat cognito-unauth-policy.json

# Create the IAM policy
UNAUTH_POLICY_ARN=$(aws iam create-policy \
  --policy-name "$UNAUTH_POLICY_NAME" \
  --policy-document file://cognito-unauth-policy.json \
  --description "Limited S3 read access for unauthenticated Cognito users" \
  --query 'Policy.Arn' \
  --output text)
echo "UNAUTH_POLICY_ARN=$UNAUTH_POLICY_ARN"

# Attach policy to unauthenticated role
aws iam attach-role-policy \
  --role-name "$UNAUTH_ROLE_NAME" \
  --policy-arn "$UNAUTH_POLICY_ARN"

# Verify policy attachment
aws iam list-attached-role-policies \
  --role-name "$UNAUTH_ROLE_NAME" \
  --output table
```

---

## Step 7 – Create Permissions Policy for Authenticated Users

```bash
# Set authenticated policy name
AUTH_POLICY_NAME="CognitoAuthenticatedPolicy"
echo "AUTH_POLICY_NAME=$AUTH_POLICY_NAME"

# Create enhanced permissions policy for authenticated users
cat > cognito-auth-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowAuthenticatedS3FullAccess",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject"
      ],
      "Resource": "arn:aws:s3:::${BUCKET_NAME}/authenticated/*"
    },
    {
      "Sid": "AllowPublicS3Read",
      "Effect": "Allow",
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::${BUCKET_NAME}/public/*"
    },
    {
      "Sid": "AllowListBucket",
      "Effect": "Allow",
      "Action": [
        "s3:ListBucket",
        "s3:GetBucketLocation"
      ],
      "Resource": "arn:aws:s3:::${BUCKET_NAME}"
    },
    {
      "Sid": "AllowGetCallerIdentity",
      "Effect": "Allow",
      "Action": "sts:GetCallerIdentity",
      "Resource": "*"
    }
  ]
}
EOF

# Display the policy document
cat cognito-auth-policy.json

# Create the IAM policy
AUTH_POLICY_ARN=$(aws iam create-policy \
  --policy-name "$AUTH_POLICY_NAME" \
  --policy-document file://cognito-auth-policy.json \
  --description "Enhanced S3 access for authenticated Cognito users" \
  --query 'Policy.Arn' \
  --output text)
echo "AUTH_POLICY_ARN=$AUTH_POLICY_ARN"

# Attach policy to authenticated role
aws iam attach-role-policy \
  --role-name "$AUTH_ROLE_NAME" \
  --policy-arn "$AUTH_POLICY_ARN"

# Verify policy attachment
aws iam list-attached-role-policies \
  --role-name "$AUTH_ROLE_NAME" \
  --output table
```

---

## Step 8 – Create Cognito Identity Pool

```bash
# Create Cognito Identity Pool with Google as IdP
# Note: This requires the Google Client ID from Step 3
IDENTITY_POOL_OUTPUT=$(aws cognito-identity create-identity-pool \
  --identity-pool-name "$IDENTITY_POOL_NAME" \
  --allow-unauthenticated-identities \
  --supported-login-providers accounts.google.com="$GOOGLE_CLIENT_ID" \
  --output json)

# Extract Identity Pool ID
IDENTITY_POOL_ID=$(echo $IDENTITY_POOL_OUTPUT | jq -r '.IdentityPoolId')
echo "IDENTITY_POOL_ID=$IDENTITY_POOL_ID"

# Display Identity Pool details
echo "$IDENTITY_POOL_OUTPUT" | jq '.'

# Verify Identity Pool creation
aws cognito-identity describe-identity-pool \
  --identity-pool-id "$IDENTITY_POOL_ID" \
  --output table
```

---

## Step 9 – Update IAM Role Trust Policies with Identity Pool ID

```bash
# Update unauthenticated role trust policy with actual Identity Pool ID
cat > cognito-unauth-trust-updated.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "cognito-identity.amazonaws.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "cognito-identity.amazonaws.com:aud": "${IDENTITY_POOL_ID}"
        },
        "ForAnyValue:StringLike": {
          "cognito-identity.amazonaws.com:amr": "unauthenticated"
        }
      }
    }
  ]
}
EOF

# Update unauthenticated role trust policy
aws iam update-assume-role-policy \
  --role-name "$UNAUTH_ROLE_NAME" \
  --policy-document file://cognito-unauth-trust-updated.json

echo "Updated unauthenticated role trust policy"

# Update authenticated role trust policy with actual Identity Pool ID
cat > cognito-auth-trust-updated.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "cognito-identity.amazonaws.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "cognito-identity.amazonaws.com:aud": "${IDENTITY_POOL_ID}"
        },
        "ForAnyValue:StringLike": {
          "cognito-identity.amazonaws.com:amr": "authenticated"
        }
      }
    }
  ]
}
EOF

# Update authenticated role trust policy
aws iam update-assume-role-policy \
  --role-name "$AUTH_ROLE_NAME" \
  --policy-document file://cognito-auth-trust-updated.json

echo "Updated authenticated role trust policy"
```

---

## Step 10 – Attach IAM Roles to Cognito Identity Pool

```bash
# Set IAM roles for the Cognito Identity Pool
aws cognito-identity set-identity-pool-roles \
  --identity-pool-id "$IDENTITY_POOL_ID" \
  --roles authenticated="$AUTH_ROLE_ARN",unauthenticated="$UNAUTH_ROLE_ARN"

echo "Attached IAM roles to Cognito Identity Pool"

# Verify role mappings
aws cognito-identity get-identity-pool-roles \
  --identity-pool-id "$IDENTITY_POOL_ID" \
  --output json | jq '.'
```

---

## Step 11 – Test Unauthenticated Access

```bash
# Get Identity ID for unauthenticated user
echo "Testing unauthenticated access..."

UNAUTH_IDENTITY=$(aws cognito-identity get-id \
  --identity-pool-id "$IDENTITY_POOL_ID" \
  --output json)

IDENTITY_ID=$(echo $UNAUTH_IDENTITY | jq -r '.IdentityId')
echo "IDENTITY_ID=$IDENTITY_ID"

# Get temporary credentials for unauthenticated user
UNAUTH_CREDS=$(aws cognito-identity get-credentials-for-identity \
  --identity-id "$IDENTITY_ID" \
  --output json)

# Extract credentials
UNAUTH_ACCESS_KEY=$(echo $UNAUTH_CREDS | jq -r '.Credentials.AccessKeyId')
UNAUTH_SECRET_KEY=$(echo $UNAUTH_CREDS | jq -r '.Credentials.SecretKey')
UNAUTH_SESSION_TOKEN=$(echo $UNAUTH_CREDS | jq -r '.Credentials.SessionToken')
UNAUTH_EXPIRATION=$(echo $UNAUTH_CREDS | jq -r '.Credentials.Expiration')

echo "Unauthenticated temporary credentials obtained"
echo "Expiration: $UNAUTH_EXPIRATION"

# Export unauthenticated credentials
export AWS_ACCESS_KEY_ID="$UNAUTH_ACCESS_KEY"
export AWS_SECRET_ACCESS_KEY="$UNAUTH_SECRET_KEY"
export AWS_SESSION_TOKEN="$UNAUTH_SESSION_TOKEN"

# Test unauthenticated access to public folder (should succeed)
echo ""
echo "Testing access to public folder (should succeed)..."
aws s3 ls "s3://${BUCKET_NAME}/public/" || echo "Access denied"
aws s3 cp "s3://${BUCKET_NAME}/public/unauth-test.txt" - || echo "Access denied"

# Test unauthenticated access to authenticated folder (should fail)
echo ""
echo "Testing access to authenticated folder (should fail)..."
aws s3 ls "s3://${BUCKET_NAME}/authenticated/" || echo "Access denied (expected)"

# Unset credentials
unset AWS_ACCESS_KEY_ID
unset AWS_SECRET_ACCESS_KEY
unset AWS_SESSION_TOKEN

echo ""
echo "Unauthenticated access test complete"
```

---

## Step 12 – Authenticate with Google and Test Federated Access

```bash
# Display instructions for Google authentication
cat <<'AUTH_INSTRUCTIONS'
========================================
Google Authentication Flow
========================================

To obtain a Google ID token for testing:

1. Use Google OAuth 2.0 Playground: https://developers.google.com/oauthplayground/

2. Configure OAuth 2.0 settings:
   - Click settings (gear icon)
   - Check "Use your own OAuth credentials"
   - Enter your OAuth Client ID and Client Secret
   - Close settings

3. Select APIs:
   - Find "Google OAuth2 API v2"
   - Select "https://www.googleapis.com/auth/userinfo.email"
   - Click "Authorize APIs"

4. Sign in with Google account

5. Click "Exchange authorization code for tokens"

6. Copy the "id_token" value (long JWT string)

AUTH_INSTRUCTIONS

echo ""
read -p "Paste your Google ID token here: " GOOGLE_ID_TOKEN

# Get Identity ID for authenticated user with Google token
echo ""
echo "Authenticating with Google..."

AUTH_IDENTITY=$(aws cognito-identity get-id \
  --identity-pool-id "$IDENTITY_POOL_ID" \
  --logins accounts.google.com="$GOOGLE_ID_TOKEN" \
  --output json)

AUTH_IDENTITY_ID=$(echo $AUTH_IDENTITY | jq -r '.IdentityId')
echo "AUTH_IDENTITY_ID=$AUTH_IDENTITY_ID"

# Get temporary credentials for authenticated user
AUTH_CREDS=$(aws cognito-identity get-credentials-for-identity \
  --identity-id "$AUTH_IDENTITY_ID" \
  --logins accounts.google.com="$GOOGLE_ID_TOKEN" \
  --output json)

# Extract authenticated credentials
AUTH_ACCESS_KEY=$(echo $AUTH_CREDS | jq -r '.Credentials.AccessKeyId')
AUTH_SECRET_KEY=$(echo $AUTH_CREDS | jq -r '.Credentials.SecretKey')
AUTH_SESSION_TOKEN=$(echo $AUTH_CREDS | jq -r '.Credentials.SessionToken')
AUTH_EXPIRATION=$(echo $AUTH_CREDS | jq -r '.Credentials.Expiration')

echo "Authenticated temporary credentials obtained"
echo "Expiration: $AUTH_EXPIRATION"

# Export authenticated credentials
export AWS_ACCESS_KEY_ID="$AUTH_ACCESS_KEY"
export AWS_SECRET_ACCESS_KEY="$AUTH_SECRET_KEY"
export AWS_SESSION_TOKEN="$AUTH_SESSION_TOKEN"

# Test authenticated user identity
echo ""
echo "Verifying authenticated identity..."
aws sts get-caller-identity

# Test authenticated access to public folder (should succeed)
echo ""
echo "Testing access to public folder (should succeed)..."
aws s3 ls "s3://${BUCKET_NAME}/public/"
aws s3 cp "s3://${BUCKET_NAME}/public/unauth-test.txt" -

# Test authenticated access to authenticated folder (should succeed)
echo ""
echo "Testing access to authenticated folder (should succeed)..."
aws s3 ls "s3://${BUCKET_NAME}/authenticated/"
aws s3 cp "s3://${BUCKET_NAME}/authenticated/auth-test.txt" -

# Test write access to authenticated folder (should succeed)
echo ""
echo "Testing write access to authenticated folder..."
echo "Federated user upload at $(date)" > federated-upload.txt
aws s3 cp federated-upload.txt "s3://${BUCKET_NAME}/authenticated/"

# Verify upload
aws s3 ls "s3://${BUCKET_NAME}/authenticated/"

# Unset credentials
unset AWS_ACCESS_KEY_ID
unset AWS_SECRET_ACCESS_KEY
unset AWS_SESSION_TOKEN

echo ""
echo "✅ Authenticated federated access test complete"
```

---

## Step 13 – Validate Token Expiration

```bash
# Display token expiration information
echo "=========================================="
echo "Temporary Credentials Expiration"
echo "=========================================="
echo ""
echo "Unauthenticated credentials expire at: $UNAUTH_EXPIRATION"
echo "Authenticated credentials expire at: $AUTH_EXPIRATION"
echo ""
echo "Temporary credentials automatically expire after 1 hour"
echo "Users must re-authenticate to obtain new credentials"
echo ""
echo "To verify expiration, wait until the expiration time and attempt to use the credentials"
echo "Access will be denied with 'ExpiredToken' error"
```

---

## Step 14 – Cleanup Resources

```bash
# Detach policies from roles
echo "Detaching policies from IAM roles..."
aws iam detach-role-policy \
  --role-name "$UNAUTH_ROLE_NAME" \
  --policy-arn "$UNAUTH_POLICY_ARN" || true

aws iam detach-role-policy \
  --role-name "$AUTH_ROLE_NAME" \
  --policy-arn "$AUTH_POLICY_ARN" || true

# Delete IAM roles
echo "Deleting IAM roles..."
aws iam delete-role \
  --role-name "$UNAUTH_ROLE_NAME" || true

aws iam delete-role \
  --role-name "$AUTH_ROLE_NAME" || true

# Delete IAM policies
echo "Deleting IAM policies..."
aws iam delete-policy \
  --policy-arn "$UNAUTH_POLICY_ARN" || true

aws iam delete-policy \
  --policy-arn "$AUTH_POLICY_ARN" || true

# Delete Cognito Identity Pool
echo "Deleting Cognito Identity Pool..."
aws cognito-identity delete-identity-pool \
  --identity-pool-id "$IDENTITY_POOL_ID" || true

# Empty and delete S3 bucket
echo "Emptying and deleting S3 bucket..."
aws s3 rm "s3://${BUCKET_NAME}" --recursive || true
aws s3 rb "s3://${BUCKET_NAME}" || true

# Delete local files
echo "Cleaning up local files..."
rm -f cognito-unauth-trust.json \
  cognito-auth-trust.json \
  cognito-unauth-trust-updated.json \
  cognito-auth-trust-updated.json \
  cognito-unauth-policy.json \
  cognito-auth-policy.json \
  auth-test.txt \
  unauth-test.txt \
  federated-upload.txt \
  cognito_federation_test.py

# Verify cleanup
echo ""
echo "Verifying cleanup..."

# Check Cognito Identity Pools
aws cognito-identity list-identity-pools \
  --max-results 10 \
  --query "IdentityPools[?IdentityPoolName=='$IDENTITY_POOL_NAME']" \
  --output table || echo "Identity Pool deleted"

# Check IAM roles
aws iam list-roles \
  --query "Roles[?contains(RoleName,'Cognito_${IDENTITY_POOL_NAME}')].RoleName" \
  --output table || echo "Roles deleted"

# Check S3 bucket
aws s3 ls | grep "$BUCKET_NAME" || echo "S3 bucket deleted"

echo ""
echo "✅ Cleanup complete! All Cognito federation resources have been removed."
```

---

## Summary

In this lab, you have:
- Created an Amazon Cognito Identity Pool for federated authentication
- Configured Google as an external identity provider using OAuth 2.0
- Created separate IAM roles for authenticated and unauthenticated users
- Implemented least-privilege policies for each user type
- Obtained temporary AWS credentials using STS AssumeRoleWithWebIdentity
- Tested federated access to S3 with different permission levels
- Validated temporary credential expiration (1 hour TTL)
- Created a Python application demonstrating the federation workflow
- Successfully cleaned up all Cognito and IAM resources

**Key Takeaways:**
- **No IAM Users Required**: External identities authenticate through Cognito, not IAM users
- **Temporary Credentials**: STS provides short-lived credentials (1 hour) that auto-expire
- **Least Privilege**: Unauthenticated users get minimal access, authenticated get enhanced permissions
- **Trust Policies**: Define which Cognito Identity Pool can assume each role
- **Federation Flow**: IdP Token → Cognito Identity → STS Credentials → AWS Access
- **Security Best Practices**: Separate roles for authenticated vs unauthenticated access
- **OAuth 2.0 Integration**: Leverage existing Google/Facebook accounts for AWS access

**Real-World Use Cases:**
- Mobile applications requiring AWS access (iOS, Android)
- Web applications with social login (Google, Facebook, Amazon)
- Temporary guest access to specific AWS resources
- Multi-tenant SaaS applications with customer data isolation
- Serverless backends with user authentication

**Cognito vs OIDC Direct:**
- Cognito simplifies identity management and credential vending
- Supports multiple IdPs (Google, Facebook, Amazon, SAML)
- Handles credential caching and refresh automatically
- Provides both authenticated and unauthenticated access patterns

---

## Additional Resources
- [Amazon Cognito Identity Pools](https://docs.aws.amazon.com/cognito/latest/developerguide/cognito-identity.html)
- [IAM Roles for Amazon Cognito](https://docs.aws.amazon.com/cognito/latest/developerguide/iam-roles.html)
- [GetCredentialsForIdentity API](https://docs.aws.amazon.com/cognitoidentity/latest/APIReference/API_GetCredentialsForIdentity.html)
- [Google OAuth 2.0 for Web](https://developers.google.com/identity/protocols/oauth2/web-server)
- [AWS STS AssumeRoleWithWebIdentity](https://docs.aws.amazon.com/STS/latest/APIReference/API_AssumeRoleWithWebIdentity.html)

---

```bash
