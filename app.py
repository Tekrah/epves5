from flask import Flask, render_template, request, redirect, url_for, session
import mysql.connector
from transformers import BartForConditionalGeneration, BartTokenizer
from flask_cors import CORS

app = Flask(__name__, static_folder='static', template_folder='templates')
app.secret_key = 'your_secret_key'  # Replace with a strong secret key
CORS(app)  # Enable CORS for frontend-backend communication

# Initialize BART model and tokenizer
tokenizer = BartTokenizer.from_pretrained('facebook/bart-large-cnn')
model = BartForConditionalGeneration.from_pretrained('facebook/bart-large-cnn')

# Helper function to enforce login
# Enhanced login_required decorator
def login_required(role=None):
    def decorator(func):
        def wrapper(*args, **kwargs):
            if role == 'manager' and 'manager_id' not in session:
                session['redirect_url'] = request.path  # Save the requested URL
                return redirect(url_for('login'))  # Redirect to manager login
            elif role == 'feedback_giver' and 'student_id' not in session and 'parent_id' not in session:
                session['redirect_url'] = request.path  # Save the requested URL
                return redirect(url_for('role_selection'))  # Redirect to role selection
            return func(*args, **kwargs)
        wrapper.__name__ = func.__name__
        return wrapper
    return decorator

# Database connection function
def get_db_connection():
    return mysql.connector.connect(
        host='localhost',
        user='root',
        password='capstone',  # Replace with your MySQL password
        database='fein'
    )

@app.route('/')
def index():
    return render_template('select_role.html')

@app.route('/select_role', methods=['GET', 'POST'])
def select_role():
    if request.method == 'POST':
        role = request.form['role']
        if role == 'manager':
            return redirect(url_for('login'))
        elif role == 'feedback_giver':
            return redirect(url_for('role_selection'))  # Go to role selection (parent/student)
    return render_template('select_role.html')

@app.route('/role_selection', methods=['GET', 'POST'])
def role_selection():
    if request.method == 'POST':
        role_type = request.form['role_type']
        if role_type == 'parent':
            return redirect(url_for('parent_feedback_form'))
        elif role_type == 'student':
            return redirect(url_for('student_login_form'))
    return render_template('role_selection.html')

@app.route('/faculty_list')
@login_required(role='feedback_giver')
def faculty_list():
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM faculty")
    faculties = cursor.fetchall()
    db.close()
    return render_template('faculty_list.html', faculties=faculties)

@app.route('/parent_feedback', methods=['GET', 'POST'])
@login_required(role='feedback_giver')
def parent_feedback_form():
    if request.method == 'POST':
        parent_name = request.form['parent_name']
        parent_number = request.form['parent_number']
        ward_name = request.form['ward_name']

        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute("INSERT INTO parents (parent_name, parent_number, ward_name) VALUES (%s, %s, %s)",
                       (parent_name, parent_number, ward_name))
        db.commit()

        cursor.execute("SELECT LAST_INSERT_ID()")
        parent_id = cursor.fetchone()[0]
        session['parent_id'] = parent_id
        session['parent_name'] = parent_name
        session['parent_number'] = parent_number
        session['ward_name'] = ward_name
        db.close()

        # Redirect to the originally requested page
        return redirect(session.pop('redirect_url', url_for('faculty_list')))
    return render_template('parent_feedback_form.html')

@app.route('/feedback/<int:faculty_id>', methods=['GET', 'POST'])
@login_required(role='feedback_giver')
def feedback(faculty_id):
    if request.method == 'POST':
        if 'parent_id' in session:
            # Handle parent feedback submission
            competence = request.form['competence']
            attitude = request.form['attitude']
            task_resolution = request.form['task_resolution']
            patience_composure = request.form['patience_composure']
            availability = request.form['availability']
            subjective_feedback = request.form['subjective_feedback']

            name = session.get('parent_name')
            num = session.get('parent_number')
            ward = session.get('ward_name')

            db = get_db_connection()
            cursor = db.cursor()
            cursor.execute(
                """
                INSERT INTO parent_feedback (parent_name, parent_number, ward_name, faculty_id, competence, attitude, task_resolution, patience_composure, availability, subjective_feedback)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    name, num, ward, faculty_id,
                    competence, attitude, task_resolution,
                    patience_composure, availability, subjective_feedback
                )
            )
            db.commit()
            db.close()

            return redirect(url_for('success'))

        elif 'student_id' in session:
            # Handle student feedback submission
            competence = request.form['competence']
            attitude = request.form['attitude']
            task_resolution = request.form['task_resolution']
            patience_composure = request.form['patience_composure']
            availability = request.form['availability']
            subjective_feedback = request.form['subjective_feedback']

            email = session.get('email')

            db = get_db_connection()
            cursor = db.cursor()
            cursor.execute(
                """
                INSERT INTO student_feedback (student_email, faculty_id, competence, attitude, task_resolution, patience_composure, availability, subjective_feedback)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    email, faculty_id,
                    competence, attitude, task_resolution,
                    patience_composure, availability, subjective_feedback
                )
            )
            db.commit()
            db.close()

            return redirect(url_for('success'))

    return render_template('feedback_form.html', faculty_id=faculty_id)

@app.route('/student_login', methods=['GET', 'POST'])
def student_login_form():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        if not email.endswith('@gitam.in'):
            return "Invalid email format", 400

        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute("SELECT id, password FROM students WHERE email = %s", (email,))
        student = cursor.fetchone()
        db.close()

        if student and student[1] == password:
            session['student_id'] = student[0]
            session['email'] = email
            # Redirect to the originally requested page
            return redirect(session.pop('redirect_url', url_for('faculty_list')))
        return "Invalid credentials", 401
    return render_template('student_login_form.html')

@app.route('/success', methods=['GET', 'POST'])
def success():
    return render_template('success.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Authenticate manager credentials
        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute("SELECT id, password FROM managers WHERE username = %s", (username,))
        manager = cursor.fetchone()
        db.close()

        if manager and manager[1] == password:  # Valid credentials
            session['manager_id'] = manager[0]  # Save manager ID in session
            return redirect(session.pop('redirect_url', url_for('dashboard')))  # Redirect to requested page or dashboard
        return "Invalid credentials", 401  # Invalid credentials response

    return render_template('login.html')  # Render login form for GET requests

@app.route('/dashboard')
@login_required(role='manager')  # Only accessible by logged-in managers
def dashboard():
    # Session check is enforced by login_required decorator
    manager_id = session.get('manager_id')
    
    db = get_db_connection()
    cursor = db.cursor()

    # Fetch faculties managed by the manager
    cursor.execute("SELECT id, name FROM faculty WHERE manager_id = %s", (manager_id,))
    faculties = cursor.fetchall()

    # Collect summaries and adjectives for each faculty
    summaries = {}
    for faculty in faculties:
        faculty_id = faculty[0]

        cursor.execute("""
            SELECT summary, competence_avg, attitude_avg, task_resolution_avg, patience_composure_avg, availability_avg
            FROM parent_feedback_summary WHERE faculty_id = %s
        """, (faculty_id,))
        parent_summary_row = cursor.fetchone()

        cursor.execute("""
            SELECT summary, competence_avg, attitude_avg, task_resolution_avg, patience_composure_avg, availability_avg
            FROM student_feedback_summary WHERE faculty_id = %s
        """, (faculty_id,))
        student_summary_row = cursor.fetchone()

        cursor.execute("""
            SELECT adjective_type, adjective, count
            FROM employee_adjectives WHERE faculty_id = %s
        """, (faculty_id,))
        adjectives = cursor.fetchall()

        summaries[faculty_id] = {
            'name': faculty[1],
            'parent_summary': parent_summary_row if parent_summary_row else None,
            'student_summary': student_summary_row if student_summary_row else None,
            'adjectives': adjectives
        }

    db.close()
    return render_template('dashboard_man.html', faculties=faculties, summaries=summaries)

@app.route('/logout')
def logout():
    # Clear all session data
    session.pop('student_id', None)
    session.pop('parent_id', None)
    session.pop('manager_id', None)
    return redirect(url_for('index'))  # Redirect to the home page

if __name__ == '__main__':
    app.run(debug=True)
