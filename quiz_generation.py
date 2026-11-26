import base64
import os
import json

from pathlib import Path
from anthropic import Anthropic
from dotenv import load_dotenv
from database import get_todays_quiz, save_quiz

load_dotenv()

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

PROJECT_DIR = Path(__file__).resolve().parent

QUIZ_GENERATION_MODEL = "claude-haiku-5-5"
QUIZ_PROMPT_VERSION = "v3"


def generate_quiz_text(course_name, course_plan_ref):
    encoded_pdf = encode_pdf(course_plan_ref)

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
                        "text": (
                            f"Create exactly 3 multiple-choice questions for '{course_name}', "
                            "using the attached course plan as source material about what the course teaches. "
                            "Test substantive course knowledge and skills: concepts, methods, tools, "
                            "techniques, and practical applications from the course content and learning outcomes. "
                            "Do not quiz the reader about the course plan document or administrative course details. "
                            "Do not ask about grading criteria, assessment methods, schedule, duration, credits, "
                            "or how the course is organized. Prefer questions that ask the learner to understand "
                            "or apply a course concept or skill. Do not invent details that are unsupported by the PDF. "
                            "Each question needs 4 options, "
                            "exactly 1 correct option, and a short explanation. "
                            "Write all question text, answer options, and explanations in Swedish. "
                            "Keep established technical terms in English when that is the clearest usage. "
                            "Return only JSON, with no Markdown fences, in this structure: "
                            '{"questions": ['
                            '{"question_text": "...", "explanation": "...", '
                            '"options": [["option text", false], ["option text", true], '
                            '["option text", false], ["option text", false]]}'
                            ']}'
                        ),
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
