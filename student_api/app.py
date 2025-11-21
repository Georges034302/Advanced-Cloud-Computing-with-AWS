from flask import Flask, jsonify

app = Flask(__name__)

students = [
    {"id": 1, "name": "Alice Johnson", "major": "Computer Science", "gpa": 3.8},
    {"id": 2, "name": "Bob Smith", "major": "Electrical Engineering", "gpa": 3.6},
    {"id": 3, "name": "Charlie Brown", "major": "Mathematics", "gpa": 3.9},
    {"id": 4, "name": "Diana Prince", "major": "Physics", "gpa": 3.7},
    {"id": 5, "name": "Eve Davis", "major": "Chemistry", "gpa": 3.5}
]

@app.route('/')
def home():
    return jsonify({
        "service": "Student API",
        "version": "1.0",
        "endpoints": [
            {"path": "/", "description": "Service information"},
            {"path": "/students", "description": "Get all students"},
            {"path": "/students/<id>", "description": "Get student by ID"},
            {"path": "/health", "description": "Health check endpoint"}
        ]
    })

@app.route('/students', methods=['GET'])
def get_students():
    return jsonify(students)

@app.route('/students/<int:student_id>', methods=['GET'])
def get_student(student_id):
    student = next((s for s in students if s["id"] == student_id), None)
    if student:
        return jsonify(student)
    return jsonify({"error": "Student not found"}), 404

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "healthy"}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8001)
