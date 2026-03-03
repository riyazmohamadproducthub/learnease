from __future__ import annotations

import hashlib
import json
import os
import random
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, render_template, request

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "learnease.db"

app = Flask(__name__)


SUPPORTED_METHODS = {
    "story": "Story-based learning",
    "step": "Step-by-step scaffolding",
    "feynman": "Feynman-style simplification",
    "practice": "Practice-first learning",
}


SUPPORTED_VISUALS = {
    "flow": "Flowchart",
    "timeline": "Timeline",
    "mindmap": "Mind map",
    "comparison": "Comparison table",
}


LANGUAGE_OPENERS = {
    "english": "Here is your lesson",
    "spanish": "Aquí está tu lección",
    "french": "Voici votre leçon",
    "hindi": "यह आपकी सीख है",
}


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                ip_hash TEXT NOT NULL,
                preferred_methodology TEXT,
                preferred_language TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS learning_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                topic TEXT NOT NULL,
                methodology TEXT NOT NULL,
                language TEXT NOT NULL,
                visual_style TEXT NOT NULL,
                lesson_json TEXT NOT NULL,
                quiz_json TEXT NOT NULL,
                score REAL,
                feedback TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
            """
        )


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def detect_ip() -> str:
    forwarded_for = request.headers.get("X-Forwarded-For", "")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.remote_addr or "0.0.0.0"


def get_user_id() -> str:
    raw = f"{detect_ip()}::{request.headers.get('User-Agent', 'unknown')}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return digest[:24]


def upsert_user(user_id: str, methodology: str, language: str) -> None:
    timestamp = now_iso()
    ip_hash = hashlib.sha256(detect_ip().encode("utf-8")).hexdigest()
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO users (id, ip_hash, preferred_methodology, preferred_language, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                preferred_methodology = excluded.preferred_methodology,
                preferred_language = excluded.preferred_language,
                updated_at = excluded.updated_at;
            """,
            (user_id, ip_hash, methodology, language, timestamp, timestamp),
        )


def generate_lesson(topic: str, methodology: str, language: str, visual: str) -> dict[str, Any]:
    method_label = SUPPORTED_METHODS.get(methodology, methodology)
    visual_label = SUPPORTED_VISUALS.get(visual, visual)
    opener = LANGUAGE_OPENERS.get(language.lower(), f"Lesson in {language}")

    key_points = [
        f"Define {topic} in simple terms.",
        f"Identify where {topic} is used in real life.",
        f"Break {topic} into small, learnable parts.",
        f"Apply {topic} through a quick practice exercise.",
    ]

    narrative = [
        f"{opener}: {topic} is easier when we link new ideas to familiar examples.",
        f"Method selected: {method_label}. We'll structure learning with clear micro-goals.",
        f"Visual mode selected: {visual_label}. Use the visual map to remember flow and relationships.",
        "Reflection: explain the idea back in your own words to check understanding.",
    ]

    infographic = {
        "title": f"{topic} at a glance",
        "nodes": [
            {"label": "Concept", "value": topic},
            {"label": "Method", "value": method_label},
            {"label": "Visual", "value": visual_label},
            {"label": "Outcome", "value": "Understand, apply, reflect"},
        ],
    }

    return {
        "title": f"Learning module: {topic}",
        "language": language,
        "methodology": method_label,
        "visual_style": visual_label,
        "sections": narrative,
        "key_points": key_points,
        "infographic": infographic,
    }


def generate_quiz(topic: str) -> list[dict[str, Any]]:
    distractors = [
        "Ignoring real-world examples",
        "Memorizing without understanding",
        "Avoiding reflection",
        "Skipping practice",
    ]

    questions = [
        {
            "question": f"What is the first step when learning {topic}?",
            "options": [
                f"Define {topic} in simple words",
                distractors[0],
                distractors[1],
                distractors[2],
            ],
            "answer": 0,
        },
        {
            "question": "Which action best improves retention?",
            "options": [
                "Explain the topic in your own words",
                "Read once and move on",
                "Skip visuals",
                "Only watch videos",
            ],
            "answer": 0,
        },
        {
            "question": "Why use a visual learning aid?",
            "options": [
                "To show concept relationships quickly",
                "To replace all practice",
                "To avoid asking questions",
                "To make lessons longer",
            ],
            "answer": 0,
        },
    ]

    for question in questions:
        combined = list(enumerate(question["options"]))
        random.shuffle(combined)
        question["options"] = [option for _, option in combined]
        question["answer"] = [idx for idx, (old_i, _) in enumerate(combined) if old_i == question["answer"]][0]

    return questions


init_db()


@app.route("/")
def index() -> str:
    return render_template("index.html")


@app.post("/api/generate")
def generate() -> Any:
    payload = request.get_json(force=True)
    topic = (payload.get("topic") or "").strip()
    methodology = (payload.get("methodology") or "step").strip().lower()
    language = (payload.get("language") or "English").strip()
    visual = (payload.get("visual") or "flow").strip().lower()

    if not topic:
        return jsonify({"error": "Please provide a keyword or topic."}), 400

    user_id = get_user_id()
    upsert_user(user_id, methodology, language)
    lesson = generate_lesson(topic, methodology, language, visual)
    quiz = generate_quiz(topic)

    with get_db() as conn:
        cursor = conn.execute(
            """
            INSERT INTO learning_sessions (
                user_id, topic, methodology, language, visual_style,
                lesson_json, quiz_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                topic,
                methodology,
                language,
                visual,
                json.dumps(lesson),
                json.dumps(quiz),
                now_iso(),
            ),
        )

    return jsonify({"session_id": cursor.lastrowid, "lesson": lesson, "quiz": quiz})


@app.post("/api/submit-quiz")
def submit_quiz() -> Any:
    payload = request.get_json(force=True)
    session_id = payload.get("session_id")
    answers = payload.get("answers", [])

    with get_db() as conn:
        row = conn.execute("SELECT quiz_json FROM learning_sessions WHERE id = ?", (session_id,)).fetchone()
        if row is None:
            return jsonify({"error": "Session not found."}), 404

        quiz = json.loads(row["quiz_json"])
        correct = sum(1 for i, q in enumerate(quiz) if i < len(answers) and answers[i] == q["answer"])
        score = round((correct / len(quiz)) * 100, 2)
        conn.execute("UPDATE learning_sessions SET score = ? WHERE id = ?", (score, session_id))

    return jsonify(
        {
            "score": score,
            "message": "Great progress!" if score >= 70 else "Good effort—review the key points and retry.",
        }
    )


@app.post("/api/feedback")
def submit_feedback() -> Any:
    payload = request.get_json(force=True)
    session_id = payload.get("session_id")
    feedback = (payload.get("feedback") or "").strip()

    with get_db() as conn:
        updated = conn.execute(
            "UPDATE learning_sessions SET feedback = ? WHERE id = ?",
            (feedback, session_id),
        )

    if updated.rowcount == 0:
        return jsonify({"error": "Session not found."}), 404
    return jsonify({"status": "saved"})


@app.get("/api/history")
def history() -> Any:
    user_id = get_user_id()
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT id, topic, methodology, language, visual_style, score, feedback, created_at
            FROM learning_sessions
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT 10
            """,
            (user_id,),
        ).fetchall()

    return jsonify([dict(row) for row in rows])


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)), debug=True)
