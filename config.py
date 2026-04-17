import os
from dotenv import load_dotenv

load_dotenv()

def _get(key: str, default: str = '') -> str:
    """os.environ → st.secrets の順で取得にゃ（Streamlit Cloud対応）"""
    val = os.getenv(key, '').strip()
    if val:
        return val
    try:
        import streamlit as st
        v = st.secrets.get(key, default)
        return str(v).strip() if v else default
    except Exception:
        return default


_base = os.path.dirname(os.path.abspath(__file__))


class _ConfigMeta:
    """Config.XXX でアクセスするたびに最新の環境変数を返すにゃ"""

    # 静的パス（起動時に確定するにゃ）
    GMAIL_CREDENTIALS_PATH = os.path.join(_base, 'credentials.json')
    GMAIL_TOKEN_PATH       = os.path.join(_base, 'token.json')
    LOG_PATH               = os.path.join(_base, 'logs', 'mail-manager.log')
    RULES_PATH             = os.path.join(_base, 'rules.yaml')

    def __getattr__(self, name: str):
        mapping = {
            'ANTHROPIC_API_KEY':     ('ANTHROPIC_API_KEY',     ''),
            'NOTION_TOKEN':          ('NOTION_TOKEN',           ''),
            'NOTION_PARENT_PAGE_ID': ('NOTION_PARENT_PAGE_ID', ''),
            'SUPABASE_URL':          ('SUPABASE_URL',           ''),
            'SUPABASE_KEY':          ('SUPABASE_KEY',           ''),
            'GMAIL_QUERY':           ('GMAIL_QUERY',            'is:unread is:inbox -from:me'),
            'CLAUDE_MODEL':          ('CLAUDE_MODEL',           'claude-sonnet-4-6'),
        }
        if name == 'MAX_EMAILS_PER_FETCH':
            return int(_get('MAX_EMAILS_PER_FETCH', '50'))
        if name in mapping:
            return _get(*mapping[name])
        raise AttributeError(f'Config has no attribute {name!r}')


Config = _ConfigMeta()
