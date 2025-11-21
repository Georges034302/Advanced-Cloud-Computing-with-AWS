from flask import Flask, jsonify
import os
import socket

app = Flask(__name__)
VERSION = os.getenv('APP_VERSION', '2.0')

@app.route('/')
def home():
    return jsonify({
        'message': 'Hello from App Runner!',
        'version': VERSION,
        'deployed_by': 'GitHub Actions',
        'hostname': socket.gethostname(),
        'platform': 'AWS App Runner'
    })

@app.route('/health')
def health():
    return jsonify({'status': 'healthy'}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
