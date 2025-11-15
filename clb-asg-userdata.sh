#!/bin/bash
# Update system packages
dnf update -y

# Install Apache web server
dnf install -y httpd

# Get instance metadata
INSTANCE_ID=$(ec2-metadata --instance-id | cut -d " " -f 2)
AVAILABILITY_ZONE=$(ec2-metadata --availability-zone | cut -d " " -f 2)
LOCAL_IP=$(ec2-metadata --local-ipv4 | cut -d " " -f 2)

# Create web page with instance information
cat > /var/www/html/index.html <<HTML
<!DOCTYPE html>
<html>
<head>
    <title>CLB + ASG Demo</title>
    <style>
        body { font-family: Arial; text-align: center; padding: 50px; background: #f0f0f0; }
        .box { background: white; padding: 30px; border-radius: 5px; display: inline-block; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
        h1 { color: #FF9900; }
        .info { background: #232F3E; color: white; padding: 15px; margin: 10px 0; border-radius: 3px; }
    </style>
</head>
<body>
    <div class="box">
        <h1>🔄 CLB + Auto Scaling</h1>
        <div class="info">
            <p><strong>Instance ID:</strong> ${INSTANCE_ID}</p>
            <p><strong>AZ:</strong> ${AVAILABILITY_ZONE}</p>
            <p><strong>Private IP:</strong> ${LOCAL_IP}</p>
        </div>
        <p>Refresh to see load distribution</p>
    </div>
</body>
</html>
HTML

# Create health check endpoint
echo "OK" > /var/www/html/health.html

# Start and enable Apache
systemctl start httpd
systemctl enable httpd

# Log completion
echo "Web server setup completed" > /var/log/userdata-complete.log
