#!/bin/bash
yum update -y
yum install -y python3-pip
pip3 install flask
cat > /home/ec2-user/app.py <<'APP'
from flask import Flask, jsonify; import socket
app = Flask(__name__)
@app.route('/joke')
def joke(): return jsonify({'joke':'Why do developers hate nature? It has too many bugs!','host':socket.gethostname()})
app.run(host='0.0.0.0', port=5000)
APP
nohup python3 /home/ec2-user/app.py &
