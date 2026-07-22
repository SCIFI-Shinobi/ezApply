import os
import json
import psycopg2
from psycopg2.extras import RealDictCursor

DATABASE_URL = os.environ.get("DATABASE_URL")


def get_conn():
    if not DATABASE_URL:
        raise RuntimeError(
            "DATABASE_URL environment variable is not set! "
            "Please add your Supabase Postgres connection string to your Render environment variables."
        )
    return psycopg2.connect(DATABASE_URL)


def init_db():
    if not DATABASE_URL:
        return
    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    with open(schema_path, "r", encoding="utf-8") as f:
        schema = f.read()
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(schema)
        conn.commit()


def save_profile(raw_text: str, extracted_json: dict, embedding: list):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO profile (raw_resume_text, extracted_json, embedding_json, updated_at)
            VALUES (%s, %s, %s, now())
            """,
            (raw_text, json.dumps(extracted_json), json.dumps(embedding)),
        )
        conn.commit()


def update_latest_profile(extracted_json: dict, embedding: list):
    with get_conn() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT id, raw_resume_text FROM profile ORDER BY id DESC LIMIT 1")
        row = cur.fetchone()
        if not row:
            cur.execute(
                """
                INSERT INTO profile (raw_resume_text, extracted_json, embedding_json, updated_at)
                VALUES (%s, %s, %s, now())
                """,
                ("Manual profile created from bot commands.", json.dumps(extracted_json), json.dumps(embedding)),
            )
        else:
            cur.execute(
                """
                UPDATE profile
                SET extracted_json = %s, embedding_json = %s, updated_at = now()
                WHERE id = %s
                """,
                (json.dumps(extracted_json), json.dumps(embedding), row["id"]),
            )
        conn.commit()


def get_latest_profile():
    with get_conn() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT * FROM profile ORDER BY id DESC LIMIT 1")
        return cur.fetchone()


def add_channel(username: str, kind: str):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO channels (username, kind) VALUES (%s, %s)
            ON CONFLICT (username) DO NOTHING
            """,
            (username, kind),
        )
        conn.commit()


def ensure_channels(channels: list[dict]):
    with get_conn() as conn, conn.cursor() as cur:
        for channel in channels:
            cur.execute(
                """
                INSERT INTO channels (username, kind) VALUES (%s, %s)
                ON CONFLICT (username) DO UPDATE SET kind = EXCLUDED.kind
                """,
                (channel["username"], channel["kind"]),
            )
        conn.commit()


def list_channels():
    with get_conn() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT * FROM channels ORDER BY kind, username")
        return cur.fetchall()


def save_post(channel_id: int, message_id: int, text: str, embedding: list, posted_at):
    with get_conn() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            INSERT INTO posts (channel_id, message_id, text, embedding_json, posted_at)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (channel_id, message_id) DO NOTHING
            RETURNING id
            """,
            (channel_id, message_id, text, json.dumps(embedding), posted_at),
        )
        row = cur.fetchone()
        conn.commit()
        return row["id"] if row else None


def save_match(post_id: int, score: float):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO matches (post_id, score) VALUES (%s, %s)",
            (post_id, score),
        )
        conn.commit()


def mark_notified(post_id: int):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE matches SET notified = TRUE WHERE post_id = %s",
            (post_id,),
        )
        conn.commit()
