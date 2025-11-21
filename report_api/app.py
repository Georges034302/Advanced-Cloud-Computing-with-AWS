from flask import Flask, jsonify, request
import requests

app = Flask(__name__)

# In production, this would come from environment variable
STUDENT_API_URL = "http://localhost:8001"

reports = [
    {"id": 1, "student_id": 1, "course": "Data Structures", "grade": "A", "semester": "Fall 2023"},
    {"id": 2, "student_id": 1, "course": "Algorithms", "grade": "A-", "semester": "Spring 2024"},
    {"id": 3, "student_id": 2, "course": "Circuit Design", "grade": "B+", "semester": "Fall 2023"},
    {"id": 4, "student_id": 3, "course": "Linear Algebra", "grade": "A", "semester": "Fall 2023"},
    {"id": 5, "student_id": 4, "course": "Quantum Mechanics", "grade": "A-", "semester": "Spring 2024"},
]

@app.route('/')
def home():
    return jsonify({
        "service": "Report API",
        "version": "1.0",
        "endpoints": [
            {"path": "/", "description": "Service information"},
            {"path": "/reports", "description": "Get all reports"},
            {"path": "/reports/<id>", "description": "Get report by ID"},
            {"path": "/reports/student/<student_id>", "description": "Get reports for a student"},
            {"path": "/health", "description": "Health check endpoint"}
        ]
    })

@app.route('/reports', methods=['GET'])
def get_reports():
    return jsonify(reports)

@app.route('/reports/<int:report_id>', methods=['GET'])
def get_report(report_id):
    report = next((r for r in reports if r["id"] == report_id), None)
    if report:
        return jsonify(report)
    return jsonify({"error": "Report not found"}), 404

@app.route('/reports/student/<int:student_id>', methods=['GET'])
def get_reports_by_student(student_id):
    student_reports = [r for r in reports if r["student_id"] == student_id]
    
    # Try to enrich with student data if Student API is available
    try:
        student_url = request.args.get('student_api_url', STUDENT_API_URL)
        response = requests.get(f"{student_url}/students/{student_id}", timeout=2)
        if response.status_code == 200:
            student_data = response.json()
            return jsonify({
                "student": student_data,
                "reports": student_reports,
                "total_courses": len(student_reports)
            })
    except:
        pass  # If Student API is unavailable, just return reports
    
    return jsonify({
        "student_id": student_id,
        "reports": student_reports,
        "total_courses": len(student_reports)
    })

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "healthy"}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8002)
