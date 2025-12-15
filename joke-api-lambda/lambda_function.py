import json
import random

# In-memory joke storage (for simplicity)
JOKES = [
    {"id": 1, "joke": "Why do programmers prefer dark mode? Because light attracts bugs!"},
    {"id": 2, "joke": "Why do Java developers wear glasses? Because they don't C#!"},
    {"id": 3, "joke": "How many programmers does it take to change a light bulb? None, that's a hardware problem!"},
    {"id": 4, "joke": "Why did the developer go broke? Because he used up all his cache!"},
    {"id": 5, "joke": "What's a programmer's favorite hangout place? Foo Bar!"}
]

def lambda_handler(event, context):
    """
    Handle API requests:
    - GET /joke - Get random joke
    - GET /jokes - Get all jokes
    - POST /joke - Add new joke
    """
    
    # Parse request
    http_method = event.get('requestContext', {}).get('http', {}).get('method')
    path = event.get('rawPath', '/')
    
    print(f"Method: {http_method}, Path: {path}")
    
    # Route requests
    if http_method == 'GET' and path == '/joke':
        return get_random_joke()
    
    elif http_method == 'GET' and path == '/jokes':
        return get_all_jokes()
    
    elif http_method == 'POST' and path == '/joke':
        return add_joke(event)
    
    elif path == '/':
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'message': 'Welcome to Joke API!',
                'endpoints': {
                    'GET /joke': 'Get a random joke',
                    'GET /jokes': 'Get all jokes',
                    'POST /joke': 'Add a new joke (body: {"joke": "text"})'
                }
            })
        }
    
    # 404 for unknown routes
    return {
        'statusCode': 404,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps({'error': 'Not found'})
    }

def get_random_joke():
    """Return a random joke"""
    joke = random.choice(JOKES)
    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps(joke)
    }

def get_all_jokes():
    """Return all jokes"""
    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps({
            'count': len(JOKES),
            'jokes': JOKES
        })
    }

def add_joke(event):
    """Add a new joke"""
    try:
        # Parse request body
        body = json.loads(event.get('body', '{}'))
        new_joke_text = body.get('joke')
        
        if not new_joke_text:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Missing joke text'})
            }
        
        # Add new joke
        new_id = max([j['id'] for j in JOKES]) + 1
        new_joke = {'id': new_id, 'joke': new_joke_text}
        JOKES.append(new_joke)
        
        return {
            'statusCode': 201,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'message': 'Joke added successfully',
                'joke': new_joke
            })
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': str(e)})
        }
