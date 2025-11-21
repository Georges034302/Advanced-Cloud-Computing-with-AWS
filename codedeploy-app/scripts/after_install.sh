#!/bin/bash
cd /var/www/flask-app
pip3 install -r requirements.txt

# Disable default nginx server block
mv /etc/nginx/nginx.conf /etc/nginx/nginx.conf.orig
grep -v -A 100 'server {' /etc/nginx/nginx.conf.orig | grep -v -B 100 '^    }' | grep -v '^    }' > /etc/nginx/nginx.conf || cp /etc/nginx/nginx.conf.orig /etc/nginx/nginx.conf

# Create Flask proxy configuration
cat > /etc/nginx/conf.d/flask.conf <<'NGINX'
server {
    listen 80 default_server;
    server_name _;
    
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
    
    location /health {
        proxy_pass http://127.0.0.1:5000/health;
    }
}
NGINX
