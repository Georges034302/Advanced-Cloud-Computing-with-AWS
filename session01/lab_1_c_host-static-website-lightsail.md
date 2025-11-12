# Lab 1.C: Host a Static Website on AWS Lightsail

## Overview
This lab introduces **AWS Lightsail**, a simplified platform for deploying and managing virtual private servers (VPS). You will create a Lightsail instance, install a web server, host a static HTML site, and verify its availability from the public internet.

---

## Objectives
- Create a new AWS Lightsail instance
- Configure networking and access settings
- Deploy a static HTML website using Apache
- Test public access to the site
- Clean up resources to prevent ongoing charges

---

## Architecture Diagram (Conceptual)
```
Internet → Lightsail Instance (Ubuntu)
          ├── Apache Web Server
          └── /var/www/html/index.html (Static Website)
```

---

## Prerequisites
- AWS CLI configured (`aws configure`)
- IAM permissions for Lightsail resources
- Basic familiarity with Linux commands

---

## Step 1 – Create SSH Key Pair

```bash
# Create a new SSH key pair for Lightsail
aws lightsail create-key-pair \
  --key-pair-name lightsail-key \
  --query 'privateKeyBase64' \
  --output text > lightsail-key.pem

# Set proper permissions on the key file
chmod 600 lightsail-key.pem

# Verify the key was created
aws lightsail get-key-pair \
  --key-pair-name lightsail-key
```

---

## Step 2 – Create a Lightsail Instance

```bash
# Create a Lightsail instance with Ubuntu 22.04 LTS in Sydney region
# Using the smallest available bundle ($5/month tier)
INSTANCE_NAME="lightsail-web"
echo "INSTANCE_NAME=$INSTANCE_NAME"

# Create the instance
aws lightsail create-instances \
  --instance-names $INSTANCE_NAME \
  --availability-zone ap-southeast-2a \
  --blueprint-id ubuntu_22_04 \
  --bundle-id nano_3_2 \
  --key-pair-name lightsail-key

# Wait for the instance to be running (this may take 2-3 minutes)
echo "Waiting for instance to be running..."
# Check instance state
aws lightsail get-instance-state \
  --instance-name $INSTANCE_NAME

# Get the public IP address of the instance
PUBLIC_IP=$(aws lightsail get-instance \
  --instance-name $INSTANCE_NAME \
  --query 'instance.publicIpAddress' \
  --output text)
echo "PUBLIC_IP=$PUBLIC_IP"
```

---

## Step 3 – Connect to Your Instance

```bash
# Connect to the instance using SSH with the key pair created earlier
ssh -i lightsail-key.pem ubuntu@$PUBLIC_IP
```

Once connected, confirm network connectivity:
```bash
# Test internet connectivity
ping -c 2 google.com
```

---

## Step 4 – Install and Configure Apache Web Server

```bash
# Update package lists to get latest versions
sudo apt update -y

# Install Apache web server
sudo apt install apache2 -y

# Start the Apache service
sudo systemctl start apache2

# Enable Apache to start automatically on boot
sudo systemctl enable apache2

# Verify Apache is running and active
sudo systemctl status apache2

# Check that Apache is listening on port 80
ssh -i lightsail-key.pem ubuntu@$PUBLIC_IP "sudo ss -tuln | grep :80"
```

Test the default Apache page in your browser:
```bash
# Open the custom website in your browser
"$BROWSER" "http://$PUBLIC_IP"
```

✅ You should see the default Apache welcome page.

---

## Step 5 – Deploy Your Static Website

Replace the default web page with your custom site:
```bash
# Navigate to the Apache web root directory
cd /var/www/html

# Remove the default Apache index file
sudo rm index.html
```
# Create a custom HTML file using a heredoc for better readability
```bash
sudo tee index.html > /dev/null <<'EOF'
<!DOCTYPE html>
<html>
<head>
    <title>My Lightsail Site</title>
</head>
<body style="font-family: Arial; text-align:center;">
    <h1>Welcome to My AWS Lightsail Website!</h1>
    <p>This static site is hosted on a Lightsail instance.</p>
</body>
</html>
EOF
```
# Verify the file was created successfully
```bash
cat index.html
```

---

## Step 6 – Verify Firewall Configuration

By default, Lightsail instances have ports **22 (SSH)**, **80 (HTTP)**, and **443 (HTTPS)** open. You can verify this:

```bash
# Exit the SSH session to run AWS CLI commands from your local machine
exit

# List the firewall rules (ports) for the Lightsail instance
aws lightsail get-instance-port-states \
  --instance-name $INSTANCE_NAME

# The output should show ports 22, 80, and 443 are open by default
```

⚠ **Note:** Unlike EC2 Security Groups, Lightsail firewall rules are pre-configured and typically don't require changes for basic web hosting.

---

## Step 7 – Validate the Deployment

Test your custom static website:
```bash
# Test the site using curl to verify HTML content
curl http://$PUBLIC_IP

# Open the custom website in your browser
"$BROWSER" "http://$PUBLIC_IP"
```

✅ You should receive the HTML output of your static page and see your custom website in the browser.

---

## Step 8 – Cleanup

To avoid ongoing costs, delete all resources:

```bash
# Delete the Lightsail instance
aws lightsail delete-instance \
  --instance-name $INSTANCE_NAME

# Wait for the instance to be deleted
echo "Waiting for instance deletion..."
sleep 30

# Delete the SSH key pair
aws lightsail delete-key-pair \
  --key-pair-name lightsail-key

# Remove the local key file
rm -f lightsail-key.pem

# Verify the instance has been deleted
aws lightsail get-instances \
  --query 'instances[?name==`lightsail-web`]'
```

---

## Summary

In this lab, you have:
- Created a Lightsail instance using AWS CLI
- Installed and configured an Apache web server
- Deployed a static HTML website
- Verified firewall configuration and public access
- Cleaned up all resources using CLI commands

This exercise demonstrates how Lightsail provides a fast, low-cost entry point into AWS compute for small web workloads, while maintaining CLI-based automation consistent with enterprise practices.
