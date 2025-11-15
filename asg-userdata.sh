#!/bin/bash
dnf update -y
dnf install -y httpd

# Get instance metadata
INSTANCE_ID=$(ec2-metadata --instance-id | cut -d " " -f 2)
AVAILABILITY_ZONE=$(ec2-metadata --availability-zone | cut -d " " -f 2)

# Create web page showing instance information
cat > /var/www/html/index.html <<HTML
<!DOCTYPE html>
<html>
<head>
    <title>Auto Scaling Demo</title>
    <style>
        body { font-family: Arial; text-align: center; padding: 50px; background: #f0f0f0; }
        .box { background: white; padding: 20px; border-radius: 5px; display: inline-block; }
        h1 { color: #FF9900; }
    </style>
</head>
<body>
    <div class="box">
        <h1>Auto Scaling Instance</h1>
        <p><strong>Instance ID:</strong> ${INSTANCE_ID}</p>
        <p><strong>Availability Zone:</strong> ${AVAILABILITY_ZONE}</p>
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
