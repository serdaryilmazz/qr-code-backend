from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from database import get_connection, init_db

app = FastAPI(title="Survey API")

# CORS - Frontend'in backend'e istek atabilmesi için
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Şemalar ---

class AnswerItem(BaseModel):
    question_id: int
    answer_text: str


class SubmitSurveyRequest(BaseModel):
    answers: list[AnswerItem]


# --- Uygulama başlatıldığında DB'yi oluştur ---

@app.on_event("startup")
def startup():
    init_db()


# --- Endpoint ---

@app.post("/api/submit")
def submit_survey(data: SubmitSurveyRequest):
    """Anket cevaplarını veritabanına kaydeder."""
    if not data.answers:
        raise HTTPException(status_code=400, detail="Cevap listesi boş olamaz.")

    conn = get_connection()
    cursor = conn.cursor()

    try:
        for answer in data.answers:
            cursor.execute(
                "INSERT INTO survey_answers (question_id, answer_text) VALUES (?, ?)",
                (answer.question_id, answer.answer_text),
            )
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

    return {"message": "Cevaplar başarıyla kaydedildi.", "count": len(data.answers)}
