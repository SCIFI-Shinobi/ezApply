-- Run this once against your Supabase Postgres DB.

CREATE TABLE IF NOT EXISTS profile (
    id SERIAL PRIMARY KEY,
    raw_resume_text TEXT,
    extracted_json JSONB,          -- structured skills/education/experience/target_roles
    embedding_json TEXT,           -- profile embedding vector, stored as JSON array of floats
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS channels (
    id SERIAL PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,     -- e.g. 'ethiojobs' (no @)
    kind TEXT NOT NULL CHECK (kind IN ('job', 'scholarship')),
    added_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS posts (
    id SERIAL PRIMARY KEY,
    channel_id INT REFERENCES channels(id),
    message_id BIGINT,
    text TEXT,
    embedding_json TEXT,
    posted_at TIMESTAMPTZ,
    processed BOOLEAN DEFAULT FALSE,
    UNIQUE(channel_id, message_id)
);

CREATE TABLE IF NOT EXISTS matches (
    id SERIAL PRIMARY KEY,
    post_id INT REFERENCES posts(id),
    score FLOAT,
    notified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT now()
);
