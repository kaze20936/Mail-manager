import os
from dotenv import load_dotenv

load_dotenv()

def _get(key: str, default: str = '') -> str:
    """os.environ → st.secrets の順で取得にゃ"""
    val = os.getenv(key, '')
    if val:
        return val
    try:
        import streamlit as st
        return st.secrets.get(key, default)
    except Exception:
        return default

class Config:
    @classmethod
    def _load(cls):
        load_dotenv(override=True)

    ANTHROPIC_API_KEY     = property(lambda self: _get('ANTHROPIC_API_KEY'))
    NOTION_TOKEN          = property(lambda self: _get('NOTION_TOKEN'))
    NOTION_PARENT_PAGE_ID = property(lambda self: _get('NOTION_PARENT_PAGE_ID'))
    SUPABASE_URL          = property(lambda self: _get('SUPABASE_URL'))
    SUPABASE_KEY          = property(lambda self: _get('SUPABASE_KEY'))

    _base = os.path.dirname(os.path.abspath(__file__))
    GMAIL_CREDENTIALS_PATH = os.path.join(_base, 'credentials.json')
    GMAIL_TOKEN_PATH       = os.path.join(_base, 'token.json')
    LOG_PATH               = os.path.join(_base, 'logs', 'mail-manager.log')
    RULES_PATH             = os.path.join(_base, 'rules.yaml')

    GMAIL_QUERY          = property(lambda self: _get('GMAIL_QUERY', 'is:unread is:inbox -from:me'))
    MAX_EMAILS_PER_FETCH = property(lambda self: int(_get('MAX_EMAILS_PER_FETCH', '50')))
    CLAUDE_MODEL         = property(lambda self: _get('CLAUDE_MODEL', 'claude-sonnet-4-6'))
