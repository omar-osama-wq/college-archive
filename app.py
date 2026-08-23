from flask import Flask, render_template, request, redirect, url_for, send_from_directory, session
import os
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'super_secret_key_for_college_platform'

UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def init_db():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS materials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            year TEXT NOT NULL,
            term TEXT NOT NULL,
            subject TEXT NOT NULL,
            filename TEXT NOT NULL,
            file_type TEXT DEFAULT 'محاضرة',
            likes INTEGER DEFAULT 0,
            uploaded_by TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def index():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    search_query = request.args.get('q', '').strip()
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    if search_query:
        cursor.execute('SELECT id, year, term, subject, filename, file_type, likes, uploaded_by FROM materials WHERE subject LIKE ? OR filename LIKE ?', 
                       ('%' + search_query + '%', '%' + search_query + '%'))
        search_results = [{
            'id': r[0], 'year': r[1], 'term': r[2], 'subject': r[3], 'filename': r[4], 
            'file_type': r[5] or 'محاضرة', 'likes': r[6], 'uploaded_by': r[7] or 'غير معروف'
        } for r in cursor.fetchall()]
    else:
        search_results = None
    conn.close()
    return render_template('index.html', search_query=search_query, search_results=search_results)

@app.route('/department/<year>/<term>')
def view_term(year, term):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT DISTINCT subject FROM materials WHERE year = ? AND term = ?', (year, term))
    subjects_list = cursor.fetchall()
    subjects = {}
    for sub in subjects_list:
        sub_name = sub[0]
        cursor.execute('SELECT id, filename, file_type, likes, uploaded_by FROM materials WHERE year = ? AND term = ? AND subject = ? ORDER BY likes DESC', (year, term, sub_name))
        files = [{
            'id': row[0], 'filename': row[1], 'file_type': row[2] or 'محاضرة', 
            'likes': row[3], 'uploaded_by': row[4] or 'غير معروف'
        } for row in cursor.fetchall()]
        subjects[sub_name] = files
    conn.close()
    return render_template('material.html', year=year, term=term, subjects=subjects)

@app.route('/register', methods=['GET', 'POST'])
def register():
    error = None
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username and password:
            try:
                hashed_password = generate_password_hash(password)
                conn = sqlite3.connect('database.db')
                cursor = conn.cursor()
                cursor.execute('INSERT INTO users (username, password) VALUES (?, ?)', (username, hashed_password))
                conn.commit()
                conn.close()
                return redirect(url_for('login'))
            except sqlite3.IntegrityError:
                error = 'اسم المستخدم ده مستخدم من قبل، اختر اسم تاني!'
        else:
            error = 'الرجاء إدخال اسم المستخدم وكلمة المرور'
    return render_template('register.html', error=error)

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute('SELECT password FROM users WHERE username = ?', (username,))
        user = cursor.fetchone()
        conn.close()
        if user and check_password_hash(user[0], password):
            session['logged_in'] = True
            session['username'] = username
            return redirect(url_for('index'))
        else:
            error = 'اسم المستخدم أو كلمة المرور غير صحيحة!'
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    username = session.get('username')
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, year, term, subject, filename, file_type, likes FROM materials WHERE uploaded_by = ?', (username,))
    my_files = [{
        'id': r[0], 'year': r[1], 'term': r[2], 'subject': r[3], 'filename': r[4], 
        'file_type': r[5] or 'محاضرة', 'likes': r[6]
    } for r in cursor.fetchall()]
    conn.close()
    return render_template('dashboard.html', my_files=my_files, username=username)

@app.route('/upload/<year>/<term>/<subject>', methods=['POST'])
def upload_file(year, term, subject):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    file_type = request.form.get('file_type', 'محاضرة')
    if 'file' in request.files:
        file = request.files['file']
        if file.filename != '':
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
            file.save(file_path)
            uploader = session.get('username')
            conn = sqlite3.connect('database.db')
            cursor = conn.cursor()
            cursor.execute('INSERT INTO materials (year, term, subject, filename, file_type, likes, uploaded_by) VALUES (?, ?, ?, ?, ?, 0, ?)',
                           (year, term, subject, file.filename, file_type, uploader))
            conn.commit()
            conn.close()
    return redirect(url_for('view_term', year=year, term=term))

@app.route('/add_subject/<year>/<term>', methods=['POST'])
def add_subject(year, term):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    subject_name = request.form.get('subject_name')
    file_type = request.form.get('file_type', 'محاضرة')
    if 'file' in request.files and subject_name:
        file = request.files['file']
        if file.filename != '':
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
            file.save(file_path)
            uploader = session.get('username')
            conn = sqlite3.connect('database.db')
            cursor = conn.cursor()
            cursor.execute('INSERT INTO materials (year, term, subject, filename, file_type, likes, uploaded_by) VALUES (?, ?, ?, ?, ?, 0, ?)',
                           (year, term, subject_name.strip(), file.filename, file_type, uploader))
            conn.commit()
            conn.close()
    return redirect(url_for('view_term', year=year, term=term))

@app.route('/like/<int:file_id>/<year>/<term>')
def like_file(file_id, year, term):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE materials SET likes = likes + 1 WHERE id = ?', (file_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('view_term', year=year, term=term))

@app.route('/delete/<int:file_id>/<year>/<term>')
def delete_file(file_id, year, term):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM materials WHERE id = ?', (file_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('view_term', year=year, term=term))

@app.route('/delete_from_dashboard/<int:file_id>')
def delete_from_dashboard(file_id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM materials WHERE id = ?', (file_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('dashboard'))

@app.route('/download/<filename>')
def download_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    app.run(debug=True)
