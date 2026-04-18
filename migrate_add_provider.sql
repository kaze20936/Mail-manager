-- gmail_accounts テーブルにプロバイダー・IMAP/SMTP 設定カラムを追加するにゃ
-- Supabase の SQL Editor で実行してにゃ

ALTER TABLE gmail_accounts
  ADD COLUMN IF NOT EXISTS provider   TEXT    DEFAULT 'gmail',
  ADD COLUMN IF NOT EXISTS imap_host  TEXT,
  ADD COLUMN IF NOT EXISTS imap_port  INTEGER DEFAULT 993,
  ADD COLUMN IF NOT EXISTS smtp_host  TEXT,
  ADD COLUMN IF NOT EXISTS smtp_port  INTEGER DEFAULT 587,
  ADD COLUMN IF NOT EXISTS username   TEXT,
  ADD COLUMN IF NOT EXISTS password   TEXT;

-- 既存レコードを gmail プロバイダーに設定にゃ
UPDATE gmail_accounts SET provider = 'gmail' WHERE provider IS NULL;
