from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
import os

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    psycopg2 = None


app = Flask(__name__)

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "online-examination-secret-key"
)

DATABASE_URL = os.environ.get("DATABASE_URL")

PASSING_PERCENTAGE = 50.0


# ============================================================
# DATABASE
# ============================================================

def using_postgresql():
    return DATABASE_URL is not None and psycopg2 is not None


def get_db():
    if using_postgresql():
        return psycopg2.connect(DATABASE_URL)

    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    return conn


def execute_query(cursor, query, params=()):
    if using_postgresql():
        query = query.replace("?", "%s")

    cursor.execute(query, params)


def fetch_one(cursor):
    return cursor.fetchone()


def fetch_all(cursor):
    return cursor.fetchall()


# ============================================================
# INITIALIZE DATABASE
# ============================================================

def init_db():

    conn = get_db()

    if using_postgresql():

        cursor = conn.cursor(
            cursor_factory=RealDictCursor
        )

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                role TEXT NOT NULL
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS exams (
                id SERIAL PRIMARY KEY,
                title TEXT NOT NULL,
                duration INTEGER DEFAULT 60
            )
        """)

        # Add duration to old PostgreSQL database
        cursor.execute("""
            ALTER TABLE exams
            ADD COLUMN IF NOT EXISTS duration INTEGER DEFAULT 60
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS questions (
                id SERIAL PRIMARY KEY,
                exam_id INTEGER NOT NULL
                    REFERENCES exams(id)
                    ON DELETE CASCADE,
                question TEXT NOT NULL,
                option1 TEXT NOT NULL,
                option2 TEXT NOT NULL,
                option3 TEXT NOT NULL,
                option4 TEXT NOT NULL,
                correct INTEGER NOT NULL
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS results (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL
                    REFERENCES users(id)
                    ON DELETE CASCADE,
                exam_id INTEGER NOT NULL
                    REFERENCES exams(id)
                    ON DELETE CASCADE,
                score INTEGER NOT NULL,
                total INTEGER NOT NULL,
                status TEXT
            )
        """)

        cursor.execute("""
            ALTER TABLE results
            ADD COLUMN IF NOT EXISTS status TEXT
        """)

        cursor.execute("""
            INSERT INTO users
                (username, password, role)
            VALUES
                ('admin', 'admin123', 'admin')
            ON CONFLICT (username) DO NOTHING
        """)

    else:

        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                role TEXT NOT NULL
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS exams (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                duration INTEGER DEFAULT 60
            )
        """)

        # Check old SQLite database for duration column
        cursor.execute("PRAGMA table_info(exams)")
        exam_columns = [
            row["name"] for row in cursor.fetchall()
        ]

        if "duration" not in exam_columns:
            cursor.execute("""
                ALTER TABLE exams
                ADD COLUMN duration INTEGER DEFAULT 60
            """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                exam_id INTEGER NOT NULL,
                question TEXT NOT NULL,
                option1 TEXT NOT NULL,
                option2 TEXT NOT NULL,
                option3 TEXT NOT NULL,
                option4 TEXT NOT NULL,
                correct INTEGER NOT NULL,
                FOREIGN KEY (exam_id)
                    REFERENCES exams(id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                exam_id INTEGER NOT NULL,
                score INTEGER NOT NULL,
                total INTEGER NOT NULL,
                status TEXT,
                FOREIGN KEY (user_id)
                    REFERENCES users(id),
                FOREIGN KEY (exam_id)
                    REFERENCES exams(id)
            )
        """)

        cursor.execute("PRAGMA table_info(results)")
        result_columns = [
            row["name"] for row in cursor.fetchall()
        ]

        if "status" not in result_columns:
            cursor.execute("""
                ALTER TABLE results
                ADD COLUMN status TEXT
            """)

        cursor.execute("""
            INSERT OR IGNORE INTO users
                (username, password, role)
            VALUES
                ('admin', 'admin123', 'admin')
        """)

    conn.commit()
    conn.close()


# ============================================================
# HOME
# ============================================================

@app.route("/")
def home():
    return redirect(url_for("login"))


# ============================================================
# LOGIN
# ============================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    message = ""

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        conn = get_db()

        if using_postgresql():
            cursor = conn.cursor(
                cursor_factory=RealDictCursor
            )
        else:
            cursor = conn.cursor()

        execute_query(
            cursor,
            """
            SELECT *
            FROM users
            WHERE username = ?
            AND password = ?
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

            return redirect(
                url_for("student_dashboard")
            )

        message = "Invalid username or password"

    return render_template(
        "login.html",
        message=message
    )


# ============================================================
# STUDENT REGISTRATION
# ============================================================

@app.route("/register", methods=["GET", "POST"])
def register():

    message = ""

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        conn = get_db()

        try:

            cursor = conn.cursor()

            execute_query(
                cursor,
                """
                INSERT INTO users
                    (username, password, role)
                VALUES
                    (?, ?, 'student')
                """,
                (username, password)
            )

            conn.commit()
            conn.close()

            return redirect(url_for("login"))

        except Exception:

            conn.rollback()
            conn.close()

            message = "Username already exists"

    return render_template(
        "register.html",
        message=message
    )


# ============================================================
# ADMIN DASHBOARD
# ============================================================

@app.route("/admin")
def admin_dashboard():

    if session.get("role") != "admin":
        return redirect(url_for("login"))

    conn = get_db()

    if using_postgresql():
        cursor = conn.cursor(
            cursor_factory=RealDictCursor
        )
    else:
        cursor = conn.cursor()

    execute_query(
        cursor,
        """
        SELECT *
        FROM exams
        ORDER BY id
        """
    )

    exams = fetch_all(cursor)

    conn.close()

    return render_template(
        "admin_dashboard.html",
        exams=exams
    )


# ============================================================
# CREATE EXAM
# ============================================================

@app.route("/add_exam", methods=["GET", "POST"])
def add_exam():

    if session.get("role") != "admin":
        return redirect(url_for("login"))

    if request.method == "POST":

        title = request.form["title"].strip()

        duration_text = request.form.get(
            "duration",
            "60"
        )

        try:
            duration = int(duration_text)
        except ValueError:
            duration = 60

        if duration < 1:
            duration = 60

        if not title:
            return render_template(
                "create_exam.html",
                message="Please enter an exam name"
            )

        conn = get_db()

        if using_postgresql():

            cursor = conn.cursor(
                cursor_factory=RealDictCursor
            )

            execute_query(
                cursor,
                """
                INSERT INTO exams
                    (title, duration)
                VALUES
                    (?, ?)
                RETURNING id
                """,
                (title, duration)
            )

            new_exam = fetch_one(cursor)
            exam_id = new_exam["id"]

        else:

            cursor = conn.cursor()

            execute_query(
                cursor,
                """
                INSERT INTO exams
                    (title, duration)
                VALUES
                    (?, ?)
                """,
                (title, duration)
            )

            exam_id = cursor.lastrowid

        conn.commit()
        conn.close()

        # Automatically open Add Questions
        # for the newly-created exam.
        return redirect(
            url_for(
                "add_question",
                exam_id=exam_id
            )
        )

    return render_template(
        "create_exam.html"
    )


# ============================================================
# ADD QUESTION
# ============================================================

@app.route("/add_question", methods=["GET", "POST"])
@app.route("/add_question/<int:exam_id>", methods=["GET", "POST"])
def add_question(exam_id=None):

    if session.get("role") != "admin":
        return redirect(url_for("login"))

    conn = get_db()

    if using_postgresql():
        cursor = conn.cursor(
            cursor_factory=RealDictCursor
        )
    else:
        cursor = conn.cursor()

    # --------------------------------------------------------
    # ADD QUESTION
    # --------------------------------------------------------

    if request.method == "POST":

        selected_exam_id = request.form.get(
            "exam_id"
        )

        question = request.form["question"].strip()
        option1 = request.form["option1"].strip()
        option2 = request.form["option2"].strip()
        option3 = request.form["option3"].strip()
        option4 = request.form["option4"].strip()
        correct = request.form["correct"]

        if not selected_exam_id:
            conn.close()
            return "Please select an exam."

        execute_query(
            cursor,
            """
            SELECT *
            FROM exams
            WHERE id = ?
            """,
            (selected_exam_id,)
        )

        selected_exam = fetch_one(cursor)

        if not selected_exam:
            conn.close()
            return "Selected exam does not exist."

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
                selected_exam_id,
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

        # Stay on the same exam.
        return redirect(
            url_for(
                "add_question",
                exam_id=int(selected_exam_id)
            )
        )

    # --------------------------------------------------------
    # GET EXAMS
    # --------------------------------------------------------

    execute_query(
        cursor,
        """
        SELECT *
        FROM exams
        ORDER BY id
        """
    )

    exams = fetch_all(cursor)

    selected_exam = None
    questions = []

    # --------------------------------------------------------
    # SELECTED EXAM
    # --------------------------------------------------------

    if exam_id is not None:

        execute_query(
            cursor,
            """
            SELECT *
            FROM exams
            WHERE id = ?
            """,
            (exam_id,)
        )

        selected_exam = fetch_one(cursor)

        if selected_exam:

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
        "add_question.html",
        exams=exams,
        selected_exam_id=exam_id,
        selected_exam=selected_exam,
        questions=questions
    )


# ============================================================
# STUDENT DASHBOARD
# ============================================================

@app.route("/student")
def student_dashboard():

    if session.get("role") != "student":
        return redirect(url_for("login"))

    conn = get_db()

    if using_postgresql():
        cursor = conn.cursor(
            cursor_factory=RealDictCursor
        )
    else:
        cursor = conn.cursor()

    execute_query(
        cursor,
        """
        SELECT *
        FROM exams
        ORDER BY id
        """
    )

    exams = fetch_all(cursor)

    conn.close()

    return render_template(
        "student_dashboard.html",
        exams=exams
    )


# ============================================================
# TAKE EXAM
# ============================================================

@app.route("/take_exam/<int:exam_id>")
def take_exam(exam_id):

    if session.get("role") != "student":
        return redirect(url_for("login"))

    conn = get_db()

    if using_postgresql():
        cursor = conn.cursor(
            cursor_factory=RealDictCursor
        )
    else:
        cursor = conn.cursor()

    # Get exam
    execute_query(
        cursor,
        """
        SELECT *
        FROM exams
        WHERE id = ?
        """,
        (exam_id,)
    )

    exam = fetch_one(cursor)

    if not exam:
        conn.close()
        return "Exam not found."

    # Get questions for this exam
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


# ============================================================
# SUBMIT EXAM
# ============================================================

@app.route("/submit_exam/<int:exam_id>", methods=["POST"])
def submit_exam(exam_id):

    if session.get("role") != "student":
        return redirect(url_for("login"))

    conn = get_db()

    if using_postgresql():
        cursor = conn.cursor(
            cursor_factory=RealDictCursor
        )
    else:
        cursor = conn.cursor()

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

    for question in questions:

        answer = request.form.get(
            f"question_{question['id']}"
        )

        if answer is not None:

            try:

                if int(answer) == int(
                    question["correct"]
                ):
                    score += 1

            except ValueError:
                pass

    if total > 0:
        percentage = (
            score / total
        ) * 100
    else:
        percentage = 0

    if percentage >= PASSING_PERCENTAGE:
        status = "PASS"
    else:
        status = "FAIL"

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

    return render_template(
        "result.html",
        score=score,
        total=total,
        percentage=percentage,
        status=status
    )


# ============================================================
# STUDENT RESULTS
# ============================================================

@app.route("/student_results")
def student_results():

    if session.get("role") != "student":
        return redirect(url_for("login"))

    conn = get_db()

    if using_postgresql():
        cursor = conn.cursor(
            cursor_factory=RealDictCursor
        )
    else:
        cursor = conn.cursor()

    execute_query(
        cursor,
        """
        SELECT
            results.id,
            exams.title AS exam_title,
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

    results_data = fetch_all(cursor)

    conn.close()

    return render_template(
        "student_results.html",
        results=results_data
    )


# ============================================================
# ADMIN RESULTS
# ============================================================

@app.route("/results")
def results():

    if session.get("role") != "admin":
        return redirect(url_for("login"))

    conn = get_db()

    if using_postgresql():
        cursor = conn.cursor(
            cursor_factory=RealDictCursor
        )
    else:
        cursor = conn.cursor()

    execute_query(
        cursor,
        """
        SELECT
            results.id,
            users.username,
            exams.title AS exam_title,
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


# ============================================================
# LOGOUT
# ============================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("login"))


# ============================================================
# INITIALIZE DATABASE
# ============================================================

init_db()


# ============================================================
# RUN APPLICATION
# ============================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )