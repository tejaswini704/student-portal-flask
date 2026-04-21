from flask import Flask, render_template, request, redirect, session, url_for, flash, Response
import sqlite3
import os

app = Flask(__name__, template_folder="templates")
app.secret_key = "supersecretkey123"

app.permanent_session_lifetime = 3600

app.config.update(
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=False
)

# ================= DATABASE =================
def get_db_connection():
    conn = sqlite3.connect("student.db", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

# ================= INIT DB =================
def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT,
            role TEXT
        )
    """)

    # ✅ FIXED: added username column (IMPORTANT)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            username TEXT,
            roll TEXT,
            dept TEXT,
            marks INTEGER
        )
    """)

    conn.commit()
    conn.close()

init_db()

# ================= AUTO ADMIN FIX =================
def create_admin():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM users WHERE username='admin'")
    admin = cursor.fetchone()

    if not admin:
        cursor.execute(
            "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
            ("admin", "admin", "admin")
        )
        conn.commit()

    conn.close()

create_admin()

# ================= HOME =================
@app.route('/')
def home():
    return render_template('index.html')

# ================= LOGIN =================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT username, password, role FROM users WHERE username=?",
            (username,)
        )
        user = cursor.fetchone()

        conn.close()

        if user and user[1] == password:

            session.clear()
            session.permanent = True

            role = user[2].strip().lower()

            session['user'] = user[0]
            session['role'] = role

            flash("Login successful!", "success")

            if role == "admin":
                return redirect(url_for('dashboard'))
            elif role == "student":
                return redirect(url_for('student_dashboard'))
            elif role == "teacher":
                return redirect(url_for('teacher_dashboard'))
            else:
                flash("Invalid role in database", "danger")
                return redirect(url_for('login'))

        else:
            flash("Invalid credentials", "danger")

    return render_template('login.html')

# ================= REGISTER =================
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role = request.form['role'].strip().lower()

        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO users (username, password, role)
                VALUES (?, ?, ?)
            """, (username, password, role))

            conn.commit()
            flash("Registration successful! Please login", "success")

        except:
            flash("Username already exists", "danger")

        conn.close()

        return redirect(url_for('login'))

    return render_template('register.html')

# ================= DASHBOARDS =================

# ✅ FIXED STUDENT DASHBOARD (IMPORTANT)
@app.route('/student_dashboard')
def student_dashboard():
    if session.get('role') != 'student':
        return redirect(url_for('login'))

    username = session['user']

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT name, username, roll, dept, marks
        FROM students
        WHERE username = ?
    """, (username,))

    student = cursor.fetchone()
    conn.close()

    return render_template("student_dashboard.html", student=student)


@app.route('/teacher_dashboard')
def teacher_dashboard():
    if session.get('role') != 'teacher':
        return redirect(url_for('login'))
    return render_template("teacher_dashboard.html")

# ================= ADMIN DASHBOARD =================
@app.route('/dashboard')
def dashboard():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM students")
    total_students = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM students WHERE marks >= 40")
    pass_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM students WHERE marks < 40")
    fail_count = cursor.fetchone()[0]

    cursor.execute("""
        SELECT id, name, roll, dept, marks 
        FROM students 
        ORDER BY id DESC 
        LIMIT 5
    """)
    recent_students = cursor.fetchall()

    cursor.execute("SELECT id, username, role FROM users")
    users = cursor.fetchall()

    conn.close()

    return render_template(
        "dashboard.html",
        total_students=total_students,
        pass_count=pass_count,
        fail_count=fail_count,
        recent_students=recent_students,
        users=users
    )

# ================= VIEW =================
@app.route('/view')
def view_students():
    if session.get('role') not in ['admin', 'teacher']:
        return redirect(url_for('login'))

    search = request.args.get('search', '')

    conn = get_db_connection()
    cursor = conn.cursor()

    if search:
        cursor.execute("""
            SELECT id, name, roll, dept, marks
            FROM students
            WHERE name LIKE ? OR roll LIKE ? OR dept LIKE ?
        """, (f"%{search}%", f"%{search}%", f"%{search}%"))
    else:
        cursor.execute("SELECT id, name, roll, dept, marks FROM students")

    students = cursor.fetchall()
    conn.close()

    return render_template("view_students.html", students=students, search=search)

# ================= ADD (FIXED) =================
@app.route('/add', methods=['GET', 'POST'])
def add_student():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))

    if request.method == 'POST':
        name = request.form['name']
        username = request.form['username']   # ✅ FIX ADDED
        roll = request.form['roll']
        dept = request.form['dept']
        marks = request.form['marks']

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO students (name, username, roll, dept, marks)
            VALUES (?, ?, ?, ?, ?)
        """, (name, username, roll, dept, marks))

        conn.commit()
        conn.close()

        flash("Student added successfully!", "success")
        return redirect(url_for('view_students'))

    return render_template('add_student.html')

# ================= STUDENT MARKS (FIXED) =================
@app.route('/student_marks')
def student_marks():
    if 'user' not in session:
        return redirect(url_for('login'))

    username = session['user']

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT name, roll, dept, marks 
        FROM students 
        WHERE username = ?
    """, (username,))

    data = cursor.fetchone()

    conn.close()

    return render_template("student_marks.html", data=data)

# ================= EDIT =================
@app.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit_student(id):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        cursor.execute("""
            UPDATE students
            SET name=?, roll=?, dept=?, marks=?
            WHERE id=?
        """, (
            request.form['name'],
            request.form['roll'],
            request.form['dept'],
            request.form['marks'],
            id
        ))

        conn.commit()
        conn.close()

        flash("Student updated successfully!", "info")
        return redirect(url_for('manage_students'))

    cursor.execute("SELECT id, name, roll, dept, marks FROM students WHERE id=?", (id,))
    student = cursor.fetchone()

    conn.close()

    return render_template('edit_student.html', student=student)

# ================= DELETE =================
@app.route('/delete/<int:id>')
def delete_student(id):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM students WHERE id=?", (id,))
    conn.commit()
    conn.close()

    flash("Student deleted successfully!", "danger")
    return redirect(url_for('manage_students'))

# ================= MANAGE =================
@app.route('/manage')
def manage_students():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id, name, roll, dept, marks FROM students")
    students = cursor.fetchall()

    conn.close()

    return render_template('manage_students.html', students=students)

# ================= LOGOUT =================
@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out successfully!", "info")
    return redirect(url_for('login'))

# ================= EXPORT =================
@app.route('/export')
def export_csv():
    if 'user' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id, name, roll, dept, marks FROM students")
    data = cursor.fetchall()

    conn.close()

    def generate():
        yield "ID,Name,Roll,Department,Marks\n"
        for row in data:
            yield f"{row[0]},{row[1]},{row[2]},{row[3]},{row[4]}\n"

    return Response(
        generate(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=students.csv"}
    )

# ================= RUN =================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)