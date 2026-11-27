import base64
import os
import json
from random import SystemRandom

from pathlib import Path
from anthropic import Anthropic
from dotenv import load_dotenv
from database import get_todays_quiz, save_quiz

load_dotenv()

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

PROJECT_DIR = Path(__file__).resolve().parent

QUIZ_GENERATION_MODEL = "claude-haiku-5-5"
QUIZ_PROMPT_VERSION = "v8"
PROMPTS_DIR = PROJECT_DIR / "prompts"
QUIZ_PROMPT_FILE = PROMPTS_DIR / f"quiz_prompt_{QUIZ_PROMPT_VERSION}.txt"
RANDOM = SystemRandom()


def generate_quiz_text(course_name, course_plan_ref):
    encoded_pdf = encode_pdf(course_plan_ref)
    quiz_prompt = QUIZ_PROMPT_FILE.read_text(encoding="utf-8").replace(
        "{course_name}", course_name
    )

    response = client.messages.create(
        model=QUIZ_GENERATION_MODEL,
        max_tokens=10000,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": "application/pdf",
                            "data": encoded_pdf,
                        }
                    },
                    {
                        "type": "text",
                        "text": quiz_prompt,
                    }
                ]
            }
        ]
    )

    return next(
        block.text for block in response.content if block.type == "text"
    )


def generate_quiz_questions(course_name, course_plan_ref):
    response_text = generate_quiz_text(course_name, course_plan_ref)
    quiz_data = json.loads(response_text)

    questions = quiz_data.get("questions")

    if not isinstance(questions, list):
        raise ValueError("Claude's response is missing the questions list")

    if len(questions) != 3:
        raise ValueError("Claude's response must contain exactly 3 questions")

    for question in questions:
        RANDOM.shuffle(question["options"])

    return questions


def generate_and_save_quiz(quiz_date, course_name, course_plan_ref):
    existing_quiz = get_todays_quiz(quiz_date)
    if existing_quiz is not None:
        return existing_quiz["id"]

    questions = generate_quiz_questions(course_name, course_plan_ref)

    return save_quiz(
        quiz_date,
        course_name,
        course_plan_ref,
        questions,
        QUIZ_GENERATION_MODEL,
        QUIZ_PROMPT_VERSION
    )


def get_course_plan_path(course_plan_ref):
    course_plan_dir = Path(
        os.getenv("CYBERBEAR_COURSE_PLAN_DIR", "data/course-plans")
    )

    if not course_plan_dir.is_absolute():
        course_plan_dir = PROJECT_DIR / course_plan_dir

    return course_plan_dir / course_plan_ref


def encode_pdf(course_plan_ref):
    pdf_path = get_course_plan_path(course_plan_ref)
    pdf_bytes = pdf_path.read_bytes()
    return base64.standard_b64encode(pdf_bytes).decode("utf-8")
