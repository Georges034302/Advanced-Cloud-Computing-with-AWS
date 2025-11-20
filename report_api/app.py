from flask import Flask, jsonify

app = Flask(__name__)

STUDENTS = [
    {"id": 1, "name": "Alice", "mark": 85},
    {"id": 2, "name": "Bob", "mark": 67},
    {"id": 3, "name": "Charlie", "mark": 92},
    {"id": 4, "name": "Diana", "mark": 58},
]

def compute_grade(mark):
    if mark >= 85:
        return "HD"
    elif mark >= 75:
        return "D"
    elif mark >= 65:
        return "C"
    elif mark >= 50:
        return "P"
    else:
        return "F"

@app.route('/')
def index():
    return jsonify({"service": "report-api", "status": "running"})

@app.route('/reports')
def all_reports():
    reports = []
    for s in STUDENTS:
        reports.append({
            "id": s["id"],
            "name": s["name"],
            "mark": s["mark"],
            "grade": compute_grade(s["mark"])
        })
    return jsonify(reports)

@app.route('/report/<int:student_id>')
def report_for_student(student_id):
    for s in STUDENTS:
        if s["id"] == student_id:
            return jsonify({
                "id": s["id"],
                "name": s["name"],
                "mark": s["mark"],
                "grade": compute_grade(s["mark"])
            })
    return jsonify({"error": "Student not found"}), 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
