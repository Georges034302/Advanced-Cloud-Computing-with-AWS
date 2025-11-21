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
    assert data['service'] == 'Report API'

def test_get_reports(client):
    response = client.get('/reports')
    assert response.status_code == 200
    data = response.get_json()
    assert len(data) == 5
    assert data[0]['course'] == 'Data Structures'

def test_get_report_by_id(client):
    response = client.get('/reports/1')
    assert response.status_code == 200
    data = response.get_json()
    assert data['course'] == 'Data Structures'
    assert data['grade'] == 'A'

def test_get_report_not_found(client):
    response = client.get('/reports/999')
    assert response.status_code == 404
    data = response.get_json()
    assert 'error' in data

def test_get_reports_by_student(client):
    response = client.get('/reports/student/1')
    assert response.status_code == 200
    data = response.get_json()
    assert 'reports' in data
    assert data['total_courses'] == 2

def test_health(client):
    response = client.get('/health')
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'healthy'
