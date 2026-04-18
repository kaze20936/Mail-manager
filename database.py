import logging
from datetime import datetime
from typing import Dict, List, Optional

from supabase import create_client, Client
from config import Config

logger = logging.getLogger(__name__)


class Database:
    def __init__(self):
        if not Config.SUPABASE_URL or not Config.SUPABASE_KEY:
            raise ValueError(
                'SUPABASE_URL と SUPABASE_KEY が設定されていないにゃ！\n'
                '⚙️設定タブ → 🔧初期設定 で設定してにゃ。'
            )
        self.client: Client = create_client(Config.SUPABASE_URL, Config.SUPABASE_KEY)

    # ─────────────────────────────────────────────
    # メール保存・取得
    # ─────────────────────────────────────────────

    def email_exists(self, gmail_id: str) -> bool:
        r = self.client.table('emails').select('id').eq('gmail_id', gmail_id).execute()
        return len(r.data) > 0

    def save_email(self, email_data: dict) -> Optional[int]:
        # 既存レコードがあれば ID だけ返す
        r = self.client.table('emails').select('id').eq('gmail_id', email_data['gmail_id']).execute()
        if r.data:
            return r.data[0]['id']

        insert_data = {
            'gmail_id':          email_data['gmail_id'],
            'thread_id':         email_data.get('thread_id', ''),
            'message_id_header': email_data.get('message_id_header', ''),
            'sender_name':       email_data.get('sender_name', ''),
            'sender_email':      email_data['sender_email'],
            'subject':           email_data.get('subject', ''),
            'body':              email_data.get('body', ''),
            'category':          email_data.get('category', 'その他'),
            'received_at':       email_data.get('received_at', ''),
            'reply_text':        email_data.get('reply_text', ''),
            'status':            'pending',
            'hidden':            False,
        }
        r = self.client.table('emails').insert(insert_data).execute()
        return r.data[0]['id'] if r.data else None

    def get_emails_by_status(self, status: str, include_hidden: bool = False) -> List[Dict]:
        q = self.client.table('emails').select('*').eq('status', status)
        if not include_hidden:
            q = q.eq('hidden', False)
        r = q.order('received_at', desc=True).execute()
        return r.data or []

    def get_counts(self) -> Dict[str, int]:
        result = {}
        for status in ['pending', 'saved', 'sent', 'skipped']:
            r = (self.client.table('emails')
                 .select('id', count='exact')
                 .eq('status', status)
                 .limit(0)
                 .execute())
            result[status] = r.count or 0
        return result

    def get_email_by_id(self, email_id: int) -> Optional[Dict]:
        r = self.client.table('emails').select('*').eq('id', email_id).execute()
        return r.data[0] if r.data else None

    # ─────────────────────────────────────────────
    # ステータス・返信文の更新
    # ─────────────────────────────────────────────

    def update_status(self, email_id: int, status: str):
        self.client.table('emails').update({
            'status':     status,
            'updated_at': datetime.now().isoformat(),
        }).eq('id', email_id).execute()

    def update_reply_text(self, email_id: int, reply_text: str):
        self.client.table('emails').update({
            'reply_text': reply_text,
            'updated_at': datetime.now().isoformat(),
        }).eq('id', email_id).execute()

    def save_reply_and_set_saved(self, email_id: int, reply_text: str):
        """返信文を保存してステータスを saved に変更"""
        self.client.table('emails').update({
            'reply_text': reply_text,
            'status':     'saved',
            'updated_at': datetime.now().isoformat(),
        }).eq('id', email_id).execute()

    # ─────────────────────────────────────────────
    # 送信者管理
    # ─────────────────────────────────────────────

    def get_senders_summary(self) -> List[Dict]:
        """送信者ごとのメール件数・スキップ件数を返す"""
        r = (self.client.table('emails')
             .select('sender_email,sender_name,category,status,received_at')
             .execute())
        emails = r.data or []

        summary: Dict[str, Dict] = {}
        for e in emails:
            addr = e.get('sender_email', '')
            if not addr:
                continue
            if addr not in summary:
                summary[addr] = {
                    'sender_email':   addr,
                    'sender_name':    e.get('sender_name', ''),
                    'category':       e.get('category', 'その他'),
                    'mail_count':     0,
                    'skipped_count':  0,
                    'latest_received': '',
                }
            summary[addr]['mail_count'] += 1
            if e.get('status') == 'skipped':
                summary[addr]['skipped_count'] += 1
            recv = e.get('received_at', '') or ''
            if recv > summary[addr]['latest_received']:
                summary[addr]['latest_received'] = recv

        return sorted(summary.values(),
                      key=lambda x: (x['mail_count'], x['latest_received']),
                      reverse=True)

    def get_emails_by_sender(self, sender_email: str) -> List[Dict]:
        """特定送信者のメール一覧（最新20件）"""
        r = (self.client.table('emails')
             .select('id,subject,received_at,status,category')
             .eq('sender_email', sender_email)
             .order('received_at', desc=True)
             .limit(20)
             .execute())
        return r.data or []

    def hide_emails_by_sender(self, sender_email: str):
        """指定送信者のメールをすべて非表示にする"""
        self.client.table('emails').update({
            'hidden':     True,
            'updated_at': datetime.now().isoformat(),
        }).eq('sender_email', sender_email).execute()

    def show_emails_by_sender(self, sender_email: str):
        """指定送信者のメールをすべて再表示する"""
        self.client.table('emails').update({
            'hidden':     False,
            'updated_at': datetime.now().isoformat(),
        }).eq('sender_email', sender_email).execute()

    def skip_emails_by_sender(self, sender_email: str):
        """指定送信者の未対応・保存済みメールをすべてスキップに変更"""
        self.client.table('emails').update({
            'status':     'skipped',
            'updated_at': datetime.now().isoformat(),
        }).eq('sender_email', sender_email).in_('status', ['pending', 'saved']).execute()

    # ─────────────────────────────────────────────
    # Gmailアカウント管理
    # ─────────────────────────────────────────────

    def get_gmail_accounts(self) -> List[Dict]:
        """登録済みGmailアカウント一覧を返すにゃ"""
        r = self.client.table('gmail_accounts').select('*').order('created_at').execute()
        return r.data or []

    def get_active_account(self) -> Optional[Dict]:
        """アクティブなアカウントを返すにゃ"""
        r = self.client.table('gmail_accounts').select('*').eq('is_active', True).limit(1).execute()
        return r.data[0] if r.data else None

    def upsert_gmail_account(self, email: str, token_json: str):
        """Gmailアカウントを登録・更新するにゃ（既存なら token_json だけ更新）"""
        r = self.client.table('gmail_accounts').select('id').eq('email', email).execute()
        if r.data:
            self.client.table('gmail_accounts').update({
                'token_json': token_json,
                'provider':   'gmail',
            }).eq('email', email).execute()
        else:
            self.client.table('gmail_accounts').insert({
                'email':      email,
                'token_json': token_json,
                'provider':   'gmail',
                'is_active':  False,
            }).execute()

    def upsert_imap_account(self, email: str, password: str,
                            imap_host: str, imap_port: int,
                            smtp_host: str, smtp_port: int,
                            provider: str = 'imap'):
        """IMAPアカウントを登録・更新するにゃ"""
        r = self.client.table('gmail_accounts').select('id').eq('email', email).execute()
        if r.data:
            self.client.table('gmail_accounts').update({
                'password':  password,
                'imap_host': imap_host,
                'imap_port': imap_port,
                'smtp_host': smtp_host,
                'smtp_port': smtp_port,
                'provider':  provider,
            }).eq('email', email).execute()
        else:
            self.client.table('gmail_accounts').insert({
                'email':     email,
                'token_json': '',
                'password':  password,
                'imap_host': imap_host,
                'imap_port': imap_port,
                'smtp_host': smtp_host,
                'smtp_port': smtp_port,
                'provider':  provider,
                'is_active': False,
            }).execute()

    def set_active_account(self, email: str):
        """指定アカウントをアクティブにして他を非アクティブにするにゃ（空文字で全解除）"""
        self.client.table('gmail_accounts').update({'is_active': False}).neq('email', '').execute()
        if email:
            self.client.table('gmail_accounts').update({'is_active': True}).eq('email', email).execute()

    def delete_gmail_account(self, email: str):
        """アカウントを削除するにゃ"""
        self.client.table('gmail_accounts').delete().eq('email', email).execute()
