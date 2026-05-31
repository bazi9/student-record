from flask import Flask, render_template, request, jsonify
import configparser
import uuid
import os

app = Flask(__name__)
INI_FILE = 'users.ini'

# Ensure the INI file exists when the app starts
if not os.path.exists(INI_FILE):
    open(INI_FILE, 'w').close()

def get_config():
    config = configparser.ConfigParser()
    config.read(INI_FILE)
    return config

def save_config(config):
    with open(INI_FILE, 'w') as configfile:
        config.write(configfile)

@app.route('/')
def index():
    # Renders the index.html from your 'templates' folder
    return render_template('index.html')

@app.route('/get_students', methods=['GET'])
def get_students():
    config = get_config()
    students = []
    for section in config.sections():
        student = dict(config.items(section))
        student['sys_id'] = section
        students.append(student)
    return jsonify(students)

@app.route('/add_student', methods=['POST'])
def add_student():
    data = request.json
    config = get_config()
    
    # Generate a unique ID for the INI section
    new_sys_id = str(uuid.uuid4())
    
    config[new_sys_id] = {
        'id': str(data.get('id')),
        'name': data.get('name'),
        'age': str(data.get('age')),
        'email': data.get('email'),
        'address': data.get('address')
    }
    save_config(config)
    return jsonify({"status": "success", "sys_id": new_sys_id})

@app.route('/edit_student', methods=['POST'])
def edit_student():
    data = request.json
    sys_id = data.get('sys_id')
    config = get_config()
    
    if sys_id in config:
        config[sys_id]['id'] = str(data.get('id'))
        config[sys_id]['name'] = data.get('name')
        config[sys_id]['age'] = str(data.get('age'))
        config[sys_id]['email'] = data.get('email')
        config[sys_id]['address'] = data.get('address')
        save_config(config)
        return jsonify({"status": "success"})
    return jsonify({"status": "error", "message": "Student not found"}), 404

@app.route('/delete_students', methods=['POST'])
def delete_students():
    data = request.json
    ids_to_remove = data.get('ids', [])
    config = get_config()
    
    for sys_id in ids_to_remove:
        if sys_id in config:
            config.remove_section(sys_id)
            
    save_config(config)
    return jsonify({"status": "success"})

if __name__ == '__main__':
    app.run(debug=True)
