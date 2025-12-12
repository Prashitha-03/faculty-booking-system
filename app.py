import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev_secret_key")  # Use env variable for production

# Database setup
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database.db")

# ---------- DATABASE HELPERS ----------
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            role TEXT,
            password TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS slots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            faculty_name TEXT,
            date TEXT,
            time TEXT,
            booked_by TEXT
        )
    ''')
    conn.commit()
    conn.close()

def seed_users():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) as cnt FROM users")
    if c.fetchone()["cnt"] == 0:
        sample = [
            ('alice_fac', 'faculty', generate_password_hash('pass123')),
            ('bob_stu', 'student', generate_password_hash('pass123'))
        ]
        c.executemany("INSERT INTO users (name, role, password) VALUES (?, ?, ?)", sample)
        conn.commit()
    conn.close()

# Initialize DB and seed users on startup
init_db()
seed_users()

# ---------- ROUTES ----------

@app.route('/')
def home():
    return render_template('index.html')

# Registration
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name'].strip()
        role = request.form['role']
        password = request.form['password']

        if not name or not password:
            flash("Please provide name and password.")
            return redirect(url_for('register'))

        conn = get_conn()
        c = conn.cursor()
        try:
            c.execute(
                "INSERT INTO users (name, role, password) VALUES (?, ?, ?)",
                (name, role, generate_password_hash(password))
            )
            conn.commit()
            flash("Registration successful. You can now login.")
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash("User already exists. Choose a different name.")
            return redirect(url_for('register'))
        finally:
            conn.close()

    return render_template('register.html')

# Login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        name = request.form['name'].strip()
        password = request.form['password']
        role = request.form['role']

        conn = get_conn()
        c = conn.cursor()
        c.execute("SELECT password, role FROM users WHERE name=?", (name,))
        row = c.fetchone()
        conn.close()

        if row is None:
            flash("User not found. Please register or check username.")
            return redirect(url_for('login'))

        db_password = row['password']
        db_role = row['role']

        if db_role != role:
            flash(f"Role mismatch. Selected role: {role} but user role is: {db_role}")
            return redirect(url_for('login'))

        if check_password_hash(db_password, password):
            if role == "faculty":
                return redirect(url_for('faculty', name=name))
            else:
                return redirect(url_for('student', name=name))
        else:
            flash("Incorrect password. Try again.")
            return redirect(url_for('login'))

    return render_template('login.html')

# Faculty dashboard
@app.route('/faculty/<name>', methods=['GET', 'POST'])
def faculty(name):
    conn = get_conn()
    c = conn.cursor()

    if request.method == 'POST':
        date = request.form['date']
        time = request.form['time']
        if date and time:
            c.execute(
                "INSERT INTO slots (faculty_name, date, time, booked_by) VALUES (?, ?, ?, ?)",
                (name, date, time, None)
            )
            conn.commit()

    c.execute("SELECT * FROM slots WHERE faculty_name=?", (name,))
    slots = c.fetchall()
    conn.close()
    return render_template('faculty.html', name=name, slots=slots)

# Student dashboard
@app.route('/student/<name>', methods=['GET', 'POST'])
def student(name):
    conn = get_conn()
    c = conn.cursor()

    if request.method == 'POST':
        slot_id = request.form.get('slot_id')
        if slot_id:
            c.execute(
                "UPDATE slots SET booked_by=? WHERE id=? AND booked_by IS NULL",
                (name, slot_id)
            )
            if c.rowcount == 0:
                flash("Slot already booked by someone else or invalid slot.")
            else:
                conn.commit()
                flash("Slot booked successfully.")

    c.execute("SELECT * FROM slots WHERE booked_by IS NULL")
    slots = c.fetchall()
    conn.close()
    return render_template('student.html', name=name, slots=slots)

# View all confirmed bookings
@app.route('/bookings')
def bookings():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM slots WHERE booked_by IS NOT NULL")
    data = c.fetchall()
    conn.close()
    return render_template('bookings.html', data=data)

# Development helper: re-seed users (dev only)
@app.route('/seed')
def seed_route():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    init_db()
    seed_users()
    return "Database re-initialized and sample users seeded. Use alice_fac / pass123 and bob_stu / pass123"

# List users (dev only)
@app.route('/list_users')
def list_users():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id, name, role FROM users")
    users = c.fetchall()
    conn.close()
    return "<br>".join([f"{u['id']}: {u['name']} ({u['role']})" for u in users])

# ---------- RUN APP ----------
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
