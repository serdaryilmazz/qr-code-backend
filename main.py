import json
import uuid
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from database import get_connection, init_db

app = FastAPI(title="Survey API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {"status": "ok", "service": "qr-code-backend"}


@app.get("/health")
def health_check():
    return {"status": "healthy"}


class AnswerItem(BaseModel):
    question_id: int
    answer_text: str


class SubmitSurveyRequest(BaseModel):
    answers: list[AnswerItem]


@app.on_event("startup")
def startup():
    init_db()


def parse_options(options: Optional[str]):
    if options is None:
        return None

    try:
        return json.loads(options)
    except json.JSONDecodeError:
        return None


@app.get("/api/questions")
def get_questions():
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            SELECT id, question_text, question_type, input_type, options, placeholder
            FROM questions
            WHERE is_active = TRUE
            ORDER BY sort_order ASC
            """
        )
        questions = cursor.fetchall()
    finally:
        conn.close()

    return [
        {
            "id": question["id"],
            "question": question["question_text"],
            "type": question["question_type"],
            "inputType": question["input_type"],
            "options": parse_options(question["options"]),
            "placeholder": question["placeholder"],
        }
        for question in questions
    ]


@app.get("/api/answers")
def get_answers():
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            SELECT
                survey_answers.id AS id,
                survey_answers.answer_text AS answer_text,
                survey_answers.session_id AS session_id,
                survey_answers.created_at AS created_at,
                questions.id AS question_id,
                questions.question_text AS question_text,
                questions.question_type AS question_type,
                questions.input_type AS input_type,
                questions.options AS options,
                questions.placeholder AS placeholder
            FROM survey_answers
            INNER JOIN questions ON survey_answers.question_id = questions.id
            ORDER BY survey_answers.created_at DESC, survey_answers.id DESC
            """
        )
        answers = cursor.fetchall()
    finally:
        conn.close()

    return [
        {
            "id": answer["id"],
            "answer": answer["answer_text"],
            "sessionId": answer["session_id"],
            "createdAt": answer["created_at"],
            "question": {
                "id": answer["question_id"],
                "question": answer["question_text"],
                "type": answer["question_type"],
                "inputType": answer["input_type"],
                "options": parse_options(answer["options"]),
                "placeholder": answer["placeholder"],
            },
        }
        for answer in answers
    ]


@app.get("/api/participants/count")
def get_participants_count():
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            SELECT COUNT(DISTINCT session_id) AS total_participants
            FROM survey_answers
            """
        )
        result = cursor.fetchone()
    finally:
        conn.close()

    return {"totalParticipants": result["total_participants"]}


@app.post("/api/submit")
def submit_survey(data: SubmitSurveyRequest):
    if not data.answers:
        raise HTTPException(status_code=400, detail="Cevap listesi bos olamaz.")

    conn = get_connection()
    cursor = conn.cursor()
    session_id = str(uuid.uuid4())

    try:
        for answer in data.answers:
            cursor.execute(
                """
                INSERT INTO survey_answers (question_id, answer_text, session_id)
                VALUES (%s, %s, %s)
                """,
                (answer.question_id, answer.answer_text, session_id),
            )
        conn.commit()
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        conn.close()

    return {
        "message": "Cevaplar basariyla kaydedildi.",
        "count": len(data.answers),
        "sessionId": session_id,
    }
