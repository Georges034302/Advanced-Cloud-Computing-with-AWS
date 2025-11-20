from flask import Flask, jsonify

app = Flask(__name__)

STUDENTS = [
    {"id": 1, "name": "Alice", "mark": 85},
    {"id": 2, "name": "Bob", "mark": 67},
    {"id": 3, "name": "Charlie", "mark": 92},
    {"id": 4, "name": "Diana", "mark": 58},
]

@app.route('/')
def index():
    return jsonify({"service": "student-api", "status": "running"})

@app.route('/students')
def get_students():
    return jsonify(STUDENTS)

@app.route('/students/<int:student_id>')
def get_student(student_id):
    for s in STUDENTS:
        if s["id"] == student_id:
            return jsonify(s)
    return jsonify({"error": "Student not found"}), 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
