from flask import Flask, render_template, request, redirect, url_for, session, flash, g
import json
import os
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from collections import defaultdict
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Replace with a secure secret key

# File paths
USERS_FILE = 'data/users.json'
ACTIVITIES_FILE = 'data/activities.json'
SIGNUPS_FILE = 'data/signups.json'
ATTENDANCE_FILE = 'data/attendance.json'
FEEDBACK_FILE = 'data/feedback.json'

# Helper functions to read and write JSON files
def read_json(file):
    if not os.path.exists('data'):
        os.makedirs('data')
    if not os.path.exists(file):
        with open(file, 'w') as f:
            json.dump([], f)
    with open(file, 'r') as f:
        return json.load(f)

def write_json(file, data):
    with open(file, 'w') as f:
        json.dump(data, f, indent=4)

# Decorators for role-based access
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def roles_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if g.current_user['role'] not in roles:
                flash('You do not have permission to access this page.', 'danger')
                return redirect(url_for('home'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# Initialize admin account if it doesn't exist
def init_admin():
    users = read_json(USERS_FILE)
    admin_exists = any(u['role'] == 'Admin' for u in users)
    if not admin_exists:
        admin_user = {
            'username': 'admin',
            'password': generate_password_hash('admin123'),
            'role': 'Admin',
            'name': 'Administrator',
            'description': '',
            'grade': ''
        }
        users.append(admin_user)
        write_json(USERS_FILE, users)
init_admin()

# Context processor to make current_user available in templates
@app.before_request
def before_request():
    if 'username' in session:
        users = read_json(USERS_FILE)
        g.current_user = next((u for u in users if u['username'] == session['username']), None)
    else:
        g.current_user = None

app.jinja_env.globals.update(current_user=lambda: g.current_user)

# Routes
@app.route('/')
def home():
    return render_template('home.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        users = read_json(USERS_FILE)
        username = request.form['username']
        password = request.form['password']
        role = 'Student'  # Default role
        name = request.form['name']
        description = request.form['description']
        grade = request.form['grade']

        # Check if user already exists
        if any(user['username'] == username for user in users):
            flash('Username already exists!', 'danger')
            return redirect(url_for('register'))

        hashed_password = generate_password_hash(password)
        users.append({
            'username': username,
            'password': hashed_password,
            'role': role,
            'name': name,
            'description': description,
            'grade': grade
        })
        write_json(USERS_FILE, users)
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        users = read_json(USERS_FILE)
        username = request.form['username']
        password = request.form['password']

        user = next((u for u in users if u['username'] == username), None)
        if user and check_password_hash(user['password'], password):
            session['username'] = username
            flash('Login successful!', 'success')
            return redirect(url_for('home'))
        else:
            flash('Invalid credentials!', 'danger')
            return redirect(url_for('login'))

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('home'))

@app.route('/manage_account', methods=['GET', 'POST'])
@login_required
def manage_account():
    users = read_json(USERS_FILE)
    user = next((u for u in users if u['username'] == session['username']), None)
    if request.method == 'POST':
        user['name'] = request.form['name']
        user['description'] = request.form['description']
        user['grade'] = request.form['grade']
        write_json(USERS_FILE, users)
        flash('Account details updated!', 'success')
        return redirect(url_for('manage_account'))
    return render_template('manage_account.html', user=user)

@app.route('/activities')
@login_required
def activities():
    activities = read_json(ACTIVITIES_FILE)
    signups = read_json(SIGNUPS_FILE)
    user_signups = [s['activity_id'] for s in signups if s['username'] == session['username']]
    return render_template('activities.html', activities=activities, user_signups=user_signups)

@app.route('/activities/<int:activity_id>', methods=['GET', 'POST'])
@login_required
def activity(activity_id):
    activities = read_json(ACTIVITIES_FILE)
    activity = next((a for a in activities if a['id'] == activity_id), None)
    if not activity:
        flash('Activity not found.', 'danger')
        return redirect(url_for('activities'))
    if request.method == 'POST':
        signups = read_json(SIGNUPS_FILE)
        # Check for overlapping activities (simplified example)
        if any(s['activity_id'] == activity_id and s['username'] == session['username'] for s in signups):
            flash('You have already signed up for this activity.', 'warning')
        else:
            signups.append({'username': session['username'], 'activity_id': activity_id})
            write_json(SIGNUPS_FILE, signups)
            flash('You have signed up for the activity!', 'success')
        return redirect(url_for('activities'))
    return render_template('activity.html', activity=activity)

@app.route('/create_activity', methods=['GET', 'POST'])
@login_required
@roles_required('Teacher', 'Admin')
def create_activity():
    if request.method == 'POST':
        activities = read_json(ACTIVITIES_FILE)
        activity_id = max([a['id'] for a in activities], default=0) + 1
        name = request.form['name']
        description = request.form['description']
        activities.append({'id': activity_id, 'name': name, 'description': description})
        write_json(ACTIVITIES_FILE, activities)
        flash('Activity created successfully!', 'success')
        return redirect(url_for('activities'))
    return render_template('create_activity.html')

@app.route('/attendance')
@login_required
def attendance():
    users = read_json(USERS_FILE)
    current_user = next((u for u in users if u['username'] == session['username']), None)
    activities = read_json(ACTIVITIES_FILE)
    activity_dict = {activity['id']: activity for activity in activities}
    if current_user['role'] == 'Student':
        signups = read_json(SIGNUPS_FILE)
        user_activities = [s['activity_id'] for s in signups if s['username'] == session['username']]
        user_activity_details = [activity_dict[a_id] for a_id in user_activities]
        attendance = read_json(ATTENDANCE_FILE)
        user_attendance = [att for att in attendance if att['username'] == session['username']]
        attendance_status = {att['activity_id']: att['status'] for att in user_attendance}
        return render_template('attendance.html', activities=user_activity_details, attendance_status=attendance_status)
    else:
        # For Teacher and Admin to view activities
        activities = read_json(ACTIVITIES_FILE)
        return render_template('attendance_overview.html', activities=activities)

@app.route('/attendance/overview')
@login_required
@roles_required('Teacher', 'Admin')
def attendance_overview():
    users = read_json(USERS_FILE)
    students = [u for u in users if u['role'] == 'Student']
    attendance = read_json(ATTENDANCE_FILE)
    activities = read_json(ACTIVITIES_FILE)
    activity_dict = {activity['id']: activity['name'] for activity in activities}

    # Prepare student attendance data
    student_attendance = []
    for student in students:
        attended_records = [att for att in attendance if att['username'] == student['username']]
        attendance_records = []
        for activity in activities:
            att_status = next((att['status'] for att in attended_records if att['activity_id'] == activity['id']), None)
            if att_status:
                status = att_status
            else:
                # Check if the student signed up for the activity
                signups = read_json(SIGNUPS_FILE)
                signed_up = any(s['username'] == student['username'] and s['activity_id'] == activity['id'] for s in signups)
                if signed_up:
                    status = 'Not Marked'
                else:
                    status = 'Not Enrolled'
            attendance_records.append({
                'activity_name': activity['name'],
                'status': status
            })
        student_attendance.append({
            'username': student['username'],
            'name': student['name'],
            'attendance_records': attendance_records
        })

    return render_template(
        'student_attendance.html',
        student_attendance=student_attendance,
        activities=activities
    )

@app.route('/attendance/activity/<int:activity_id>')
@login_required
@roles_required('Teacher', 'Admin')
def activity_attendance(activity_id):
    activities = read_json(ACTIVITIES_FILE)
    activity = next((a for a in activities if a['id'] == activity_id), None)
    if not activity:
        flash('Activity not found.', 'danger')
        return redirect(url_for('attendance'))

    attendance = read_json(ATTENDANCE_FILE)
    signups = read_json(SIGNUPS_FILE)
    users = read_json(USERS_FILE)

    # Students who signed up for the activity
    signed_up_users = [s['username'] for s in signups if s['activity_id'] == activity_id]

    # Prepare data for attendance table
    student_attendance = []
    for username in signed_up_users:
        user = next((u for u in users if u['username'] == username), None)
        att_record = next((att for att in attendance if att['username'] == username and att['activity_id'] == activity_id), None)
        status = att_record['status'] if att_record else 'Not Marked'
        student_attendance.append({
            'username': username,
            'name': user['name'] if user else 'Unknown',
            'status': status
        })

    return render_template(
        'activity_attendance.html',
        activity=activity,
        student_attendance=student_attendance
    )

@app.route('/mark_attendance')
@login_required
@roles_required('Teacher', 'Admin')
def mark_attendance():
    activities = read_json(ACTIVITIES_FILE)
    return render_template('mark_attendance.html', activities=activities)

@app.route('/mark_attendance/<int:activity_id>', methods=['GET', 'POST'])
@login_required
@roles_required('Teacher', 'Admin')
def mark_attendance_activity(activity_id):
    activities = read_json(ACTIVITIES_FILE)
    activity = next((a for a in activities if a['id'] == activity_id), None)
    if not activity:
        flash('Activity not found.', 'danger')
        return redirect(url_for('mark_attendance'))

    signups = read_json(SIGNUPS_FILE)
    users = read_json(USERS_FILE)
    attendance = read_json(ATTENDANCE_FILE)

    # Students who signed up for the activity
    signed_up_users = [s['username'] for s in signups if s['activity_id'] == activity_id]
    students = [u for u in users if u['username'] in signed_up_users]

    if request.method == 'POST':
        for student in students:
            status = request.form.get(f'status_{student["username"]}')
            # Remove existing attendance record for this student and activity
            attendance = [att for att in attendance if not (att['username'] == student['username'] and att['activity_id'] == activity_id)]
            # Only save attendance if status is provided
            if status and status != 'Not Marked':
                attendance.append({
                    'username': student['username'],
                    'activity_id': activity_id,
                    'status': status,
                    'timestamp': datetime.now().isoformat()
                })
        write_json(ATTENDANCE_FILE, attendance)
        flash('Attendance updated successfully!', 'success')
        return redirect(url_for('activity_attendance', activity_id=activity_id))

    # Prepare current attendance status
    attendance_status = {}
    for student in students:
        att_record = next((att for att in attendance if att['username'] == student['username'] and att['activity_id'] == activity_id), None)
        attendance_status[student['username']] = att_record['status'] if att_record else 'Not Marked'

    return render_template(
        'mark_attendance_activity.html',
        activity=activity,
        students=students,
        attendance_status=attendance_status
    )

@app.route('/feedback/<int:activity_id>', methods=['GET', 'POST'])
@login_required
def feedback(activity_id):
    if request.method == 'POST':
        feedback = read_json(FEEDBACK_FILE)
        comments = request.form['comments']
        rating = int(request.form['rating'])
        feedback.append({
            'username': session['username'],
            'activity_id': activity_id,
            'comments': comments,
            'rating': rating
        })
        write_json(FEEDBACK_FILE, feedback)
        flash('Thank you for your feedback!', 'success')
        return redirect(url_for('activities'))
    activities = read_json(ACTIVITIES_FILE)
    activity = next((a for a in activities if a['id'] == activity_id), None)
    return render_template('feedback.html', activity=activity)

@app.route('/dashboard')
@login_required
@roles_required('Teacher', 'Admin')
def dashboard():
    feedback = read_json(FEEDBACK_FILE)
    attendance = read_json(ATTENDANCE_FILE)
    users = read_json(USERS_FILE)
    activities = read_json(ACTIVITIES_FILE)
    activity_dict = {activity['id']: activity['name'] for activity in activities}

    # Prepare attendance counts per activity
    attendance_counts = defaultdict(int)
    for att in attendance:
        if att['status'] == 'Present':
            activity_name = activity_dict.get(att['activity_id'], 'Unknown Activity')
            attendance_counts[activity_name] += 1

    # Prepare data for Chart.js
    attendance_chart_data = {
        'labels': list(attendance_counts.keys()),
        'data': list(attendance_counts.values())
    }

    return render_template(
        'dashboard.html',
        feedback=feedback,
        attendance=attendance,
        users=users,
        activity_dict=activity_dict,
        attendance_chart_data=json.dumps(attendance_chart_data)
    )

@app.route('/manage_users', methods=['GET', 'POST'])
@login_required
@roles_required('Admin')
def manage_users():
    users = read_json(USERS_FILE)
    if request.method == 'POST':
        username = request.form['username']
        new_role = request.form['role']
        user = next((u for u in users if u['username'] == username), None)
        if user:
            user['role'] = new_role
            write_json(USERS_FILE, users)
            flash('User role updated!', 'success')
        else:
            flash('User not found.', 'danger')
        return redirect(url_for('manage_users'))
    return render_template('manage_users.html', users=users)

if __name__ == '__main__':
    app.run(debug=True)
