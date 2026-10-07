from flask import Flask, render_template, request, redirect, session, url_for
import sqlite3

app = Flask(__name__)
app.secret_key = "secret_key_examination_system"

# Passing score threshold (50%)
PASSING_PERCENTAGE = 50.0


def get_db():
    conn = sqlite3.connect("database.db", timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cursor = conn.cursor()

    # Users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT,
            role TEXT
        )
    """)

    # Exams table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS exams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT
        )
    """)

    # Questions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exam_id INTEGER,
            question TEXT,
            option1 TEXT,
            option2 TEXT,
            option3 TEXT,
            option4 TEXT,
            correct INTEGER
        )
    """)

    # Results table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            exam_id INTEGER,
            score INTEGER,
            total INTEGER,
            status TEXT
        )
    """)

    # Add status column if it does not exist
    try:
        cursor.execute("ALTER TABLE results ADD COLUMN status TEXT")
    except sqlite3.OperationalError:
        pass

    # Create default admin account
    cursor.execute(
        "SELECT * FROM users WHERE username = 'admin'"
    )

    if not cursor.fetchone():
        cursor.execute(
            """
            INSERT INTO users (username, password, role)
            VALUES ('admin', 'admin123', 'admin')
            """
        )

    conn.commit()
    conn.close()


# Initialize database
init_db()


# --------------------------------------------------
# HOME
# --------------------------------------------------

@app.route("/")
def home():
    return redirect(url_for("login"))


# --------------------------------------------------
# LOGIN
# --------------------------------------------------

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT * FROM users
            WHERE username = ? AND password = ?
            """,
            (username, password)
        )

        user = cursor.fetchone()
        conn.close()

        if user:

            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["role"] = user["role"]

            if user["role"] == "admin":
                return redirect(url_for("admin_dashboard"))

            else:
                return redirect(url_for("student_dashboard"))

        else:
            return "Invalid Credentials. Please try again."

    return render_template("login.html")


# --------------------------------------------------
# STUDENT REGISTRATION
# --------------------------------------------------

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        conn = get_db()
        cursor = conn.cursor()

        try:

            cursor.execute(
                """
                INSERT INTO users (username, password, role)
                VALUES (?, ?, 'student')
                """,
                (username, password)
            )

            conn.commit()
            conn.close()

            return redirect(url_for("login"))

        except sqlite3.IntegrityError:

            conn.close()

            return "Username already exists!"

    return render_template("register.html")


# --------------------------------------------------
# ADMIN DASHBOARD
# --------------------------------------------------

@app.route("/admin")
def admin_dashboard():

    if session.get("role") != "admin":
        return redirect(url_for("login"))

    return render_template("admin_dashboard.html")


# --------------------------------------------------
# CREATE EXAM
# --------------------------------------------------

@app.route("/add_exam", methods=["GET", "POST"])
def add_exam():

    if session.get("role") != "admin":
        return redirect(url_for("login"))

    if request.method == "POST":

        title = request.form["title"]

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute(
            "INSERT INTO exams (title) VALUES (?)",
            (title,)
        )

        conn.commit()
        conn.close()

        return redirect(url_for("admin_dashboard"))

    return render_template("create_exam.html")


# --------------------------------------------------
# ADD QUESTION
# --------------------------------------------------

@app.route("/add_question", methods=["GET", "POST"])
def add_question():

    if session.get("role") != "admin":
        return redirect(url_for("login"))

    conn = get_db()
    cursor = conn.cursor()

    if request.method == "POST":

        exam_id = request.form["exam_id"]
        question = request.form["question"]
        option1 = request.form["option1"]
        option2 = request.form["option2"]
        option3 = request.form["option3"]
        option4 = request.form["option4"]
        correct = request.form["correct"]

        cursor.execute(
            """
            INSERT INTO questions
            (
                exam_id,
                question,
                option1,
                option2,
                option3,
                option4,
                correct
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                exam_id,
                question,
                option1,
                option2,
                option3,
                option4,
                correct
            )
        )

        conn.commit()
        conn.close()

        return redirect(url_for("admin_dashboard"))

    cursor.execute("SELECT * FROM exams")
    exams = cursor.fetchall()

    conn.close()

    return render_template(
        "add_question.html",
        exams=exams
    )


# --------------------------------------------------
# STUDENT DASHBOARD
# --------------------------------------------------

@app.route("/student")
def student_dashboard():

    if session.get("role") != "student":
        return redirect(url_for("login"))

    conn = get_db()
    cursor = conn.cursor()

    # Get all exams
    cursor.execute("SELECT * FROM exams")
    exams = cursor.fetchall()

    # Get student's results
    cursor.execute(
        """
        SELECT
            exams.title,
            results.score,
            results.total,
            results.status
        FROM results
        JOIN exams
            ON results.exam_id = exams.id
        WHERE results.user_id = ?
        """,
        (session["user_id"],)
    )

    student_results = cursor.fetchall()

    conn.close()

    return render_template(
        "student_dashboard.html",
        exams=exams,
        results=student_results
    )


# --------------------------------------------------
# TAKE EXAM
# --------------------------------------------------

@app.route("/take_exam/<int:exam_id>")
def take_exam(exam_id):

    if session.get("role") != "student":
        return redirect(url_for("login"))

    conn = get_db()
    cursor = conn.cursor()

    # Get exam
    cursor.execute(
        "SELECT * FROM exams WHERE id = ?",
        (exam_id,)
    )

    exam = cursor.fetchone()

    # Exam not found
    if not exam:
        conn.close()
        return "Exam not found."

    # Get questions
    cursor.execute(
        """
        SELECT * FROM questions
        WHERE exam_id = ?
        """,
        (exam_id,)
    )

    questions = cursor.fetchall()

    conn.close()

    return render_template(
        "take_exam.html",
        exam=exam,
        questions=questions
    )


# --------------------------------------------------
# SUBMIT EXAM
# --------------------------------------------------

@app.route("/submit_exam/<int:exam_id>", methods=["POST"])
def submit_exam(exam_id):

    if session.get("role") != "student":
        return redirect(url_for("login"))

    conn = get_db()
    cursor = conn.cursor()

    # Get questions
    cursor.execute(
        """
        SELECT * FROM questions
        WHERE exam_id = ?
        """,
        (exam_id,)
    )

    questions = cursor.fetchall()

    score = 0
    total = len(questions)

    # Check answers
    for q in questions:

        selected_option = request.form.get(
            f"q_{q['id']}"
        )

        if selected_option:

            try:

                if int(selected_option) == q["correct"]:
                    score += 1

            except ValueError:
                pass

    # Calculate percentage
    if total > 0:
        percentage = (score / total) * 100
    else:
        percentage = 0

    # Pass / Fail
    if percentage >= PASSING_PERCENTAGE:
        status = "PASS"
    else:
        status = "FAIL"

    # Save result
    cursor.execute(
        """
        INSERT INTO results
        (
            user_id,
            exam_id,
            score,
            total,
            status
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            session["user_id"],
            exam_id,
            score,
            total,
            status
        )
    )

    conn.commit()
    conn.close()

    return redirect(url_for("student_dashboard"))


# --------------------------------------------------
# ADMIN RESULTS
# --------------------------------------------------

@app.route("/results")
def results():

    if session.get("role") != "admin":
        return redirect(url_for("login"))

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            users.username,
            exams.title,
            results.score,
            results.total,
            results.status
        FROM results
        JOIN users
            ON results.user_id = users.id
        JOIN exams
            ON results.exam_id = exams.id
        """
    )

    results_data = cursor.fetchall()

    conn.close()

    return render_template(
        "results.html",
        results=results_data
    )


# --------------------------------------------------
# LOGOUT
# --------------------------------------------------

@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("login"))


# --------------------------------------------------
# START APPLICATION
# --------------------------------------------------

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )