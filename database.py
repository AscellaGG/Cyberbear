import os
import sqlite3
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent

def initialize_database():
    configured_path = Path(
        os.getenv("CYBERBEAR_DB_PATH", "data/cyberbear-dev.sqlite3")
    )

    if not configured_path.is_absolute():
        configured_path = PROJECT_DIR / configured_path

    configured_path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(configured_path)

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
                question_number INTEGER NOT NULL CHECK(question_number BETWEEN 1 AND 5),
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