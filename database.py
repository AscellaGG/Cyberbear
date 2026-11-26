import os
import sqlite3
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent


def get_database_path():
    configured_path = Path(
        os.getenv("CYBERBEAR_DB_PATH", "data/cyberbear-dev.sqlite3")
    )

    if not configured_path.is_absolute():
        configured_path = PROJECT_DIR / configured_path

    configured_path.parent.mkdir(parents=True, exist_ok=True)

    return configured_path


def initialize_database():

    connection = sqlite3.connect(get_database_path())

    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript("""
            CREATE TABLE IF NOT EXISTS quizzes (
                id INTEGER PRIMARY KEY,
                quiz_date TEXT NOT NULL UNIQUE,
                course_name TEXT NOT NULL,
                course_plan_ref TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                generation_model TEXT,
                prompt_version TEXT
            );
            CREATE TABLE IF NOT EXISTS questions (
                id INTEGER PRIMARY KEY,
                quiz_id INTEGER NOT NULL REFERENCES quizzes(id) ON DELETE CASCADE,
                question_number INTEGER NOT NULL CHECK(question_number BETWEEN 1 AND 3),
                question_text TEXT NOT NULL,
                explanation TEXT NOT NULL,
                UNIQUE (quiz_id, question_number)
            );
            CREATE TABLE IF NOT EXISTS question_options (
                id INTEGER PRIMARY KEY,
                question_id INTEGER NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
                option_number INTEGER NOT NULL CHECK (option_number BETWEEN 1 AND 4),
                option_text TEXT NOT NULL,
                is_correct INTEGER NOT NULL CHECK (is_correct IN (0, 1)),
                UNIQUE (question_id, option_number)
            );
            CREATE TABLE IF NOT EXISTS answers (
                id INTEGER PRIMARY KEY,
                question_id INTEGER NOT NULL,
                discord_user_id TEXT NOT NULL,
                selected_option_number INTEGER NOT NULL,
                is_correct INTEGER NOT NULL CHECK (is_correct IN (0,1)),
                xp_awarded INTEGER NOT NULL CHECK (xp_awarded >= 0),
                answered_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (question_id, discord_user_id),
                FOREIGN KEY (question_id, selected_option_number)
                    REFERENCES question_options(question_id, option_number)
            );
        """)
        connection.commit()
    finally:
        connection.close()


def get_options(connection, question_id):
    rows = connection.execute(
        """
        SELECT option_number, option_text, is_correct
        FROM question_options
        WHERE question_id = ?
        ORDER BY option_number
        """,
        (question_id,)
    ).fetchall()

    return [
        {
            "option_number": row[0],
            "option_text": row[1],
            "is_correct": bool(row[2]),
        }
        for row in rows
    ]


def get_questions(connection, quiz_id):
    rows = connection.execute(
        """
        SELECT id, question_number, question_text, explanation
        FROM questions
        WHERE quiz_id = ?
        ORDER BY question_number
        """,
        (quiz_id,)
    ).fetchall()

    return [
        {
            "id": row[0],
            "question_number": row[1],
            "question_text": row[2],
            "explanation": row[3],
            "options": get_options(connection, row[0]),
        }
        for row in rows
    ]


def get_todays_quiz(quiz_date):
    connection = sqlite3.connect(get_database_path())

    try:
        row = connection.execute(
            "SELECT id, quiz_date, course_name, course_plan_ref "
            "FROM quizzes WHERE quiz_date = ?",
            (quiz_date,)
        ).fetchone()

        if row is None:
            return None

        return {
            "id": row[0],
            "quiz_date": row[1],
            "course_name": row[2],
            "course_plan_ref": row[3],
            "questions": get_questions(connection, row[0]),
        }
    finally:
        connection.close()


def insert_quiz_row(connection, quiz_date, course_name, course_plan_ref, generation_model, prompt_version):
    cursor = connection.execute("""
        INSERT INTO quizzes (quiz_date, course_name, course_plan_ref, generation_model, prompt_version)
        VALUES (?, ?, ?, ?, ?)
    """,
                                (quiz_date, course_name, course_plan_ref,
                                 generation_model, prompt_version)
                                )
    return cursor.lastrowid


def insert_question_row(connection, quiz_id, question_number, question_text, explanation):
    cursor = connection.execute("""
        INSERT INTO questions (quiz_id, question_number, question_text, explanation)
        VALUES (?, ?, ?, ?)
    """,
                                (quiz_id, question_number,
                                 question_text, explanation)
                                )
    return cursor.lastrowid


def insert_option_row(connection, question_id, option_number, option_text, is_correct):
    cursor = connection.execute("""
        INSERT INTO question_options (question_id, option_number, option_text, is_correct)
        VALUES (?, ?, ?, ?)
    """,
                                (question_id, option_number,
                                 option_text, is_correct)
                                )
    return cursor.lastrowid


def insert_question_with_options(connection, quiz_id, question_number, question_text, explanation, options):
    correct_count = sum(is_correct for _, is_correct in options)

    if correct_count != 1:
        raise ValueError("A question must have exactly one correct option")

    if len(options) != 4:
        raise ValueError("A question must have exactly 4 options")

    question_id = insert_question_row(
        connection, quiz_id, question_number, question_text, explanation)

    for option_number, (option_text, is_correct) in enumerate(options, start=1):
        insert_option_row(connection, question_id,
                          option_number, option_text, is_correct)

    return question_id


def save_quiz(quiz_date, course_name, course_plan_ref, questions, generation_model, prompt_version):
    if len(questions) != 3:
        raise ValueError("Must have exactly 3 questions")

    connection = sqlite3.connect(get_database_path())

    try:
        connection.execute("PRAGMA foreign_keys = ON")

        quiz_id = insert_quiz_row(
            connection, quiz_date, course_name, course_plan_ref, generation_model, prompt_version)

        for question_number, question in enumerate(questions, start=1):
            insert_question_with_options(
                connection,
                quiz_id,
                question_number,
                question["question_text"],
                question["explanation"],
                question["options"]
            )

        connection.commit()
        return quiz_id
    finally:
        connection.close()
