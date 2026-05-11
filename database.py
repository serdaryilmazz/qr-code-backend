import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "survey.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Veritabanını ve tabloları oluşturur, soruları ekler."""
    conn = get_connection()
    cursor = conn.cursor()

    # Sorular tablosu
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question_text TEXT NOT NULL,
            question_type TEXT NOT NULL,
            input_type TEXT,
            options TEXT,
            placeholder TEXT,
            sort_order INTEGER NOT NULL DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Cevaplar tablosu
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS survey_answers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question_id INTEGER NOT NULL,
            answer_text TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (question_id) REFERENCES questions(id) ON DELETE CASCADE
        )
    """)

    # Eğer sorular tablosu boşsa, varsayılan soruları ekle
    cursor.execute("SELECT COUNT(*) FROM questions")
    if cursor.fetchone()[0] == 0:
        questions = [
            ("Kaç yaşındasınız?", "input", "number", None, "Yaşınızı giriniz...", 1),
            ("Cinsiyetiniz nedir?", "select", None, '["Erkek", "Kadın"]', None, 2),
            ("Bölümünüz nedir?", "select", None, '["Bilgisayar Mühendisliği", "Yazılım Mühendisliği", "Elektrik Elektronik Mühendisliği", "Diğer"]', None, 3),
            ("Hangi alanda ilgileniyorsunuz?", "select", None, '["Yapay Zeka / Makine Öğrenmesi", "Web / Mobil Geliştirme", "Siber Güvenlik", "Veri Bilimi", "Diğer"]', None, 4),
        ]
        cursor.executemany(
            "INSERT INTO questions (question_text, question_type, input_type, options, placeholder, sort_order) VALUES (?, ?, ?, ?, ?, ?)",
            questions,
        )

    conn.commit()
    conn.close()
