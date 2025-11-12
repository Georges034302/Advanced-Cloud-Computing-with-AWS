#!/bin/bash
yum update -y
yum install -y python3-pip
pip3 install flask
cat > /home/ec2-user/app.py <<'APP'
from flask import Flask, jsonify; import socket
app = Flask(__name__)
@app.route('/jokes')
def jokes():
    data=['Why did the cloud break up with the server? It needed space.',
          'I told my computer I needed a break, and it said “No problem, I’ll go to sleep.”',
          'Why do Python programmers wear glasses? Because they can’t C#.']
    return jsonify({'jokes':data,'host':socket.gethostname()})
app.run(host='0.0.0.0', port=5000)
APP
nohup python3 /home/ec2-user/app.py &
