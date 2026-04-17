import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    ANTHROPIC_API_KEY     = os.getenv('ANTHROPIC_API_KEY', '')
    NOTION_TOKEN          = os.getenv('NOTION_TOKEN', '')
    NOTION_PARENT_PAGE_ID = os.getenv('NOTION_PARENT_PAGE_ID', '')

    # ── Railway デプロイ時は DATA_DIR=/data を永続ボリュームにマウントするにゃ
    #    ローカル実行時はカレントディレクトリを使うにゃ
    DATA_DIR = os.getenv('DATA_DIR', os.path.dirname(os.path.abspath(__file__)))

    GMAIL_CREDENTIALS_PATH = os.path.join(DATA_DIR, 'credentials.json')
    GMAIL_TOKEN_PATH       = os.path.join(DATA_DIR, 'token.json')
    DB_PATH                = os.path.join(DATA_DIR, 'mail_manager.db')
    LOG_PATH               = os.path.join(DATA_DIR, 'logs', 'mail-manager.log')

    # ── これらはリポジトリ内のファイルを使うにゃ（永続化不要）
    RULES_PATH           = os.getenv('RULES_PATH', os.path.join(
                               os.path.dirname(os.path.abspath(__file__)), 'rules.yaml'))
    GMAIL_QUERY          = os.getenv('GMAIL_QUERY', 'is:unread is:inbox -from:me')
    MAX_EMAILS_PER_FETCH = int(os.getenv('MAX_EMAILS_PER_FETCH', '50'))
    CLAUDE_MODEL         = os.getenv('CLAUDE_MODEL', 'claude-sonnet-4-6')
