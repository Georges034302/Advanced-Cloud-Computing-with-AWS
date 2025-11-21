from flask import Flask, render_template_string

app = Flask(__name__)

VERSION = "2.0"
COLOR = "#2ecc71"  # Green

HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>CodeDeploy Blue/Green</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            text-align: center;
            padding: 50px;
            background-color: {{ color }};
            color: white;
        }
        .container {
            background: rgba(255,255,255,0.1);
            padding: 40px;
            border-radius: 10px;
            max-width: 600px;
            margin: 0 auto;
        }
        h1 { font-size: 3em; }
        .version { font-size: 2em; margin: 20px 0; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🟢 Green Environment</h1>
        <div class="version">Version {{ version }}</div>
        <p>Deployed via AWS CodeDeploy</p>
        <p>Blue/Green Deployment Strategy</p>
        <p><strong>✨ New Features Added!</strong></p>
    </div>
</body>
</html>
"""

@app.route('/')
def home():
    return render_template_string(HTML, version=VERSION, color=COLOR)

@app.route('/health')
def health():
    return {'status': 'healthy', 'version': VERSION}, 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
