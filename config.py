import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    ANTHROPIC_API_KEY     = os.getenv('ANTHROPIC_API_KEY', '')
    NOTION_TOKEN          = os.getenv('NOTION_TOKEN', '')
    NOTION_PARENT_PAGE_ID = os.getenv('NOTION_PARENT_PAGE_ID', '')

    # ── Supabase（DB）
    SUPABASE_URL = os.getenv('SUPABASE_URL', '')
    SUPABASE_KEY = os.getenv('SUPABASE_KEY', '')  # service_role キーを使うにゃ

    # ── Gmail 認証ファイル（ローカル実行 or 環境変数から復元）
    _base = os.path.dirname(os.path.abspath(__file__))
    GMAIL_CREDENTIALS_PATH = os.path.join(_base, 'credentials.json')
    GMAIL_TOKEN_PATH       = os.path.join(_base, 'token.json')

    # ── ログ
    LOG_PATH = os.path.join(_base, 'logs', 'mail-manager.log')

    # ── ルール・その他設定
    RULES_PATH           = os.path.join(_base, 'rules.yaml')
    GMAIL_QUERY          = os.getenv('GMAIL_QUERY', 'is:unread is:inbox -from:me')
    MAX_EMAILS_PER_FETCH = int(os.getenv('MAX_EMAILS_PER_FETCH', '50'))
    CLAUDE_MODEL         = os.getenv('CLAUDE_MODEL', 'claude-sonnet-4-6')
