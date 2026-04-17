import base64
import logging
import mimetypes
import os
from datetime import datetime
from email.header import decode_header
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email import encoders
from email.utils import parseaddr

from bs4 import BeautifulSoup
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow, Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from config import Config

logger = logging.getLogger(__name__)

SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',  # メール読み取り
    'https://www.googleapis.com/auth/gmail.send',      # 返信送信のみ
    # ── 以下は意図的に除外（最小権限の原則）──
    # gmail.modify  → ラベル変更・既読化・移動などを禁止
    # gmail.compose → 新規メール作成を禁止（返信のみ許可）
    # mail.google.com → フルアクセスを禁止
    # gmail.insert  → メール挿入を禁止
]

# 送信を許可するドメイン制限（空リストで制限なし）
# 例: ALLOWED_DOMAINS = ['@example.com', '@client.co.jp']
ALLOWED_DOMAINS: list[str] = []


class GmailClient:
    def __init__(self):
        self.service = self._authenticate()

    def _authenticate(self):
        # ── Railway デプロイ用: 環境変数から credentials.json を復元にゃ
        creds_json_env = os.getenv('GMAIL_CREDENTIALS_JSON', '')
        if creds_json_env and not os.path.exists(Config.GMAIL_CREDENTIALS_PATH):
            os.makedirs(os.path.dirname(Config.GMAIL_CREDENTIALS_PATH), exist_ok=True)
            with open(Config.GMAIL_CREDENTIALS_PATH, 'w', encoding='utf-8') as f:
                f.write(creds_json_env)
            logger.info('環境変数 GMAIL_CREDENTIALS_JSON から credentials.json を生成したにゃ')

        if not os.path.exists(Config.GMAIL_CREDENTIALS_PATH):
            raise FileNotFoundError(
                '\n\n【セットアップ必要】credentials.json が見つからないにゃ！\n'
                '\nローカル: ⚙️設定タブ → 🔧初期設定 の手順に従ってにゃ\n'
                'Railway:  環境変数 GMAIL_CREDENTIALS_JSON に credentials.json の内容を設定してにゃ\n'
            )

        # ── Railway デプロイ用: 環境変数から token.json を復元にゃ
        token_json_env = os.getenv('GMAIL_TOKEN_JSON', '')
        if token_json_env and not os.path.exists(Config.GMAIL_TOKEN_PATH):
            os.makedirs(os.path.dirname(Config.GMAIL_TOKEN_PATH), exist_ok=True)
            with open(Config.GMAIL_TOKEN_PATH, 'w', encoding='utf-8') as f:
                f.write(token_json_env)
            logger.info('環境変数 GMAIL_TOKEN_JSON から token.json を生成したにゃ')

        creds = None
        if os.path.exists(Config.GMAIL_TOKEN_PATH):
            creds = Credentials.from_authorized_user_file(Config.GMAIL_TOKEN_PATH, SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
                # 更新されたトークンを保存にゃ
                os.makedirs(os.path.dirname(Config.GMAIL_TOKEN_PATH), exist_ok=True)
                with open(Config.GMAIL_TOKEN_PATH, 'w') as f:
                    f.write(creds.to_json())
            else:
                print('\nブラウザが開くにゃ。Googleアカウントでログインして許可してにゃ！\n')
                flow = InstalledAppFlow.from_client_secrets_file(
                    Config.GMAIL_CREDENTIALS_PATH, SCOPES
                )
                creds = flow.run_local_server(port=0)
                print('認証完了にゃ！\n')
                os.makedirs(os.path.dirname(Config.GMAIL_TOKEN_PATH), exist_ok=True)
                with open(Config.GMAIL_TOKEN_PATH, 'w') as f:
                    f.write(creds.to_json())
        else:
            # 有効なトークンも念のため保存パスを確認にゃ
            os.makedirs(os.path.dirname(Config.GMAIL_TOKEN_PATH), exist_ok=True)

        return build('gmail', 'v1', credentials=creds)

    def get_account_email(self) -> str:
        """現在接続中のGmailアドレスを返すにゃ"""
        try:
            profile = self.service.users().getProfile(userId='me').execute()
            return profile.get('emailAddress', '')
        except Exception:
            return ''

    def logout(self):
        """token.json を削除してログアウトするにゃ（ローカル用）"""
        if os.path.exists(Config.GMAIL_TOKEN_PATH):
            os.remove(Config.GMAIL_TOKEN_PATH)


def create_auth_flow(redirect_uri: str) -> tuple:
    """OAuth認証URLとFlowオブジェクトを返すにゃ"""
    flow = Flow.from_client_secrets_file(
        Config.GMAIL_CREDENTIALS_PATH,
        scopes=SCOPES,
        redirect_uri=redirect_uri,
    )
    auth_url, state = flow.authorization_url(
        prompt='select_account',
        access_type='offline',
        include_granted_scopes='true',
    )
    return flow, auth_url, state


def save_token_from_flow(flow: Flow, code: str):
    """認証コードをトークンに交換してtoken.jsonを保存するにゃ"""
    import os as _os
    flow.fetch_token(code=code)
    creds = flow.credentials
    _os.makedirs(_os.path.dirname(Config.GMAIL_TOKEN_PATH), exist_ok=True)
    with open(Config.GMAIL_TOKEN_PATH, 'w', encoding='utf-8') as f:
        f.write(creds.to_json())

    def _decode_str(self, value: str) -> str:
        parts = decode_header(value or '')
        result = []
        for part, enc in parts:
            if isinstance(part, bytes):
                result.append(part.decode(enc or 'utf-8', errors='replace'))
            else:
                result.append(str(part))
        return ''.join(result)

    def _extract_body(self, payload: dict) -> str:
        mime = payload.get('mimeType', '')

        if 'parts' in payload:
            # multipart: prefer text/plain
            for part in payload['parts']:
                if part['mimeType'] == 'text/plain':
                    data = part['body'].get('data', '')
                    if data:
                        return base64.urlsafe_b64decode(data).decode('utf-8', errors='replace')
            # fallback to text/html
            for part in payload['parts']:
                if part['mimeType'] == 'text/html':
                    data = part['body'].get('data', '')
                    if data:
                        html = base64.urlsafe_b64decode(data).decode('utf-8', errors='replace')
                        return BeautifulSoup(html, 'html.parser').get_text('\n').strip()
            # recurse into nested multipart
            for part in payload['parts']:
                if part['mimeType'].startswith('multipart/'):
                    body = self._extract_body(part)
                    if body:
                        return body
        else:
            data = payload['body'].get('data', '')
            if data:
                content = base64.urlsafe_b64decode(data).decode('utf-8', errors='replace')
                if mime == 'text/html':
                    return BeautifulSoup(content, 'html.parser').get_text('\n').strip()
                return content

        return ''

    def fetch_new_emails(self, max_results: int = None, query: str = None) -> list:
        max_results = max_results or Config.MAX_EMAILS_PER_FETCH
        q = query if query is not None else Config.GMAIL_QUERY
        emails = []

        try:
            res = self.service.users().messages().list(
                userId='me',
                q=q,
                maxResults=max_results
            ).execute()

            messages = res.get('messages', [])
            logger.info(f"Gmail から {len(messages)} 件取得")

            for ref in messages:
                try:
                    msg = self.service.users().messages().get(
                        userId='me', id=ref['id'], format='full'
                    ).execute()

                    hdrs = {h['name']: h['value'] for h in msg['payload'].get('headers', [])}

                    sender_raw = hdrs.get('From', '')
                    sender_name, sender_email = parseaddr(sender_raw)
                    sender_name = self._decode_str(sender_name) if sender_name else sender_email

                    subject = self._decode_str(hdrs.get('Subject', '(件名なし)'))
                    body = self._extract_body(msg['payload'])

                    if not body.strip():
                        logger.info(f"空メールをスキップ: {ref['id']}")
                        continue

                    if len(body) > 3000:
                        body = body[:3000] + '\n...(以下省略)'

                    # internalDate はミリ秒エポック
                    internal_date = msg.get('internalDate', '')
                    received_at = ''
                    if internal_date and internal_date.isdigit():
                        ts = int(internal_date) / 1000
                        received_at = datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M')

                    emails.append({
                        'gmail_id':           ref['id'],
                        'thread_id':          msg.get('threadId', ''),
                        'message_id_header':  hdrs.get('Message-ID', ''),
                        'sender_name':        sender_name,
                        'sender_email':       sender_email,
                        'subject':            subject,
                        'body':               body,
                        'received_at':        received_at,
                    })

                except Exception as e:
                    logger.error(f"メール処理エラー {ref['id']}: {e}")
                    continue

        except HttpError as e:
            logger.error(f"Gmail API エラー: {e}")

        return emails

    def send_reply(self, email_data: dict, reply_text: str, attachments: list = None) -> bool:
        to_address = email_data.get('sender_email', '')

        # ── ガード1: 送信先が空なら拒否
        if not to_address:
            logger.error('送信先メールアドレスが空のため送信を中止にゃ')
            return False

        # ── ガード2: 自分自身への送信を防止（ループ防止）
        try:
            my_profile = self.service.users().getProfile(userId='me').execute()
            my_email = my_profile.get('emailAddress', '')
            if to_address.lower() == my_email.lower():
                logger.error(f'自分自身への送信を検知・中止にゃ: {to_address}')
                return False
        except Exception:
            pass

        # ── ガード3: thread_id が一致しない場合は送信しない（誤送信防止）
        if not email_data.get('thread_id'):
            logger.error('thread_id がないため送信を中止にゃ')
            return False

        # ── ガード4: ドメイン制限
        if ALLOWED_DOMAINS:
            if not any(domain.lower() in to_address.lower() for domain in ALLOWED_DOMAINS):
                logger.error(f'送信先ドメインが許可リストにないため中止にゃ: {to_address}')
                return False

        # ── ガード5: 返信文が空なら送信しない
        if not reply_text.strip():
            logger.error('返信文が空のため送信を中止にゃ')
            return False

        try:
            subject = email_data.get('subject', '')
            subject_str = subject if subject.lower().startswith('re:') else f'Re: {subject}'

            # ── 添付ファイルがある場合は multipart、なければ plain text
            if attachments:
                msg = MIMEMultipart()
                msg.attach(MIMEText(reply_text, 'plain', 'utf-8'))

                for f in attachments:
                    # Streamlit の UploadedFile オブジェクトから読み取るにゃ
                    file_bytes = f.read() if hasattr(f, 'read') else bytes(f.getvalue())
                    file_name  = f.name if hasattr(f, 'name') else 'attachment'
                    mime_type, _ = mimetypes.guess_type(file_name)
                    if mime_type is None:
                        mime_type = 'application/octet-stream'
                    main_type, sub_type = mime_type.split('/', 1)

                    part = MIMEBase(main_type, sub_type)
                    part.set_payload(file_bytes)
                    encoders.encode_base64(part)
                    part.add_header(
                        'Content-Disposition',
                        'attachment',
                        filename=file_name
                    )
                    msg.attach(part)
                    logger.info(f'添付ファイル追加にゃ: {file_name} ({mime_type})')
            else:
                msg = MIMEText(reply_text, 'plain', 'utf-8')

            msg['to']      = to_address
            msg['subject'] = subject_str
            if email_data.get('message_id_header'):
                msg['In-Reply-To'] = email_data['message_id_header']
                msg['References']  = email_data['message_id_header']

            raw = base64.urlsafe_b64encode(msg.as_bytes()).decode('utf-8')
            body = {'raw': raw, 'threadId': email_data['thread_id']}

            result = self.service.users().messages().send(
                userId='me', body=body
            ).execute()

            logger.info(f'返信送信完了: {to_address} / msg={result.get("id")} / 添付:{len(attachments or [])}件')
            return True

        except HttpError as e:
            logger.error(f'返信送信失敗: {e}')
            return False
