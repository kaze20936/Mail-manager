"""
imap_client.py — IMAP/SMTP メールクライアント（Gmail以外のプロバイダー用）

対応プロバイダー例:
  Outlook / Hotmail / Microsoft 365
  Yahoo Mail
  iCloud Mail
  その他 IMAP 対応プロバイダー全般
"""
import base64
import imaplib
import logging
import mimetypes
import smtplib
import ssl
from datetime import datetime, timedelta
from email import message_from_bytes
from email.header import decode_header
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email import encoders
from email.utils import parseaddr
from typing import Optional

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# ── よく使うプロバイダーのデフォルト設定にゃ
PROVIDER_PRESETS = {
    'ocn': {
        'label':     'OCN メール (NTT)',
        'imap_host': 'imap.ocn.ne.jp',
        'imap_port': 993,
        'smtp_host': 'smtp.ocn.ne.jp',
        'smtp_port': 465,
    },
    'outlook': {
        'label':     'Outlook / Hotmail / Microsoft 365',
        'imap_host': 'imap-mail.outlook.com',
        'imap_port': 993,
        'smtp_host': 'smtp-mail.outlook.com',
        'smtp_port': 587,
    },
    'yahoo': {
        'label':     'Yahoo! Mail',
        'imap_host': 'imap.mail.yahoo.com',
        'imap_port': 993,
        'smtp_host': 'smtp.mail.yahoo.com',
        'smtp_port': 465,
    },
    'icloud': {
        'label':     'iCloud Mail',
        'imap_host': 'imap.mail.me.com',
        'imap_port': 993,
        'smtp_host': 'smtp.mail.me.com',
        'smtp_port': 587,
    },
    'custom': {
        'label':     'その他（カスタム設定）',
        'imap_host': '',
        'imap_port': 993,
        'smtp_host': '',
        'smtp_port': 587,
    },
}


def _decode_str(value: str) -> str:
    """メールヘッダーをデコードするにゃ"""
    parts = decode_header(value or '')
    result = []
    for part, enc in parts:
        if isinstance(part, bytes):
            result.append(part.decode(enc or 'utf-8', errors='replace'))
        else:
            result.append(str(part))
    return ''.join(result)


def _extract_body_from_msg(msg) -> str:
    """メールオブジェクトから本文を抽出するにゃ"""
    body = ''
    if msg.is_multipart():
        # text/plain を優先にゃ
        for part in msg.walk():
            if part.get_content_type() == 'text/plain':
                charset = part.get_content_charset() or 'utf-8'
                try:
                    body = part.get_payload(decode=True).decode(charset, errors='replace')
                    break
                except Exception:
                    continue
        # text/plain がなければ text/html を使うにゃ
        if not body:
            for part in msg.walk():
                if part.get_content_type() == 'text/html':
                    charset = part.get_content_charset() or 'utf-8'
                    try:
                        html = part.get_payload(decode=True).decode(charset, errors='replace')
                        body = BeautifulSoup(html, 'html.parser').get_text('\n').strip()
                        break
                    except Exception:
                        continue
    else:
        charset = msg.get_content_charset() or 'utf-8'
        payload = msg.get_payload(decode=True)
        if payload:
            content = payload.decode(charset, errors='replace')
            if msg.get_content_type() == 'text/html':
                body = BeautifulSoup(content, 'html.parser').get_text('\n').strip()
            else:
                body = content
    return body


class ImapClient:
    """IMAP/SMTP メールクライアントにゃ"""

    def __init__(self, username: str, password: str,
                 imap_host: str, imap_port: int = 993,
                 smtp_host: str = '', smtp_port: int = 587):
        self.username  = username
        self.password  = password
        self.imap_host = imap_host
        self.imap_port = imap_port
        self.smtp_host = smtp_host or imap_host  # SMTP未指定ならIMAPホストを流用にゃ
        self.smtp_port = smtp_port
        # 接続テスト
        self._test_connection()

    def _test_connection(self):
        """IMAP接続テストにゃ（初期化時に一度だけ）"""
        try:
            ctx = ssl.create_default_context()
            with imaplib.IMAP4_SSL(self.imap_host, self.imap_port, ssl_context=ctx) as imap:
                imap.login(self.username, self.password)
            logger.info(f'IMAP接続成功にゃ: {self.imap_host}')
        except imaplib.IMAP4.error as e:
            raise ValueError(
                f'IMAPログイン失敗にゃ: {e}\n'
                'ユーザー名・パスワードが正しいか確認してにゃ。\n'
                'Gmail・Yahoo は「アプリパスワード」が必要なにゃ。'
            )

    def get_account_email(self) -> str:
        """接続中のメールアドレスを返すにゃ（=ユーザー名）"""
        return self.username

    # ─────────────────────────────────────────────
    # メール取得
    # ─────────────────────────────────────────────

    def fetch_new_emails(self, max_results: int = 50, query: str = None) -> list:
        """未読メールを取得するにゃ（IMAP）"""
        emails = []
        ctx = ssl.create_default_context()

        try:
            with imaplib.IMAP4_SSL(self.imap_host, self.imap_port, ssl_context=ctx) as imap:
                imap.login(self.username, self.password)
                imap.select('INBOX', readonly=True)

                # 検索クエリを IMAPクライテリアに変換にゃ
                search_criteria = self._build_search_criteria(query)
                _, message_ids = imap.search(None, search_criteria)

                ids = message_ids[0].split()
                # 新着順（末尾が新しい）にするにゃ
                ids = list(reversed(ids))[:max_results]

                logger.info(f'IMAP から {len(ids)} 件取得にゃ')

                for uid in ids:
                    try:
                        _, data = imap.fetch(uid, '(RFC822)')
                        raw = data[0][1]
                        msg = message_from_bytes(raw)

                        sender_raw  = msg.get('From', '')
                        sender_name, sender_email = parseaddr(sender_raw)
                        sender_name = _decode_str(sender_name) if sender_name else sender_email

                        subject  = _decode_str(msg.get('Subject', '(件名なし)'))
                        msg_id   = msg.get('Message-ID', '')
                        thread_id = msg.get('In-Reply-To', '') or msg_id

                        body = _extract_body_from_msg(msg)
                        if not body.strip():
                            logger.info(f'空メールをスキップにゃ: {subject}')
                            continue

                        if len(body) > 3000:
                            body = body[:3000] + '\n...(以下省略)'

                        # 受信日時にゃ
                        date_str = msg.get('Date', '')
                        received_at = ''
                        if date_str:
                            try:
                                from email.utils import parsedate_to_datetime
                                dt = parsedate_to_datetime(date_str)
                                received_at = dt.strftime('%Y-%m-%d %H:%M')
                            except Exception:
                                received_at = date_str[:16]

                        emails.append({
                            'gmail_id':           f'imap_{uid.decode()}_{self.username}',
                            'thread_id':          thread_id,
                            'message_id_header':  msg_id,
                            'sender_name':        sender_name,
                            'sender_email':       sender_email,
                            'subject':            subject,
                            'body':               body,
                            'received_at':        received_at,
                        })

                    except Exception as e:
                        logger.error(f'メール処理エラーにゃ: {e}')
                        continue

        except Exception as e:
            logger.error(f'IMAP接続エラーにゃ: {e}')

        return emails

    def _build_search_criteria(self, query: str = None) -> str:
        """GMail風のクエリをIMAPクライテリアに変換するにゃ（簡易版）"""
        if not query:
            return 'UNSEEN'  # デフォルト: 未読のみ

        # 日付指定の変換にゃ（after:2024/01/01 形式）
        import re
        m = re.search(r'after:(\d{4}/\d{2}/\d{2})', query)
        if m:
            date_str = m.group(1).replace('/', '-')
            try:
                dt = datetime.strptime(date_str, '%Y-%m-%d')
                # IMAP の SINCE フォーマット: "01-Jan-2024"
                imap_date = dt.strftime('%d-%b-%Y')
                return f'SINCE "{imap_date}"'
            except ValueError:
                pass

        # from: 指定にゃ
        m = re.search(r'from:(\S+)', query)
        if m:
            return f'FROM "{m.group(1)}"'

        # subject: 指定にゃ
        m = re.search(r'subject:(\S+)', query)
        if m:
            return f'SUBJECT "{m.group(1)}"'

        # in:inbox -from:me 等は UNSEEN で代替にゃ
        if 'in:inbox' in query:
            return 'UNSEEN'

        return 'UNSEEN'

    # ─────────────────────────────────────────────
    # 返信送信
    # ─────────────────────────────────────────────

    def send_reply(self, email_data: dict, reply_text: str, attachments: list = None) -> bool:
        to_address = email_data.get('sender_email', '')

        if not to_address:
            logger.error('送信先が空のため中止にゃ')
            return False

        # 自分自身への送信を防止にゃ
        if to_address.lower() == self.username.lower():
            logger.error(f'自分自身への送信を検知・中止にゃ: {to_address}')
            return False

        if not reply_text.strip():
            logger.error('返信文が空のため中止にゃ')
            return False

        try:
            subject = email_data.get('subject', '')
            subject_str = subject if subject.lower().startswith('re:') else f'Re: {subject}'

            if attachments:
                msg = MIMEMultipart()
                msg.attach(MIMEText(reply_text, 'plain', 'utf-8'))

                for f in attachments:
                    file_bytes = f.read() if hasattr(f, 'read') else bytes(f.getvalue())
                    file_name  = f.name if hasattr(f, 'name') else 'attachment'
                    mime_type, _ = mimetypes.guess_type(file_name)
                    if mime_type is None:
                        mime_type = 'application/octet-stream'
                    main_type, sub_type = mime_type.split('/', 1)

                    part = MIMEBase(main_type, sub_type)
                    part.set_payload(file_bytes)
                    encoders.encode_base64(part)
                    part.add_header('Content-Disposition', 'attachment', filename=file_name)
                    msg.attach(part)
            else:
                msg = MIMEText(reply_text, 'plain', 'utf-8')

            msg['From']    = self.username
            msg['To']      = to_address
            msg['Subject'] = subject_str
            if email_data.get('message_id_header'):
                msg['In-Reply-To'] = email_data['message_id_header']
                msg['References']  = email_data['message_id_header']

            ctx = ssl.create_default_context()

            # ポート465はSSL、587はSTARTTLS にゃ
            if self.smtp_port == 465:
                with smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, context=ctx) as smtp:
                    smtp.login(self.username, self.password)
                    smtp.send_message(msg)
            else:
                with smtplib.SMTP(self.smtp_host, self.smtp_port) as smtp:
                    smtp.ehlo()
                    smtp.starttls(context=ctx)
                    smtp.login(self.username, self.password)
                    smtp.send_message(msg)

            logger.info(f'返信送信完了にゃ: {to_address} / 添付:{len(attachments or [])}件')
            return True

        except Exception as e:
            logger.error(f'返信送信失敗にゃ: {e}')
            return False
