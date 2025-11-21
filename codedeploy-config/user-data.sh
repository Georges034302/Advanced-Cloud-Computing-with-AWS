#!/bin/bash
# Update system packages
yum update -y

# Install CodeDeploy agent dependencies
yum install -y ruby wget
cd /home/ec2-user

# Download and install CodeDeploy agent
wget https://aws-codedeploy-ap-southeast-2.s3.ap-southeast-2.amazonaws.com/latest/install
chmod +x ./install
./install auto

# Install Python and nginx for application
yum install -y python3 python3-pip
amazon-linux-extras install -y nginx1
systemctl enable nginx
systemctl start nginx
