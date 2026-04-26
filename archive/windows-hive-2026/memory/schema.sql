-- LLMS Memory Schema
-- Applied once on first run, idempotent (IF NOT EXISTS)

CREATE TABLE IF NOT EXISTS profile (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    root_path TEXT,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_accessed TIMESTAMP
);

CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER REFERENCES projects(id),
    source_path TEXT,
    doc_type TEXT CHECK(doc_type IN ('pdf', 'text', 'markdown', 'code', 'image', 'url')),
    title TEXT,
    page_count INTEGER,
    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    content_type TEXT CHECK(content_type IN ('text', 'ocr', 'vision_description', 'summary', 'code')),
    page_number INTEGER,
    embedding BLOB,
    token_count INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER REFERENCES projects(id),
    category TEXT CHECK(category IN ('knowledge', 'fact', 'preference', 'concept', 'summary', 'instruction')),
    content TEXT NOT NULL,
    importance REAL DEFAULT 0.5 CHECK(importance >= 0.0 AND importance <= 1.0),
    access_count INTEGER DEFAULT 0,
    embedding BLOB,
    source_document_id INTEGER REFERENCES documents(id),
    summary_type TEXT,
    tags TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_accessed TIMESTAMP
);

CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT,
    user_message TEXT NOT NULL,
    bot_response TEXT NOT NULL,
    model_used TEXT,
    route_decision TEXT,
    memory_used TEXT,
    tools_used TEXT,
    response_time REAL,
    feedback TEXT CHECK(feedback IN ('correct', 'wrong', 'partial', NULL)),
    project_id INTEGER REFERENCES projects(id),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS query_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query TEXT NOT NULL,
    routed_to TEXT NOT NULL,
    reasoning TEXT,
    project_id INTEGER REFERENCES projects(id),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_chunks_document ON chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_memories_category ON memories(category);
CREATE INDEX IF NOT EXISTS idx_memories_importance ON memories(importance DESC);
CREATE INDEX IF NOT EXISTS idx_memories_project ON memories(project_id);
CREATE INDEX IF NOT EXISTS idx_conversations_session ON conversations(session_id);
CREATE INDEX IF NOT EXISTS idx_conversations_timestamp ON conversations(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_query_log_timestamp ON query_log(timestamp DESC);
