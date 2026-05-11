import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL environment variable is not set!")


def get_connection():
    """PostgreSQL bağlantısı döndürür."""
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    return conn


def init_db():
    """Veritabanını ve tabloları oluşturur, soruları ekler."""
    conn = get_connection()
    cursor = conn.cursor()

    # Sorular tablosu
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS questions (
            id SERIAL PRIMARY KEY,
            question_text TEXT NOT NULL,
            question_type TEXT NOT NULL,
            input_type TEXT,
            options TEXT,
            placeholder TEXT,
            sort_order INTEGER NOT NULL DEFAULT 0,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Cevaplar tablosu
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS survey_answers (
            id SERIAL PRIMARY KEY,
            question_id INTEGER NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
            answer_text TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Eğer sorular tablosu boşsa, varsayılan soruları ekle
    cursor.execute("SELECT COUNT(*) AS count FROM questions")
    if cursor.fetchone()["count"] == 0:
        questions = [
            ("Kaç yaşındasınız?", "input", "number", None, "Yaşınızı giriniz...", 1),
            ("Cinsiyetiniz nedir?", "select", None, '["Erkek", "Kadın"]', None, 2),
            ("Bölümünüz nedir?", "select", None, '["Bilgisayar Mühendisliği", "Yazılım Mühendisliği", "Elektrik Elektronik Mühendisliği", "Diğer"]', None, 3),
            ("Hangi alanda ilgileniyorsunuz?", "select", None, '["Yapay Zeka / Makine Öğrenmesi", "Web / Mobil Geliştirme", "Siber Güvenlik", "Veri Bilimi", "Diğer"]', None, 4),
        ]
        cursor.executemany(
            "INSERT INTO questions (question_text, question_type, input_type, options, placeholder, sort_order) VALUES (%s, %s, %s, %s, %s, %s)",
            questions,
        )

    conn.commit()
    cursor.close()
    conn.close()
