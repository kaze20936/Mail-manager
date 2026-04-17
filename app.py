"""
app.py — Mail Manager WebUI
起動: streamlit run app.py
"""
import logging
import os
import subprocess
import sys

import streamlit as st
import yaml
from dotenv import load_dotenv

load_dotenv(override=True)

from database import Database
from gmail_client import GmailClient, create_auth_flow, save_token_from_flow
from notion_logger import NotionLogger
from config import Config

logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# セットアップ状況確認・.env 保存
# ─────────────────────────────────────────────

def get_setup_status() -> dict:
    """セットアップ状況を確認して返す"""
    load_dotenv(override=True)
    cwd = os.path.dirname(os.path.abspath(__file__))

    # ファイルが存在するか、または環境変数（Streamlit Cloud用）があればOKにゃ
    creds_env = os.getenv('GMAIL_CREDENTIALS_JSON', '').strip()
    try:
        import streamlit as _st
        creds_env = creds_env or str(_st.secrets.get('GMAIL_CREDENTIALS_JSON', ''))
    except Exception:
        pass
    credentials_ok = os.path.exists(os.path.join(cwd, 'credentials.json')) or bool(creds_env)

    token_env = os.getenv('GMAIL_TOKEN_JSON', '').strip()
    try:
        import streamlit as _st
        token_env = token_env or str(_st.secrets.get('GMAIL_TOKEN_JSON', ''))
    except Exception:
        pass
    token_ok = os.path.exists(os.path.join(cwd, 'token.json')) or bool(token_env)
    api_key         = os.getenv('ANTHROPIC_API_KEY', '').strip()
    anthropic_ok    = bool(api_key and not api_key.startswith('your_') and len(api_key) > 10)
    notion_token    = os.getenv('NOTION_TOKEN', '').strip()
    notion_ok       = bool(notion_token and not notion_token.startswith('your_') and len(notion_token) > 10)
    supabase_url    = os.getenv('SUPABASE_URL', '').strip()
    supabase_key    = os.getenv('SUPABASE_KEY', '').strip()
    supabase_ok     = bool(supabase_url and supabase_key
                           and supabase_url.startswith('https://')
                           and len(supabase_key) > 20)

    return {
        'credentials':        credentials_ok,
        'token':              token_ok,
        'anthropic_ok':       anthropic_ok,
        'anthropic_value':    api_key,
        'supabase_ok':        supabase_ok,
        'supabase_url_value': supabase_url,
        'supabase_key_value': supabase_key,
        'notion_ok':          notion_ok,
        'notion_value':       notion_token,
        'notion_page_value':  os.getenv('NOTION_PARENT_PAGE_ID', '').strip(),
        'all_required':       credentials_ok and token_ok and anthropic_ok and supabase_ok,
    }


def write_env_value(key: str, value: str):
    """指定キーの値を .env に保存（なければ追加・あれば上書き）"""
    cwd = os.path.dirname(os.path.abspath(__file__))
    env_path = os.path.join(cwd, '.env')

    lines = []
    if os.path.exists(env_path):
        with open(env_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

    found = False
    new_lines = []
    for line in lines:
        if line.startswith(f'{key}=') or line.startswith(f'{key} ='):
            new_lines.append(f'{key}={value}\n')
            found = True
        else:
            new_lines.append(line)

    if not found:
        new_lines.append(f'{key}={value}\n')

    with open(env_path, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)

    os.environ[key] = value

CATEGORY_ICONS = {
    '仕事依頼':     '🟠',
    '問い合わせ':   '🔵',
    '請求・支払い': '🔴',
    '通知・自動送信': '⚫',
    'その他':       '⚪',
}

st.set_page_config(page_title='Mail Manager', page_icon='✉️', layout='wide')

st.markdown("""
<style>
/* ══ グローバル ══════════════════════════════ */
section.main > div { padding-top: 1.2rem; }
.block-container { padding: 1.5rem 2.5rem; }

/* ══ ボタン ══════════════════════════════════ */
div.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #22c55e 0%, #16a34a 100%);
    color: white; border: none; border-radius: 8px;
    font-weight: 700; padding: 0.45rem 1.1rem;
    box-shadow: 0 2px 8px rgba(34,197,94,0.35);
    transition: all .15s;
}
div.stButton > button[kind="primary"]:hover {
    background: linear-gradient(135deg, #16a34a 0%, #15803d 100%);
    box-shadow: 0 4px 12px rgba(34,197,94,0.5); transform: translateY(-1px);
}
div.stButton > button[kind="secondary"] {
    background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
    color: white; border: none; border-radius: 8px;
    font-weight: 600; padding: 0.45rem 1.1rem;
    box-shadow: 0 2px 6px rgba(245,158,11,0.3);
    transition: all .15s;
}
div.stButton > button[kind="secondary"]:hover {
    background: linear-gradient(135deg, #d97706 0%, #b45309 100%);
    box-shadow: 0 4px 10px rgba(245,158,11,0.45); transform: translateY(-1px);
}
div.stButton > button[kind="tertiary"] {
    border: 1.5px solid #94a3b8; color: #64748b;
    border-radius: 8px; transition: all .15s;
}
div.stButton > button[kind="tertiary"]:hover {
    border-color: #64748b; color: #334155; background: #f1f5f9;
}

/* ══ 統計カード ══════════════════════════════ */
.stat-card {
    border-radius: 12px; padding: 1rem 1.4rem;
    text-align: center; margin-bottom: .5rem;
}
.stat-card .stat-num {
    font-size: 2.2rem; font-weight: 800; line-height: 1.1;
}
.stat-card .stat-label {
    font-size: 0.82rem; font-weight: 500; opacity: .75; margin-top: .2rem;
}
.stat-pending  { background: #eff6ff; border: 2px solid #bfdbfe; color: #1e40af; }
.stat-saved    { background: #fefce8; border: 2px solid #fde68a; color: #92400e; }
.stat-sent     { background: #f0fdf4; border: 2px solid #bbf7d0; color: #14532d; }

/* ══ メールカード ════════════════════════════ */
.mail-card {
    border-radius: 12px; border: 1.5px solid #e2e8f0;
    padding: 1rem 1.2rem; margin-bottom: .8rem;
    background: white;
    border-left-width: 5px !important;
}
.mail-card-仕事依頼      { border-left-color: #f97316 !important; }
.mail-card-問い合わせ    { border-left-color: #3b82f6 !important; }
.mail-card-請求・支払い  { border-left-color: #ef4444 !important; }
.mail-card-通知・自動送信 { border-left-color: #6b7280 !important; }
.mail-card-その他        { border-left-color: #a855f7 !important; }

.mail-category {
    display: inline-block; font-size: .72rem; font-weight: 700;
    padding: .15rem .55rem; border-radius: 20px; margin-bottom: .4rem;
}
.cat-仕事依頼      { background: #fff7ed; color: #c2410c; }
.cat-問い合わせ    { background: #eff6ff; color: #1d4ed8; }
.cat-請求・支払い  { background: #fef2f2; color: #b91c1c; }
.cat-通知・自動送信 { background: #f3f4f6; color: #374151; }
.cat-その他        { background: #faf5ff; color: #7e22ce; }

.mail-subject {
    font-size: 1.05rem; font-weight: 700; color: #0f172a; margin: .3rem 0;
}
.mail-meta {
    font-size: .78rem; color: #64748b; margin-bottom: .5rem;
}

/* ══ タブ ════════════════════════════════════ */
.stTabs [data-baseweb="tab-list"] {
    gap: 4px; border-bottom: 2px solid #e2e8f0;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 8px 8px 0 0; padding: .55rem 1.2rem;
    font-weight: 600; font-size: .9rem;
}
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# リソース初期化（キャッシュ）
# ─────────────────────────────────────────────

def get_db() -> Database:
    if 'db' not in st.session_state:
        st.session_state['db'] = Database()
    return st.session_state['db']


def get_gmail() -> GmailClient | None:
    if 'gmail_client' not in st.session_state:
        try:
            st.session_state['gmail_client'] = GmailClient()
        except Exception as e:
            st.error(f'Gmail 認証エラー: {e}')
            st.session_state['gmail_client'] = None
    return st.session_state['gmail_client']


def get_notion() -> NotionLogger | None:
    if 'notion_logger' not in st.session_state:
        try:
            st.session_state['notion_logger'] = NotionLogger()
        except Exception as e:
            logger.error(f'Notion 初期化エラー: {e}')
            st.session_state['notion_logger'] = None
    return st.session_state['notion_logger']


# ─────────────────────────────────────────────
# ヘルパー
# ─────────────────────────────────────────────

def init_reply_state(emails: list):
    """メール一覧のセッション状態を初期化（初回のみ）"""
    for email in emails:
        key = f"reply_{email['id']}"
        if key not in st.session_state:
            st.session_state[key] = email.get('reply_text') or ''


def do_send(db: Database, email: dict, reply_text: str, attachments: list = None) -> bool:
    gmail = get_gmail()
    if not gmail:
        return False

    success = gmail.send_reply(email, reply_text, attachments=attachments or [])
    if success:
        db.update_reply_text(email['id'], reply_text)
        db.update_status(email['id'], 'sent')

        notion = get_notion()
        if notion:
            email_copy = {**email, 'reply_text': reply_text}
            notion.log_sent(email_copy)

    return success


def bulk_send(db: Database, emails_map: dict, selected_ids: list):
    success_n, fail_n = 0, 0
    progress = st.progress(0, text='送信中...')

    for i, eid in enumerate(selected_ids):
        email = emails_map[eid]
        reply_text = st.session_state.get(f"reply_{eid}", '').strip()

        if reply_text and do_send(db, email, reply_text):
            success_n += 1
        else:
            fail_n += 1

        progress.progress((i + 1) / len(selected_ids),
                          text=f'送信中... {i+1}/{len(selected_ids)}')

    progress.empty()
    st.success(f'✅ 完了！  成功: {success_n} 件 　失敗: {fail_n} 件')
    st.rerun()


# ─────────────────────────────────────────────
# メールカード
# ─────────────────────────────────────────────

def render_card(db: Database, email: dict):
    eid        = email['id']
    reply_key  = f"reply_{eid}"
    check_key  = f"check_{eid}"
    category   = email.get('category', 'その他')

    with st.container():
        col_chk, col_info = st.columns([0.04, 0.96])

        with col_chk:
            st.checkbox('', key=check_key, label_visibility='collapsed')

        with col_info:
            st.markdown(f'''<div class="mail-card mail-card-{category}">
                <span class="mail-category cat-{category}">{category}</span>
                <div class="mail-subject">📧 {email.get('subject','(件名なし)')}</div>
                <div class="mail-meta">
                    👤 {email.get('sender_name','')}
                    &lt;{email.get('sender_email','')}&gt;
                    &nbsp;·&nbsp; 🕐 {email.get('received_at','')}
                </div>
            </div>''', unsafe_allow_html=True)

        with st.expander('📨 元のメールを見る'):
            st.text(email.get('body', '(本文なし)'))

        st.text_area('返信文（編集可能）', key=reply_key, height=180,
                     placeholder='返信文がここに表示されます...')

        # ── 添付ファイル
        uploaded = st.file_uploader(
            '📎 添付ファイル（任意）',
            key=f"attach_{eid}",
            accept_multiple_files=True,
            help='写真・PDF・Word等どんなファイルでも添付できるにゃ',
            label_visibility='visible',
        )
        if uploaded:
            st.caption(f'添付: {", ".join(f.name for f in uploaded)}')

        b1, b2, b3, _ = st.columns([1.2, 1.2, 1, 3])

        with b1:
            if st.button('✉ この1件を送信', key=f"send_{eid}", type='primary'):
                text = st.session_state.get(reply_key, '').strip()
                if not text:
                    st.error('返信文が空ですにゃ！')
                else:
                    with st.spinner('送信中...'):
                        if do_send(db, email, text, attachments=uploaded or []):
                            st.success('送信完了にゃ！')
                            st.rerun()
                        else:
                            st.error('送信に失敗しましたにゃ...')

        with b2:
            if st.button('💾 編集を保存', key=f"save_{eid}", type='secondary'):
                text = st.session_state.get(reply_key, '')
                db.save_reply_and_set_saved(eid, text)
                st.success('保存したにゃ！')
                st.rerun()

        with b3:
            if st.button('⏭ スキップ', key=f"skip_{eid}"):
                db.update_status(eid, 'skipped')
                st.rerun()

        st.divider()


def render_tab(db: Database, status: str, bulk_key_suffix: str):
    emails = db.get_emails_by_status(status)
    init_reply_state(emails)

    if not emails:
        st.info('メールはありませんにゃ 🎉')
        return

    emails_map = {e['id']: e for e in emails}

    # ── 選択された件数を確認（前の実行から）
    selected_ids = [
        eid for eid in emails_map
        if st.session_state.get(f"check_{eid}", False)
    ]

    top_col1, top_col2 = st.columns([2, 3])
    with top_col1:
        if selected_ids:
            if st.button(
                f'📤 選択した {len(selected_ids)} 件をまとめて送信',
                type='primary',
                key=f'bulk_send_{bulk_key_suffix}'
            ):
                bulk_send(db, emails_map, selected_ids)
        else:
            st.caption('☑ チェックで複数選択 → まとめて送信できるにゃ')

    with top_col2:
        sel_col1, sel_col2 = st.columns(2)
        with sel_col1:
            if st.button('全選択', key=f'sel_all_{bulk_key_suffix}'):
                for eid in emails_map:
                    st.session_state[f"check_{eid}"] = True
                st.rerun()
        with sel_col2:
            if st.button('全解除', key=f'desel_all_{bulk_key_suffix}'):
                for eid in emails_map:
                    st.session_state[f"check_{eid}"] = False
                st.rerun()

    st.markdown('')
    for email in emails:
        render_card(db, email)


# ─────────────────────────────────────────────
# 設定タブ
# ─────────────────────────────────────────────

def load_rules() -> dict:
    try:
        with open(Config.RULES_PATH, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except Exception:
        return {'skip': {'senders': [], 'subject_keywords': []}, 'categories': {}}

def save_rules(rules: dict):
    with open(Config.RULES_PATH, 'w', encoding='utf-8') as f:
        yaml.dump(rules, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

def render_list_editor(label: str, items: list, add_key: str, placeholder: str) -> list:
    """リスト形式のルール編集UI。変更後のリストを返す"""
    st.caption(label)
    to_delete = []
    for i, item in enumerate(items):
        col1, col2 = st.columns([5, 1])
        with col1:
            st.code(item)
        with col2:
            if st.button('削除', key=f"del_{add_key}_{i}"):
                to_delete.append(i)

    new_items = [item for i, item in enumerate(items) if i not in to_delete]

    new_val = st.text_input('追加', key=f"add_input_{add_key}", placeholder=placeholder)
    if st.button('＋ 追加', key=f"add_btn_{add_key}"):
        if new_val.strip() and new_val.strip() not in new_items:
            new_items.append(new_val.strip())
            st.rerun()

    return new_items

def render_sender_mails(db, email_addr: str, skip_senders: list, rules: dict):
    """送信者のメール一覧と操作ボタンを表示"""
    mails = db.get_emails_by_sender(email_addr)
    if mails:
        for m in mails:
            status_icon = {'pending':'📬','saved':'💾','sent':'✅','skipped':'⏭'}.get(m['status'],'')
            st.markdown(f"{status_icon} `{m['received_at']}` &nbsp; {m['subject'] or '(件名なし)'}")
    else:
        st.caption('メールなし')

    rule_skip = any(p.lower() in email_addr.lower() for p in skip_senders)
    if rule_skip:
        if st.button('✅ 返信しないリストから外す', key=f"remove_{email_addr}"):
            skip_senders[:] = [x for x in skip_senders if x != email_addr]
            save_rules(rules)
            db.show_emails_by_sender(email_addr)  # 非表示を解除して再表示
            st.rerun()
    else:
        if st.button('🚫 返信しないリストに登録', key=f"promote_{email_addr}"):
            if email_addr not in skip_senders:
                skip_senders.append(email_addr)
                save_rules(rules)
                db.hide_emails_by_sender(email_addr)  # 未対応・保存済みを非表示に
                st.rerun()


def render_initial_setup():
    """初期設定タブ — 非技術者向けセットアップウィザード"""
    status = get_setup_status()
    cwd = os.path.dirname(os.path.abspath(__file__))

    st.caption('アプリを使い始めるための設定をここで行うにゃ。上から順番に設定してにゃ。')

    # ── ステップ1: credentials.json
    st.markdown('---')
    ok1 = status['credentials']
    st.markdown(f'### {"✅" if ok1 else "❌"} ステップ1：Gmail接続ファイルの設置')

    if ok1:
        st.success('credentials.json が見つかったにゃ ✓')
    else:
        st.error('credentials.json がないにゃ！以下の手順でファイルを入手してにゃ。')

    with st.expander('📋 設置手順を見る（クリックして開くにゃ）', expanded=not ok1):
        st.markdown('''
**Googleのサイトでファイルをダウンロードしてフォルダにいれるにゃ：**

**① Google Cloud Consoleを開くにゃ**
→ ブラウザで `console.cloud.google.com` を開いてGoogleアカウントでログインにゃ

**② 新しいプロジェクトを作るにゃ**
→ 画面上の「プロジェクトを選択」→「新しいプロジェクト」をクリックにゃ
→ 名前は「mail-manager」などでOKにゃ

**③ Gmail APIを有効にするにゃ**
→ 左メニュー「APIとサービス」→「ライブラリ」→「Gmail API」を検索→「有効にする」にゃ

**④ 認証情報を作るにゃ**
→「APIとサービス」→「認証情報」→「認証情報を作成」→「OAuthクライアントID」にゃ
→ 初回は「同意画面の設定」が先に出るにゃ。「外部」を選んでアプリ名だけ入れてOKにゃ
→ アプリの種類は「**デスクトップアプリ**」を選ぶにゃ

**⑤ ファイルをダウンロードするにゃ**
→ 作成後に「JSONをダウンロード」をクリックにゃ
→ ダウンロードしたファイルを **`credentials.json`** に名前を変えるにゃ
→ このアプリのフォルダ（`mail-manager`）の中に移動するにゃ

**⑥ このページを再読み込みする（F5キー）にゃ**
→ ✅ に変わればOKにゃ！
        ''')

    # ── ステップ2: Supabase（データベース）
    st.markdown('---')
    ok_sb = status['supabase_ok']
    st.markdown(f'### {"✅" if ok_sb else "❌"} ステップ2：データベース（Supabase）を設定する')

    if ok_sb:
        st.success(f'Supabase が設定されているにゃ ✓  （`{status["supabase_url_value"]}`）')
    else:
        st.error('Supabase が未設定にゃ！以下の手順で設定してにゃ。')

    with st.expander('🗄️ Supabaseの設定手順を見る', expanded=not ok_sb):
        st.markdown('''
**Supabaseのアカウントを作ってプロジェクトを作成するにゃ：**

**① Supabaseでアカウントを作るにゃ**
→ ブラウザで `supabase.com` を開いて「Start your project」でGitHubアカウントでログインにゃ

**② 新しいプロジェクトを作るにゃ**
→ 「New project」をクリックにゃ
→ 名前: `mail-manager`、パスワードは何でもOK（メモしておくにゃ）、リージョン: `Northeast Asia (Tokyo)` を選ぶにゃ

**③ テーブルを作るにゃ**
→ 左メニュー「SQL Editor」→「New query」をクリックにゃ
→ このアプリフォルダにある `supabase_schema.sql` の内容を全部コピーして貼り付けにゃ
→ 「Run」ボタンを押してにゃ（「Success」と出ればOKにゃ）

**④ URLとAPIキーをコピーするにゃ**
→ 左メニュー「Settings」→「API」を開くにゃ
→ **Project URL** をコピーして下に貼り付けるにゃ
→ **service_role** の「Reveal」ボタンを押してキーをコピーして下に貼り付けるにゃ
→ （`anon` ではなく `service_role` の方にゃ！）
        ''')
        new_sb_url = st.text_input(
            'SUPABASE_URL を貼り付けてにゃ',
            value=status['supabase_url_value'],
            placeholder='https://xxxxxxxxxx.supabase.co',
            key='input_supabase_url',
        )
        new_sb_key = st.text_input(
            'SUPABASE_KEY（service_role）を貼り付けてにゃ',
            value=status['supabase_key_value'],
            type='password',
            placeholder='eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...',
            key='input_supabase_key',
        )
        if st.button('💾 Supabase設定を保存する', key='save_supabase', type='primary'):
            if new_sb_url.strip() and new_sb_key.strip():
                write_env_value('SUPABASE_URL', new_sb_url.strip())
                write_env_value('SUPABASE_KEY', new_sb_key.strip())
                st.success('保存したにゃ！ページを更新（F5）すると反映されるにゃ')
                st.rerun()
            else:
                st.warning('URLとキーの両方を入力してにゃ')

    # ── ステップ3: ANTHROPIC_API_KEY
    st.markdown('---')
    ok2 = status['anthropic_ok']
    st.markdown(f'### {"✅" if ok2 else "❌"} ステップ3：AIのAPIキーを設定する')

    if ok2:
        masked = f"sk-...{status['anthropic_value'][-4:]}" if len(status['anthropic_value']) > 4 else '（設定済み）'
        st.success(f'ANTHROPIC_API_KEY が設定されているにゃ ✓  （`{masked}`）')
    else:
        st.error('ANTHROPIC_API_KEY が未設定にゃ！下から入力してにゃ。')

    with st.expander('🔑 APIキーを入力・変更するにゃ', expanded=not ok2):
        st.markdown('''
**AnthropicのサイトでAPIキーを取得するにゃ：**

1. ブラウザで `console.anthropic.com` を開いてログインにゃ
2. 左メニューの **「API Keys」** を開くにゃ
3. **「Create Key」** をクリックにゃ
4. 表示されたキー（`sk-ant-...`で始まる文字列）をコピーするにゃ
5. 下のボックスに貼り付けて「保存」を押すにゃ
        ''')
        new_key = st.text_input(
            'ANTHROPIC_API_KEY を貼り付けてにゃ',
            value=status['anthropic_value'],
            type='password',
            placeholder='sk-ant-api03-xxxxx...',
            key='input_anthropic_key',
        )
        if st.button('💾 APIキーを保存する', key='save_anthropic_key', type='primary'):
            if new_key.strip():
                write_env_value('ANTHROPIC_API_KEY', new_key.strip())
                st.success('保存したにゃ！')
                st.rerun()
            else:
                st.warning('キーを入力してにゃ')

    # ── ステップ3: Gmail認証
    st.markdown('---')
    ok3 = status['token']
    st.markdown(f'### {"✅" if ok3 else "❌"} ステップ4：Gmailにログインする')

    if ok3:
        st.success('Gmailの認証が完了しているにゃ ✓')
        st.caption('※ ログインし直したいときは下のボタンを使うにゃ')
    else:
        st.info(
            '下のボタンを押すとブラウザが自動で開くにゃ。\n'
            'Gmailのアカウントを選んでログインすれば完了にゃ。\n\n'
            '⚠️ ステップ1のファイルが設置されていないと動かないにゃ'
        )

    col_auth, _ = st.columns([2, 3])
    with col_auth:
        btn_label = '🔄 Gmailを再認証する' if ok3 else '🌐 ブラウザでGmailにログインする'
        btn_type  = 'secondary' if ok3 else 'primary'
        if st.button(btn_label, key='gmail_auth_btn', type=btn_type, disabled=not ok1):
            with st.spinner('ブラウザを開いているにゃ... ログインが終わるまで待つにゃ...'):
                env = os.environ.copy()
                env['PYTHONIOENCODING'] = 'utf-8'
                try:
                    result = subprocess.run(
                        [sys.executable, '-c',
                         'import sys; sys.path.insert(0, "."); '
                         'from gmail_client import GmailClient; GmailClient(); print("AUTH_OK")'],
                        capture_output=True, text=True, encoding='utf-8',
                        errors='replace', cwd=cwd, env=env, timeout=180
                    )
                    if 'AUTH_OK' in result.stdout or os.path.exists(os.path.join(cwd, 'token.json')):
                        st.success('ログイン完了にゃ！')
                        st.rerun()
                    else:
                        st.error(
                            'ログインに失敗したにゃ...\n\n'
                            'credentials.json が正しく設置されているか確認してにゃ。\n'
                            f'詳細: {result.stderr[:200]}'
                        )
                except subprocess.TimeoutExpired:
                    st.error('時間切れになったにゃ。ブラウザでログインを完了してからもう一度押してにゃ。')

    # ── オプション: Notion連携
    st.markdown('---')
    notion_icon = '✅' if status['notion_ok'] else '⬜'
    st.markdown(f'### {notion_icon} オプション：Notion連携（使わなくてもOKにゃ）')
    st.caption('送信した返信の履歴をNotionに自動記録したい場合のみ設定するにゃ。')

    with st.expander('Notionと連携する場合はここを開くにゃ'):
        st.markdown('''
1. ブラウザで `notion.so/my-integrations` を開くにゃ
2. **「新しいインテグレーション」** を作成にゃ
3. 表示されたシークレット（`secret_...`）をコピーして下に貼り付けるにゃ
4. NotionページのURL末尾の32文字のIDも入力するにゃ
        ''')
        new_notion = st.text_input(
            'NOTION_TOKEN',
            value=status['notion_value'],
            type='password',
            placeholder='secret_xxxxx...',
            key='input_notion_token',
        )
        new_notion_page = st.text_input(
            'NOTION_PARENT_PAGE_ID',
            value=status['notion_page_value'],
            placeholder='xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
            key='input_notion_page',
            help='NotionページのURLにある32文字のIDにゃ（ハイフンなし）'
        )
        if st.button('💾 Notion設定を保存', key='save_notion'):
            if new_notion.strip():
                write_env_value('NOTION_TOKEN', new_notion.strip())
            if new_notion_page.strip():
                write_env_value('NOTION_PARENT_PAGE_ID', new_notion_page.strip())
            st.success('保存したにゃ！')
            st.rerun()

    # ── セットアップ状況まとめ
    st.markdown('---')
    st.markdown('### 📊 セットアップ状況まとめ')
    c1, c2, c3, c4 = st.columns(4)
    c1.metric('Gmail接続ファイル', '✅ OK' if ok1 else '❌ 未設定')
    c2.metric('Supabase DB',      '✅ OK' if ok_sb else '❌ 未設定')
    c3.metric('AI APIキー',        '✅ OK' if ok2 else '❌ 未設定')
    c4.metric('Gmailログイン',     '✅ OK' if ok3 else '❌ 未完了')

    all_ok = ok1 and ok_sb and ok2 and ok3
    if all_ok:
        st.success('🎉 すべての設定が完了しているにゃ！「📥 メールを取得する」から始めてにゃ！')
    else:
        remain = sum([not ok1, not ok_sb, not ok2, not ok3])
        st.warning(f'あと {remain} 項目残っているにゃ。上から順番に設定してにゃ。')


def _get_app_url() -> str:
    """アプリのベースURLを取得にゃ（リダイレクトURIに使うにゃ）"""
    # 環境変数 or Streamlit Secrets から取得にゃ
    url = os.getenv('APP_URL', '').strip()
    if not url:
        try:
            url = str(st.secrets.get('APP_URL', '')).strip()
        except Exception:
            pass
    return url.rstrip('/') if url else ''


def render_account_tab():
    """アカウント切り替えタブにゃ（アプリ内OAuth完結）"""

    # ── OAuthコールバック処理（URLに?code=が付いてきたとき）
    params = st.query_params
    oauth_code = params.get('code', '')
    if oauth_code and 'oauth_flow' in st.session_state:
        with st.spinner('Googleと認証中にゃ...'):
            try:
                save_token_from_flow(st.session_state['oauth_flow'], oauth_code)
                del st.session_state['oauth_flow']
                if 'gmail_client' in st.session_state:
                    del st.session_state['gmail_client']
                st.query_params.clear()
                st.success('✅ アカウントを切り替えたにゃ！')
                st.rerun()
            except Exception as e:
                st.error(f'認証に失敗したにゃ: {e}')
                st.query_params.clear()
                if 'oauth_flow' in st.session_state:
                    del st.session_state['oauth_flow']

    # ── 現在のアカウント表示
    st.markdown('### 📧 接続中のGmailアカウント')
    gmail = get_gmail()
    if gmail:
        account_email = gmail.get_account_email()
        st.markdown(
            f'<div style="background:#f0fdf4;border:2px solid #bbf7d0;border-radius:12px;'
            f'padding:1rem 1.4rem;margin-bottom:1.2rem;">'
            f'<div style="font-size:.78rem;color:#16a34a;font-weight:600;margin-bottom:.3rem;">現在接続中</div>'
            f'<div style="font-size:1.1rem;font-weight:700;color:#0f172a;">📧 {account_email or "(取得中...)"}</div>'
            f'</div>',
            unsafe_allow_html=True
        )
    else:
        st.warning('Gmailに接続されていないにゃ')

    st.markdown('### 🔄 アカウントを切り替える')

    app_url = _get_app_url()

    if not app_url:
        # APP_URL未設定の場合は入力してもらうにゃ
        st.info('アプリのURLを設定するとワンクリックで切り替えられるにゃ！')
        app_url_input = st.text_input(
            'このアプリのURL',
            placeholder='https://xxx.streamlit.app または http://localhost:8501',
            help='ブラウザのアドレスバーに表示されているURLをコピーしてにゃ（?以降は不要にゃ）'
        )
        if app_url_input:
            app_url = app_url_input.strip().rstrip('/')

    if app_url:
        st.caption(f'リダイレクト先: `{app_url}`')

        # 認証URLを生成してリンクボタン表示にゃ
        if st.button('🔄 別のGoogleアカウントに切り替える', type='primary'):
            try:
                flow, auth_url, _ = create_auth_flow(app_url)
                st.session_state['oauth_flow'] = flow
                st.session_state['pending_auth_url'] = auth_url
            except Exception as e:
                st.error(f'認証URLの生成に失敗したにゃ: {e}')

        if 'pending_auth_url' in st.session_state:
            st.markdown('---')
            st.markdown('**↓ 下のボタンを押してGoogleアカウントを選択するにゃ！**')
            st.link_button(
                '🔑 Googleでアカウントを選択する',
                st.session_state['pending_auth_url'],
                type='primary',
                use_container_width=True,
            )
            st.caption('認証後、自動的にこのページに戻ってきてアカウントが切り替わるにゃ 🎉')

    st.markdown('---')
    st.markdown('#### ⚠️ 初回設定が必要にゃ（1回だけ）')
    with st.expander('Google Cloud Consoleへの登録手順（初回のみ）'):
        app_url_disp = app_url or 'https://あなたのアプリURL.streamlit.app'
        st.markdown(f'''
1. [Google Cloud Console](https://console.cloud.google.com/) を開くにゃ
2. 左メニュー → **「APIとサービス」→「認証情報」** を開くにゃ
3. credentials.json を作った OAuth クライアントIDをクリックにゃ
4. **「承認済みのリダイレクト URI」** に以下を追加にゃ：
   ```
   {app_url_disp}
   ```
5. 保存してにゃ ✅

→ これを設定するとボタン1つでアカウントが切り替わるにゃ！
        ''')


def render_settings():
    st.subheader('⚙️ 返信ルール設定')
    rules = load_rules()
    db = get_db()

    cfg_tab2, cfg_tab3, cfg_tab4, cfg_tab_account = st.tabs([
        '📋 送信者管理', '🚫 返信しないキーワード', '📂 カテゴリルール', '📧 アカウント'
    ])

    # ══════════════════════════════════════════
    # タブ0: 送信者管理（返信する / しないで分類）
    # ══════════════════════════════════════════
    with cfg_tab2:
        st.info(
            '**送信者をここで仕分けるにゃ**\n\n'
            '- **✉️ 返信する** — 未対応タブに表示されて返信対象になるにゃ\n'
            '- **🚫 返信しない** — 未対応から非表示になり、次回から自動スキップされるにゃ（メルマガ・通知メールはここに登録するにゃ）\n'
            '- チェックして一括で移動できるにゃ。個別に移動したいときは各行を展開してボタンを押すにゃ'
        )
        skip = rules.setdefault('skip', {'senders': [], 'subject_keywords': []})
        skip_senders = skip.setdefault('senders', [])

        senders = db.get_senders_summary()

        if not senders:
            st.info('まだメールを取得していないにゃ。上の「📥 メールを取得する」パネルから取得してにゃ')
        else:
            search = st.text_input('🔍 絞り込む', key='sender_search',
                                   placeholder='名前・アドレスで検索にゃ')

            def match(s):
                if not search:
                    return True
                q = search.lower()
                return q in s['sender_email'].lower() or q in (s['sender_name'] or '').lower()

            filtered = [s for s in senders if match(s)]

            skip_list    = [s for s in filtered if any(p.lower() in s['sender_email'].lower() for p in skip_senders)
                                                or (s.get('skipped_count', 0) == s['mail_count'] and s['mail_count'] > 0)]
            reply_list   = [s for s in filtered if s not in skip_list]

            # ── 返信するリスト
            st.markdown(f'### ✉️ 返信する（{len(reply_list)}件）')
            if not reply_list:
                st.caption('なしにゃ')
            else:
                sel_c1, sel_c2 = st.columns([1, 1])
                with sel_c1:
                    if st.button('全選択', key='sel_all_reply'):
                        for s in reply_list:
                            st.session_state[f"to_skip_{s['sender_email']}"] = True
                        st.rerun()
                with sel_c2:
                    if st.button('全解除', key='desel_all_reply'):
                        for s in reply_list:
                            st.session_state[f"to_skip_{s['sender_email']}"] = False
                        st.rerun()

            selected_to_skip = []
            for s in reply_list:
                email_addr    = s['sender_email']
                name          = s['sender_name'] or email_addr
                count         = s['mail_count']
                skipped_count = s.get('skipped_count', 0) or 0
                category      = s['category']
                icon          = CATEGORY_ICONS.get(category, '⚪')

                c_chk, c_info = st.columns([0.05, 0.95])
                with c_chk:
                    if st.checkbox('', key=f"to_skip_{email_addr}"):
                        selected_to_skip.append(email_addr)
                with c_info:
                    badge = f'{icon} {category}'
                    if skipped_count > 0:
                        badge += f'　⏭ {skipped_count}/{count}件スキップ'
                    with st.expander(f'**{name}** `{email_addr}`　{badge}　📧 {count}件'):
                        render_sender_mails(db, email_addr, skip_senders, rules)

            if selected_to_skip:
                if st.button(f'🚫 選択した {len(selected_to_skip)} 件を「返信しない」に移動',
                             type='primary', key='move_to_skip'):
                    for addr in selected_to_skip:
                        if addr not in skip_senders:
                            skip_senders.append(addr)
                        db.hide_emails_by_sender(addr)  # 未対応・保存済みを非表示に
                    save_rules(rules)
                    st.success(f'{len(selected_to_skip)} 件を返信しないに移動したにゃ！未対応から非表示にしたにゃ')
                    st.rerun()

            st.divider()

            # ── 返信しないリスト
            st.markdown(f'### 🚫 返信しない（{len(skip_list)}件）')
            if not skip_list:
                st.caption('なしにゃ')
            else:
                sel_c3, sel_c4 = st.columns([1, 1])
                with sel_c3:
                    if st.button('全選択', key='sel_all_skip'):
                        for s in skip_list:
                            st.session_state[f"to_reply_{s['sender_email']}"] = True
                        st.rerun()
                with sel_c4:
                    if st.button('全解除', key='desel_all_skip'):
                        for s in skip_list:
                            st.session_state[f"to_reply_{s['sender_email']}"] = False
                        st.rerun()

            selected_to_reply = []
            for s in skip_list:
                email_addr    = s['sender_email']
                name          = s['sender_name'] or email_addr
                count         = s['mail_count']
                skipped_count = s.get('skipped_count', 0) or 0
                rule_skip     = any(p.lower() in email_addr.lower() for p in skip_senders)

                c_chk, c_info = st.columns([0.05, 0.95])
                with c_chk:
                    if st.checkbox('', key=f"to_reply_{email_addr}"):
                        selected_to_reply.append(email_addr)
                with c_info:
                    badge = '🚫 ルール登録済み' if rule_skip else f'⏭ 全件スキップ済み'
                    with st.expander(f'**{name}** `{email_addr}`　{badge}　📧 {count}件'):
                        render_sender_mails(db, email_addr, skip_senders, rules)

            if selected_to_reply:
                if st.button(f'✅ 選択した {len(selected_to_reply)} 件を「返信する」に戻す',
                             type='secondary', key='move_to_reply'):
                    skip['senders'] = [x for x in skip_senders
                                       if not any(x.lower() in addr.lower() or addr.lower() in x.lower()
                                                  for addr in selected_to_reply)]
                    save_rules(rules)
                    for addr in selected_to_reply:
                        db.show_emails_by_sender(addr)  # 非表示を解除して再表示
                    st.success('返信するに戻して、未対応に再表示したにゃ！')
                    st.rerun()

            st.divider()

            # ── 全メール一覧（確認用）
            st.markdown('### 📬 全受信メール一覧（確認用）')
            st.info(
                'DBに保存されているすべてのメールをここで確認できるにゃ。\n\n'
                '- **ステータスで絞り込む** — 未対応・保存済み・送信済み・スキップでフィルタできるにゃ\n'
                '- **非表示メールも含めて表示** — 「返信しない」に登録して非表示になったメールも一覧できるにゃ\n'
                '- 過去に取得したメール全件がここで見られるにゃ（fetch.pyで取得した分すべてにゃ）'
            )

            all_emails_query = db.get_emails_by_status
            show_hidden = st.toggle('非表示メールも含めて表示', key='show_hidden', value=False)
            all_emails = []
            for status in ['pending', 'saved', 'sent', 'skipped']:
                all_emails.extend(db.get_emails_by_status(status, include_hidden=show_hidden))
            all_emails.sort(key=lambda x: x.get('received_at', ''), reverse=True)

            status_filter = st.multiselect(
                'ステータスで絞り込む',
                options=['📬 未対応', '💾 保存済み', '✅ 送信済み', '⏭ スキップ'],
                default=['📬 未対応', '💾 保存済み', '✅ 送信済み', '⏭ スキップ'],
                key='all_mail_filter'
            )
            status_map = {'📬 未対応': 'pending', '💾 保存済み': 'saved',
                          '✅ 送信済み': 'sent', '⏭ スキップ': 'skipped'}
            allowed = {status_map[k] for k in status_filter}

            shown = [e for e in all_emails if e.get('status') in allowed]
            st.caption(f'{len(shown)} 件表示中')

            for email in shown:
                s_icon = {'pending':'📬','saved':'💾','sent':'✅','skipped':'⏭'}.get(email['status'],'')
                cat    = email.get('category','その他')
                c_icon = CATEGORY_ICONS.get(cat,'⚪')
                label  = (f"{s_icon} `{email.get('received_at','')}` "
                          f"{c_icon} **{email.get('subject','(件名なし)')}** "
                          f"— {email.get('sender_name','') or email.get('sender_email','')}")
                with st.expander(label):
                    st.caption(f"送信者: {email.get('sender_email','')}　カテゴリ: {cat}")
                    st.text(email.get('body','')[:500] + ('...' if len(email.get('body','')) > 500 else ''))

    # ══════════════════════════════════════════
    # タブ2: 返信しないキーワード
    # ══════════════════════════════════════════
    with cfg_tab3:
        skip = rules.setdefault('skip', {'senders': [], 'subject_keywords': []})
        skip_senders  = skip.setdefault('senders', [])
        skip_keywords = skip.setdefault('subject_keywords', [])

        st.info(
            '**件名にキーワードが含まれるメールを自動でスキップするにゃ**\n\n'
            '例: `[自動返信]` `不在通知` `自動応答` などを登録しておくと、'
            '自動返信メールをスキップして未対応に表示されなくなるにゃ。\n\n'
            '送信者アドレスでスキップしたい場合は「送信者管理」タブから「返信しない」に登録するにゃ。'
        )
        to_del_k = []
        for i, item in enumerate(list(skip_keywords)):
            c1, c2 = st.columns([5, 1])
            c1.code(item)
            if c2.button('削除', key=f"del_sk_{i}"):
                to_del_k.append(item)
        if to_del_k:
            skip['subject_keywords'] = [x for x in skip_keywords if x not in to_del_k]
            save_rules(rules)
            st.rerun()

        new_k = st.text_input('追加', key='add_skip_kw', placeholder='自動返信 / 不在通知')
        if st.button('＋ 追加', key='btn_add_skip_kw'):
            if new_k.strip() and new_k.strip() not in skip_keywords:
                skip_keywords.append(new_k.strip())
                save_rules(rules)
                st.rerun()

    # ══════════════════════════════════════════
    # タブ3: カテゴリルール
    # ══════════════════════════════════════════
    with cfg_tab4:
        st.info(
            '**メールのカテゴリ自動判定ルールを設定するにゃ**\n\n'
            'メール取得時に送信者アドレスや件名のキーワードでカテゴリを自動付与するにゃ。\n'
            'カテゴリは未対応タブの色アイコンで区別され、AIへの返信生成ヒントにもなるにゃ。\n\n'
            '- **送信者パターン** — `@client.co.jp` や `billing@` のように部分一致で指定するにゃ\n'
            '- **件名キーワード** — `請求書` `依頼` など含まれていればマッチするにゃ\n'
            '- 上のカテゴリほど優先度が高いにゃ（スキップルールが最優先にゃ）'
        )
        categories = rules.get('categories', {})
        cat_names  = [c for c in categories if c != 'その他']

        for cat in cat_names:
            cat_rules = categories.setdefault(cat, {'senders': [], 'subject_keywords': []})
            icon = CATEGORY_ICONS.get(cat, '⚪')
            with st.expander(f'{icon} {cat}'):
                col1, col2 = st.columns(2)
                with col1:
                    cat_rules['senders'] = render_list_editor(
                        '送信者パターン', cat_rules.get('senders', []),
                        f'cat_sender_{cat}', '@example.com / billing@ など'
                    )
                with col2:
                    cat_rules['subject_keywords'] = render_list_editor(
                        '件名キーワード', cat_rules.get('subject_keywords', []),
                        f'cat_kw_{cat}', '依頼 / 請求書 など'
                    )

        if st.button('💾 カテゴリルールを保存', type='primary', use_container_width=True):
            save_rules(rules)
            st.success('保存したにゃ！')
            st.rerun()

        with st.expander('rules.yaml の内容を見る'):
            st.code(
                yaml.dump(rules, allow_unicode=True, default_flow_style=False, sort_keys=False),
                language='yaml'
            )

    # ══════════════════════════════════════════
    # タブ4: アカウント管理
    # ══════════════════════════════════════════
    with cfg_tab_account:
        render_account_tab()


# ─────────────────────────────────────────────
# メイン
# ─────────────────────────────────────────────

def main():
    # ── タイトル＋接続アカウント表示
    title_col, account_col = st.columns([3, 2])
    with title_col:
        st.title('✉️ Mail Manager')
    with account_col:
        gmail = get_gmail()
        if gmail:
            account_email = gmail.get_account_email()
            if account_email:
                st.markdown(
                    f'<div style="text-align:right;padding-top:1.2rem;">'
                    f'<span style="background:#f0fdf4;border:1.5px solid #bbf7d0;'
                    f'border-radius:20px;padding:.35rem .9rem;font-size:.82rem;'
                    f'color:#15803d;font-weight:600;">📧 {account_email}</span></div>',
                    unsafe_allow_html=True
                )

    # ── 使い方ガイド
    with st.expander('📖 使い方ガイド（はじめて使うときに読んでにゃ）'):
        st.markdown('''
**基本の流れにゃ：**

1. **📥 メールを取得する** — 上の「メールを取得する」パネルを開いてボタンを押すにゃ。GmailからAIが返信案を自動生成して保存するにゃ。
2. **📬 未対応タブ** — AIが作った返信案を確認・編集してそのまま送信できるにゃ。後回しにしたいときは「編集を保存」で保存済みに移動するにゃ。
3. **💾 保存済みタブ** — 一度保存した返信案をまとめて確認・送信できるにゃ。
4. **✅ 送信済みタブ** — 送信した内容の履歴を見られるにゃ。

**送信者の管理（⚙️設定タブ）にゃ：**

- **返信する** — この一覧にいる人のメールが「未対応」に表示されるにゃ
- **返信しない** — ここに登録すると「未対応」から非表示になって自動スキップされるにゃ（メルマガ・通知メールなど）
- **全受信メール一覧** — 設定タブの一番下にあるにゃ。DBに保存されている全メールをステータスでフィルタして確認できるにゃ

**よくある操作にゃ：**
- チェックボックスで複数選択 → 「まとめて送信」ができるにゃ
- 「📨 元のメールを見る」で受信した本文を確認できるにゃ
- 「⏭ スキップ」で今は対応しないメールを後回しにできるにゃ（設定タブ→送信者管理→返信しないに移動するとより効果的にゃ）
        ''')

    db     = get_db()
    counts = db.get_counts()

    pending_n = counts.get('pending', 0)
    saved_n   = counts.get('saved',   0)
    sent_n    = counts.get('sent',    0)

    # ── ヘッダー統計カード
    m1, m2, m3 = st.columns(3)
    with m1:
        st.markdown(f'''<div class="stat-card stat-pending">
            <div class="stat-num">{pending_n}</div>
            <div class="stat-label">📬 未対応</div>
        </div>''', unsafe_allow_html=True)
    with m2:
        st.markdown(f'''<div class="stat-card stat-saved">
            <div class="stat-num">{saved_n}</div>
            <div class="stat-label">💾 保存済み</div>
        </div>''', unsafe_allow_html=True)
    with m3:
        st.markdown(f'''<div class="stat-card stat-sent">
            <div class="stat-num">{sent_n}</div>
            <div class="stat-label">✅ 送信済み</div>
        </div>''', unsafe_allow_html=True)

    st.divider()

    # ── メール取得パネル
    with st.expander('📥 メールを取得する', expanded=(pending_n == 0 and saved_n == 0)):
        fetch_tab1, fetch_tab2, fetch_tab3 = st.tabs(['🆕 新着（未読）', '📅 過去のメール', '🔍 カスタム検索'])

        cwd = os.path.dirname(os.path.abspath(__file__))

        def run_fetch(args_extra: list, spinner_msg: str):
            env = os.environ.copy()
            env['PYTHONIOENCODING'] = 'utf-8'
            with st.spinner(spinner_msg):
                result = subprocess.run(
                    [sys.executable, 'fetch.py'] + args_extra,
                    capture_output=True, text=True, encoding='utf-8',
                    errors='replace', cwd=cwd, env=env
                )
            if result.returncode == 0:
                st.success('取得完了にゃ！')
                st.rerun()
            else:
                st.error(f'エラーにゃ:\n{result.stderr[:400]}')

        with fetch_tab1:
            st.caption('Gmailの未読メール（受信トレイ）を取得して振り分けるにゃ')
            c1, c2 = st.columns([1, 3])
            with c1:
                limit_new = st.number_input('最大件数', min_value=1, max_value=500,
                                            value=50, key='limit_new')
            if st.button('🔄 新着メールを取得', type='primary', key='fetch_new'):
                run_fetch(['--limit', str(limit_new)], 'Gmail から取得中...')

        with fetch_tab2:
            st.caption('過去に受信したメールをさかのぼって取得するにゃ')
            c1, c2, c3 = st.columns([1, 1, 2])
            with c1:
                days = st.number_input('過去N日分', min_value=1, max_value=365,
                                       value=7, key='fetch_days')
            with c2:
                limit_past = st.number_input('最大件数', min_value=1, max_value=500,
                                             value=100, key='limit_past')
            with c3:
                fetch_all = st.checkbox('受信トレイ全件（未読以外も含む）', key='fetch_all')

            if st.button('📅 過去のメールを取得', type='primary', key='fetch_past'):
                if fetch_all:
                    run_fetch(['--all', '--limit', str(limit_past)],
                              f'受信トレイ全件を取得中（上限 {limit_past} 件）...')
                else:
                    run_fetch(['--days', str(days), '--limit', str(limit_past)],
                              f'過去 {days} 日分を取得中...')

        with fetch_tab3:
            st.caption('Gmailの検索クエリを直接指定するにゃ（上級者向け）')
            st.markdown('例: `from:boss@example.com` / `subject:請求書` / `after:2024/01/01`')
            custom_query = st.text_input('Gmailクエリ', value='in:inbox',
                                         key='custom_query',
                                         placeholder='from:example@gmail.com after:2024/01/01')
            limit_custom = st.number_input('最大件数', min_value=1, max_value=500,
                                           value=50, key='limit_custom')
            if st.button('🔍 検索して取得', type='primary', key='fetch_custom'):
                if custom_query.strip():
                    run_fetch(['--query', custom_query.strip(), '--limit', str(limit_custom)],
                              f'クエリで取得中: {custom_query}...')
                else:
                    st.warning('クエリを入力してにゃ')

    st.divider()

    # ── タブ
    tab1, tab2, tab3, tab4 = st.tabs([
        f'📬 未対応 ({pending_n})',
        f'💾 保存済み ({saved_n})',
        f'✅ 送信済み ({sent_n})',
        '⚙️ 設定',
    ])

    with tab1:
        st.caption('AIが生成した返信案を確認・編集して送信するにゃ。後で返信したいときは「💾 編集を保存」で保存済みタブに移動するにゃ。')
        render_tab(db, 'pending', 'pending')

    with tab2:
        st.caption('「編集を保存」で後回しにしたメールがここに入るにゃ。準備ができたら編集して送信するにゃ。')
        render_tab(db, 'saved', 'saved')

    with tab4:
        render_settings()

    with tab3:
        st.caption('送信した返信の履歴を確認できるにゃ。返信内容は「返信内容を見る」を展開して確認できるにゃ。')
        sent_emails = db.get_emails_by_status('sent')
        if not sent_emails:
            st.info('送信済みのメールはありませんにゃ')
        else:
            for email in sent_emails:
                category = email.get('category', 'その他')
                with st.container():
                    st.markdown(f'''<div class="mail-card mail-card-{category}">
                        <span class="mail-category cat-{category}">{category}</span>
                        &nbsp;<span style="color:#16a34a;font-size:.78rem;font-weight:600;">✅ 送信済み</span>
                        <div class="mail-subject">📧 {email.get('subject','(件名なし)')}</div>
                        <div class="mail-meta">
                            👤 {email.get('sender_name','')}
                            &lt;{email.get('sender_email','')}&gt;
                            &nbsp;·&nbsp; 🕐 {email.get('received_at','')}
                        </div>
                    </div>''', unsafe_allow_html=True)
                    with st.expander('返信内容を見る'):
                        st.text(email.get('reply_text', ''))


if __name__ == '__main__':
    main()
