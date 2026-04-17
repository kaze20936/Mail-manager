-- ============================================================
-- Mail Manager — Supabase テーブル定義
-- Supabase の SQL Editor にこの内容を貼り付けて実行してにゃ
-- ============================================================

-- ── メールテーブル
CREATE TABLE IF NOT EXISTS emails (
    id                  BIGSERIAL PRIMARY KEY,
    gmail_id            TEXT UNIQUE NOT NULL,
    thread_id           TEXT NOT NULL DEFAULT '',
    message_id_header   TEXT DEFAULT '',
    sender_name         TEXT DEFAULT '',
    sender_email        TEXT NOT NULL DEFAULT '',
    subject             TEXT DEFAULT '',
    body                TEXT DEFAULT '',
    category            TEXT DEFAULT 'その他',
    received_at         TEXT DEFAULT '',
    status              TEXT DEFAULT 'pending',
    reply_text          TEXT DEFAULT '',
    hidden              BOOLEAN DEFAULT FALSE,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

-- 検索高速化のインデックス
CREATE INDEX IF NOT EXISTS idx_emails_status       ON emails(status);
CREATE INDEX IF NOT EXISTS idx_emails_gmail_id     ON emails(gmail_id);
CREATE INDEX IF NOT EXISTS idx_emails_sender_email ON emails(sender_email);
CREATE INDEX IF NOT EXISTS idx_emails_received_at  ON emails(received_at DESC);

-- RLS（Row Level Security）を無効化 ─ サーバーサイド専用アプリのため
ALTER TABLE emails DISABLE ROW LEVEL SECURITY;
