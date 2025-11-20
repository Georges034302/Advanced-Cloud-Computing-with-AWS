from app import app

def test_health():
    client = app.test_client()
    resp = client.get('/')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["service"] == "student-api"

def test_get_all_students():
    client = app.test_client()
    resp = client.get('/students')
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data, list)
    assert len(data) >= 1

def test_get_single_student():
    client = app.test_client()
    resp = client.get('/students/1')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["id"] == 1
