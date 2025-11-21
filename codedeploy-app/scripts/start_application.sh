#!/bin/bash
cd /var/www/flask-app

gunicorn -b 127.0.0.1:5000 app:app \
  --daemon \
  --workers 2 \
  --access-logfile /var/log/gunicorn-access.log \
  --error-logfile /var/log/gunicorn-error.log

# Test nginx configuration and restart
nginx -t && systemctl restart nginx
