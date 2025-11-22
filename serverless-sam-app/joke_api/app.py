import json
import random

jokes = [
    "Why do programmers prefer dark mode? Because light attracts bugs!",
    "Why do Java developers wear glasses? Because they don't C#.",
    "How many programmers does it take to change a light bulb? None, that's a hardware problem.",
    "Why did the developer go broke? Because he used up all his cache.",
    "What's a programmer's favorite hangout place? The Foo Bar.",
    "Why do serverless developers sleep well? Because they have no servers to worry about!",
]

def lambda_handler(event, context):
    """
    Lambda function handler for Joke API
    """
    # Get HTTP method and path
    http_method = event.get('httpMethod', 'GET')
    path = event.get('path', '/')
    
    # Route requests
    if path == '/' and http_method == 'GET':
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'service': 'joke-api',
                'version': '1.0.0',
                'endpoints': {
                    '/': 'API info',
                    '/joke': 'Get random joke',
                    '/health': 'Health check'
                }
            })
        }
    
    elif path == '/joke' and http_method == 'GET':
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'joke': random.choice(jokes)
            })
        }
    
    elif path == '/health' and http_method == 'GET':
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'status': 'healthy'
            })
        }
    
    else:
        return {
            'statusCode': 404,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'error': 'Not Found'
            })
        }
