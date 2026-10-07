from flask import Flask, render_template, request, redirect, session, url_for
import sqlite3
import os

# PostgreSQL is used on Render
# SQLite is used locally
try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    psycopg2 = None
    RealDictCursor = None


app = Flask(__name__)

# Use Render environment variable in production
app.secret_key = os.environ.get(
    "SECRET_KEY",
    "secret_key_examination_system"
)

PASSING_PERCENTAGE = 50.0

DATABASE_URL = os.environ.get("DATABASE_URL")

# --------------------------------------------------
# DATABASE CONNECTION
# --------------------------------------------------

def get_db():
    # PostgreSQL on Render
    if DATABASE_URL:
        if psycopg2 is None:
            raise RuntimeError(
                "psycopg2-binary is required for PostgreSQL."
            )

        conn = psycopg2.connect(DATABASE_URL)
        return conn

    # SQLite locally
    conn = sqlite3.connect(
        "database.db",
        timeout=30.0
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def is_postgres():
    return bool(DATABASE_URL)


def execute_query(cursor, query, params=()):
    """
    Allows the same ? placeholders to work with SQLite
    and PostgreSQL.
    """
    if is_postgres():
        query = query.replace("?", "%s")

    cursor.execute(query, params)


def fetch_one(cursor):
    return cursor.fetchone()


def fetch_all(cursor):
    return cursor.fetchall()


# --------------------------------------------------
# INITIALIZE DATABASE
# --------------------------------------------------

def init_db():
    conn = get_db()
    cursor = conn.cursor()

    if is_postgres():

        # Users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username TEXT UNIQUE,
                password TEXT,
                role TEXT
            )
        """)

        # Exams table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS exams (
                id SERIAL PRIMARY KEY,
                title TEXT
            )
        """)

        # Questions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS questions (
                id SERIAL PRIMARY KEY,
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
                id SERIAL PRIMARY KEY,
                user_id INTEGER,
                exam_id INTEGER,
                score INTEGER,
                total INTEGER,
                status TEXT
            )
        """)

        # Make sure status exists
        cursor.execute("""
            ALTER TABLE results
            ADD COLUMN IF NOT EXISTS status TEXT
        """)

        # Check admin
        execute_query(
            cursor,
            "SELECT * FROM users WHERE username = ?",
            ("admin",)
        )

        admin = fetch_one(cursor)

        if not admin:
            execute_query(
                cursor,
                """
                INSERT INTO users
                (username, password, role)
                VALUES (?, ?, ?)
                """,
                ("admin", "admin123", "admin")
            )

    else:

        # SQLite Users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE,
                password TEXT,
                role TEXT
            )
        """)

        # SQLite Exams table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS exams (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT
            )
        """)

        # SQLite Questions table
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

        # SQLite Results table
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

        # Add status column if required
        try:
            cursor.execute(
                "ALTER TABLE results ADD COLUMN status TEXT"
            )
        except sqlite3.OperationalError:
            pass

        # Check admin
        execute_query(
            cursor,
            "SELECT * FROM users WHERE username = ?",
            ("admin",)
        )

        admin = fetch_one(cursor)

        if not admin:
            execute_query(
                cursor,
                """
                INSERT INTO users
                (username, password, role)
                VALUES (?, ?, ?)
                """,
                ("admin", "admin123", "admin")
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

        if is_postgres():
            cursor = conn.cursor(cursor_factory=RealDictCursor)
        else:
            cursor = conn.cursor()

        execute_query(
            cursor,
            """
            SELECT *
            FROM users
            WHERE username = ? AND password = ?
            """,
            (username, password)
        )

        user = fetch_one(cursor)

        conn.close()

        if user:

            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["role"] = user["role"]

            if user["role"] == "admin":
                return redirect(
                    url_for("admin_dashboard")
                )
            else:
                return redirect(
                    url_for("student_dashboard")
                )

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

            execute_query(
                cursor,
                """
                INSERT INTO users
                (username, password, role)
                VALUES (?, ?, ?)
                """,
                (username, password, "student")
            )

            conn.commit()
            conn.close()

            return redirect(url_for("login"))

        except Exception:

            conn.rollback()
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

    conn = get_db()
    cursor = conn.cursor()

    execute_query(
        cursor,
        "SELECT * FROM exams ORDER BY id"
    )

    exams = fetch_all(cursor)

    conn.close()

    return render_template(
        "admin_dashboard.html",
        exams=exams
    )


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

        execute_query(
            cursor,
            "INSERT INTO exams (title) VALUES (?)",
            (title,)
        )

        conn.commit()
        conn.close()

        return redirect(
            url_for("admin_dashboard")
        )

    return render_template("create_exam.html")


# --------------------------------------------------
# ADD QUESTION
# --------------------------------------------------

@app.route(
    "/add_question",
    methods=["GET", "POST"]
)
@app.route(
    "/add_question/<int:exam_id>",
    methods=["GET", "POST"]
)
def add_question(exam_id=None):

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

        execute_query(
            cursor,
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

        return redirect(
            url_for("admin_dashboard")
        )

    execute_query(
        cursor,
        "SELECT * FROM exams ORDER BY id"
    )

    exams = fetch_all(cursor)

    conn.close()

    return render_template(
        "add_question.html",
        exams=exams,
        selected_exam_id=exam_id
    )


# --------------------------------------------------
# STUDENT DASHBOARD
# --------------------------------------------------

@app.route("/student")
def student_dashboard():

    if session.get("role") != "student":
        return redirect(url_for("login"))

    conn = get_db()

    if is_postgres():
        cursor = conn.cursor(
            cursor_factory=RealDictCursor
        )
    else:
        cursor = conn.cursor()

    # Get all exams
    execute_query(
        cursor,
        "SELECT * FROM exams ORDER BY id"
    )

    exams = fetch_all(cursor)

    # Get student's results
    execute_query(
        cursor,
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
        ORDER BY results.id DESC
        """,
        (session["user_id"],)
    )

    student_results = fetch_all(cursor)

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

    if is_postgres():
        cursor = conn.cursor(
            cursor_factory=RealDictCursor
        )
    else:
        cursor = conn.cursor()

    # Get exam
    execute_query(
        cursor,
        "SELECT * FROM exams WHERE id = ?",
        (exam_id,)
    )

    exam = fetch_one(cursor)

    if not exam:
        conn.close()
        return "Exam not found."

    # Get questions
    execute_query(
        cursor,
        """
        SELECT *
        FROM questions
        WHERE exam_id = ?
        ORDER BY id
        """,
        (exam_id,)
    )

    questions = fetch_all(cursor)

    conn.close()

    return render_template(
        "take_exam.html",
        exam=exam,
        questions=questions
    )


# --------------------------------------------------
# SUBMIT EXAM
# --------------------------------------------------

@app.route(
    "/submit_exam/<int:exam_id>",
    methods=["POST"]
)
def submit_exam(exam_id):

    if session.get("role") != "student":
        return redirect(url_for("login"))

    conn = get_db()

    if is_postgres():
        cursor = conn.cursor(
            cursor_factory=RealDictCursor
        )
    else:
        cursor = conn.cursor()

    # Get questions
    execute_query(
        cursor,
        """
        SELECT *
        FROM questions
        WHERE exam_id = ?
        ORDER BY id
        """,
        (exam_id,)
    )

    questions = fetch_all(cursor)

    score = 0
    total = len(questions)

    # Check answers
    for q in questions:

        selected_option = request.form.get(
            f"q_{q['id']}"
        )

        if selected_option:

            try:

                if int(selected_option) == int(q["correct"]):
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
    execute_query(
        cursor,
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

    return redirect(
        url_for("student_dashboard")
    )


# --------------------------------------------------
# ADMIN RESULTS
# --------------------------------------------------

@app.route("/results")
def results():

    if session.get("role") != "admin":
        return redirect(url_for("login"))

    conn = get_db()

    if is_postgres():
        cursor = conn.cursor(
            cursor_factory=RealDictCursor
        )
    else:
        cursor = conn.cursor()

    execute_query(
        cursor,
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
        ORDER BY results.id DESC
        """
    )

    results_data = fetch_all(cursor)

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

    return redirect(
        url_for("login")
    )


# --------------------------------------------------
# START APPLICATION
# --------------------------------------------------

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )