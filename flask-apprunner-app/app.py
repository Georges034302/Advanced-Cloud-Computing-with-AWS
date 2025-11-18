from flask import Flask, jsonify
import random
import os

app = Flask(__name__)

jokes = [
    "Why do programmers prefer dark mode? Because light attracts bugs!",
    "Why did the developer go broke? Because he used up all his cache!",
    "How do you comfort a JavaScript bug? You console it!",
    "Why do Java developers wear glasses? Because they don't C#!",
    "What's a programmer's favorite hangout place? Foo Bar!"
]

@app.route('/')
def home():
    return jsonify({
        "message": "Flask Joke API on App Runner",
        "endpoints": {
            "/": "API info",
            "/joke": "Get random joke",
            "/health": "Health check"
        }
    })

@app.route('/joke')
def get_joke():
    return jsonify({"joke": random.choice(jokes)})

@app.route('/health')
def health():
    return jsonify({"status": "healthy"})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port, debug=False)
