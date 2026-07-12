-- Database schema for the application
-- Generated from SQLModel classes

-- Enable pgvector extension (required for RAG similarity search)
CREATE EXTENSION IF NOT EXISTS vector;

-- Create user table
CREATE TABLE IF NOT EXISTS "user" (
    id SERIAL PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    hashed_password TEXT NOT NULL,
    is_admin BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Create session table
CREATE TABLE IF NOT EXISTS session (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    FOREIGN KEY (user_id) REFERENCES "user"(id) ON DELETE CASCADE
);

-- Create thread table
CREATE TABLE IF NOT EXISTS thread (
    id TEXT PRIMARY KEY,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Create indexes for frequently queried columns
CREATE INDEX IF NOT EXISTS idx_user_email ON "user"(email);
CREATE INDEX IF NOT EXISTS idx_session_user_id ON session(user_id);

-- Migration: add is_admin to existing user tables (safe to run on existing DBs)
ALTER TABLE "user" ADD COLUMN IF NOT EXISTS is_admin BOOLEAN NOT NULL DEFAULT FALSE;
