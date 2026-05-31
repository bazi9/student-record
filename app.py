from flask import Flask, render_template, request, jsonify
import uuid
import configparser
import os

app = Flask(__name__)
DATA_FILE = 'users.ini'

def load_students():
    config = configparser.ConfigParser()
    students_list = []
    
    if os.path.exists(DATA_FILE):
        config.read(DATA_FILE)
        for section in config.sections():
            student = dict(config[section])
            student['sys_id'] = section 
            students_list.append(student)
            
    return students_list

def save_students(students_list):
    config = configparser.ConfigParser()
    
    for student in students_list:
        sys_id = student['sys_id']
        config[sys_id] = {
            'id': student['id'],
            'name': student['name'],
            'age': str(student['age']),
            'email': student['email'],
            'address': student['address']
        }
        
    with open(DATA_FILE, 'w') as configfile:
        config.write(configfile)

students = load_students()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get_students', methods=['GET'])
def get_students():
    return jsonify(students)

@app.route('/add_student', methods=['POST'])
def add_student():
    data = request.json
    new_student = {
        "sys_id": str(uuid.uuid4()), 
        "id": data['id'],
        "name": data['name'],
        "age": data['age'],
        "email": data['email'],
        "address": data['address']
    }
    students.append(new_student)
    save_students(students) 
    
    return jsonify({"status": "success"})

# NEW: Route to handle editing students
@app.route('/edit_student', methods=['POST'])
def edit_student():
    data = request.json
    sys_id_to_edit = data.get('sys_id')
    global students
    
    # Find the student and update their info
    for student in students:
        if student['sys_id'] == sys_id_to_edit:
            student['id'] = data['id']
            student['name'] = data['name']
            student['age'] = data['age']
            student['email'] = data['email']
            student['address'] = data['address']
            break
            
    save_students(students)
    return jsonify({"status": "success"})

@app.route('/delete_students', methods=['POST'])
def delete_students():
    ids_to_remove = request.json.get('ids', [])
    global students
    students = [s for s in students if s['sys_id'] not in ids_to_remove]
    save_students(students)
    
    return jsonify({"status": "success"})

if __name__ == '__main__':
    app.run(debug=True)