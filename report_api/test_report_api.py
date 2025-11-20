from app import app, compute_grade

def test_grade_mapping():
    assert compute_grade(90) == "HD"
    assert compute_grade(78) == "D"
    assert compute_grade(68) == "C"
    assert compute_grade(55) == "P"
    assert compute_grade(40) == "F"

def test_reports_endpoint():
    client = app.test_client()
    resp = client.get('/reports')
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert "grade" in data[0]

def test_single_report():
    client = app.test_client()
    resp = client.get('/report/1')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["id"] == 1
    assert "grade" in data
