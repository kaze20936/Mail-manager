import sqlite3
from datetime import datetime
from typing import Dict, List, Optional
from config import Config


class Database:
    def __init__(self):
        self.db_path = Config.DB_PATH
        self._init_db()

    def _conn(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        with self._conn() as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS emails (
                    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                    gmail_id            TEXT UNIQUE NOT NULL,
                    thread_id           TEXT NOT NULL DEFAULT '',
                    message_id_header   TEXT DEFAULT '',
                    sender_name         TEXT DEFAULT '',
                    sender_email        TEXT NOT NULL,
                    subject             TEXT DEFAULT '',
                    body                TEXT DEFAULT '',
                    category            TEXT DEFAULT 'その他',
                    received_at         TEXT DEFAULT '',
                    status              TEXT DEFAULT 'pending',
                    reply_text          TEXT DEFAULT '',
                    hidden              INTEGER DEFAULT 0,
                    created_at          TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at          TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            # 既存DBへのカラム追加（マイグレーション）
            try:
                conn.execute('ALTER TABLE emails ADD COLUMN hidden INTEGER DEFAULT 0')
            except Exception:
                pass  # すでに存在する場合はスキップ
            conn.commit()

    def email_exists(self, gmail_id: str) -> bool:
        with self._conn() as conn:
            cur = conn.execute('SELECT 1 FROM emails WHERE gmail_id = ?', (gmail_id,))
            return cur.fetchone() is not None

    def save_email(self, email_data: dict) -> Optional[int]:
        with self._conn() as conn:
            cur = conn.execute('''
                INSERT OR IGNORE INTO emails
                    (gmail_id, thread_id, message_id_header, sender_name,
                     sender_email, subject, body, category, received_at, reply_text)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                email_data['gmail_id'],
                email_data.get('thread_id', ''),
                email_data.get('message_id_header', ''),
                email_data.get('sender_name', ''),
                email_data['sender_email'],
                email_data.get('subject', ''),
                email_data.get('body', ''),
                email_data.get('category', 'その他'),
                email_data.get('received_at', ''),
                email_data.get('reply_text', ''),
            ))
            conn.commit()
            if cur.rowcount > 0:
                return cur.lastrowid
            # 既存レコードのIDを返す
            cur2 = conn.execute('SELECT id FROM emails WHERE gmail_id = ?', (email_data['gmail_id'],))
            row = cur2.fetchone()
            return row[0] if row else None

    def get_emails_by_status(self, status: str, include_hidden: bool = False) -> List[Dict]:
        with self._conn() as conn:
            conn.row_factory = sqlite3.Row
            if include_hidden:
                cur = conn.execute(
                    'SELECT * FROM emails WHERE status = ? ORDER BY received_at DESC',
                    (status,)
                )
            else:
                cur = conn.execute(
                    'SELECT * FROM emails WHERE status = ? AND hidden = 0 ORDER BY received_at DESC',
                    (status,)
                )
            return [dict(row) for row in cur.fetchall()]

    def get_counts(self) -> Dict[str, int]:
        with self._conn() as conn:
            cur = conn.execute('SELECT status, COUNT(*) FROM emails GROUP BY status')
            return {row[0]: row[1] for row in cur.fetchall()}

    def update_status(self, email_id: int, status: str):
        with self._conn() as conn:
            conn.execute(
                'UPDATE emails SET status = ?, updated_at = ? WHERE id = ?',
                (status, datetime.now().isoformat(), email_id)
            )
            conn.commit()

    def update_reply_text(self, email_id: int, reply_text: str):
        with self._conn() as conn:
            conn.execute(
                'UPDATE emails SET reply_text = ?, updated_at = ? WHERE id = ?',
                (reply_text, datetime.now().isoformat(), email_id)
            )
            conn.commit()

    def save_reply_and_set_saved(self, email_id: int, reply_text: str):
        """返信文を保存してステータスを saved に変更"""
        with self._conn() as conn:
            conn.execute(
                'UPDATE emails SET reply_text = ?, status = ?, updated_at = ? WHERE id = ?',
                (reply_text, 'saved', datetime.now().isoformat(), email_id)
            )
            conn.commit()

    def get_email_by_id(self, email_id: int) -> Optional[Dict]:
        with self._conn() as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.execute('SELECT * FROM emails WHERE id = ?', (email_id,))
            row = cur.fetchone()
            return dict(row) if row else None

    def get_senders_summary(self) -> List[Dict]:
        """送信者ごとのメール件数・スキップ件数を返す"""
        with self._conn() as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.execute('''
                SELECT
                    sender_email,
                    sender_name,
                    category,
                    COUNT(*) as mail_count,
                    SUM(CASE WHEN status = 'skipped' THEN 1 ELSE 0 END) as skipped_count,
                    MAX(received_at) as latest_received
                FROM emails
                WHERE sender_email != ''
                GROUP BY sender_email
                ORDER BY mail_count DESC, latest_received DESC
            ''')
            return [dict(row) for row in cur.fetchall()]

    def hide_emails_by_sender(self, sender_email: str):
        """指定送信者のメールをすべて非表示にする（ステータスは変更しない）"""
        with self._conn() as conn:
            conn.execute(
                'UPDATE emails SET hidden = 1, updated_at = ? WHERE sender_email = ?',
                (datetime.now().isoformat(), sender_email)
            )
            conn.commit()

    def show_emails_by_sender(self, sender_email: str):
        """指定送信者のメールをすべて再表示する"""
        with self._conn() as conn:
            conn.execute(
                'UPDATE emails SET hidden = 0, updated_at = ? WHERE sender_email = ?',
                (datetime.now().isoformat(), sender_email)
            )
            conn.commit()

    def skip_emails_by_sender(self, sender_email: str):
        """指定送信者の未対応・保存済みメールをすべてスキップに変更"""
        with self._conn() as conn:
            conn.execute('''
                UPDATE emails
                SET status = 'skipped', updated_at = ?
                WHERE sender_email = ? AND status IN ('pending', 'saved')
            ''', (datetime.now().isoformat(), sender_email))
            conn.commit()

    def get_emails_by_sender(self, sender_email: str) -> List[Dict]:
        """特定の送信者のメール一覧を返す"""
        with self._conn() as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.execute('''
                SELECT id, subject, received_at, status, category
                FROM emails
                WHERE sender_email = ?
                ORDER BY received_at DESC
                LIMIT 20
            ''', (sender_email,))
            return [dict(row) for row in cur.fetchall()]
