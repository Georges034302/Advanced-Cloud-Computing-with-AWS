import pytest
from app import app

@pytest.fixture
def client():
    with app.test_client() as client:
        yield client

def test_home(client):
    response = client.get('/')
    assert response.status_code == 200
    data = response.get_json()
    assert data['service'] == 'Student API'

def test_get_students(client):
    response = client.get('/students')
    assert response.status_code == 200
    data = response.get_json()
    assert len(data) == 5
    assert data[0]['name'] == 'Alice Johnson'

def test_get_student_by_id(client):
    response = client.get('/students/1')
    assert response.status_code == 200
    data = response.get_json()
    assert data['name'] == 'Alice Johnson'
    assert data['major'] == 'Computer Science'

def test_get_student_not_found(client):
    response = client.get('/students/999')
    assert response.status_code == 404
    data = response.get_json()
    assert 'error' in data

def test_health(client):
    response = client.get('/health')
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'healthy'
