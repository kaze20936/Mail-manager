#!/usr/bin/env python3
"""
check_setup.py — セットアップ状況を確認するスクリプトにゃ
使い方: python check_setup.py
"""
import os
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from dotenv import load_dotenv
load_dotenv()

OK   = '[OK]'
WARN = '[--]'
NG   = '[NG]'

results = []

def check(label, ok, detail=''):
    icon = OK if ok else NG
    results.append((icon, label, detail))
    print(f'  {icon}  {label}' + (f'  ({detail})' if detail else ''))

print()
print('=' * 50)
print('  Mail Manager セットアップ確認にゃ')
print('=' * 50)
print()

# ── 1. 必須ファイル
print('[1] 必須ファイルにゃ')
check('credentials.json',
      os.path.exists('credentials.json'),
      'なければ Google Cloud Console からダウンロードにゃ')
check('token.json（初回認証後に自動生成）',
      os.path.exists('token.json'),
      'なければ python fetch.py を実行するとブラウザが開くにゃ')
check('.env',
      os.path.exists('.env'),
      'なければ .env.example をコピーして作るにゃ')

print()

# ── 2. 環境変数（.env の中身）
print('[2] APIキー設定にゃ')

anthropic_key = os.getenv('ANTHROPIC_API_KEY', '')
check('ANTHROPIC_API_KEY',
      bool(anthropic_key and not anthropic_key.startswith('your_')),
      'console.anthropic.com で発行にゃ')

notion_token = os.getenv('NOTION_TOKEN', '')
notion_ok = bool(notion_token and not notion_token.startswith('your_'))
icon = OK if notion_ok else WARN
results.append((icon, 'NOTION_TOKEN（任意）', ''))
print(f'  {icon}  NOTION_TOKEN（任意・未設定でも動くにゃ）')

notion_page = os.getenv('NOTION_PARENT_PAGE_ID', '')
notion_page_ok = bool(notion_page and not notion_page.startswith('your_'))
icon = OK if notion_page_ok else WARN
print(f'  {icon}  NOTION_PARENT_PAGE_ID（任意・未設定でも動くにゃ）')

print()

# ── 3. Anthropic APIキーの疎通確認
print('[3] Anthropic API 接続確認にゃ')
if anthropic_key and not anthropic_key.startswith('your_'):
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=anthropic_key)
        r = client.messages.create(
            model='claude-haiku-4-5-20251001',
            max_tokens=10,
            messages=[{'role': 'user', 'content': 'hi'}]
        )
        check('Anthropic API 接続', True, 'Claude に繋がったにゃ')
    except Exception as e:
        check('Anthropic API 接続', False, str(e)[:60])
else:
    print(f'  {NG}  ANTHROPIC_API_KEY が未設定のためスキップにゃ')

print()

# ── 4. Gmail token 確認
print('[4] Gmail 認証状態にゃ')
if os.path.exists('token.json'):
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        SCOPES = [
            'https://www.googleapis.com/auth/gmail.readonly',
            'https://www.googleapis.com/auth/gmail.send',
        ]
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
        if creds.valid:
            check('Gmail トークン', True, '有効にゃ')
        elif creds.expired and creds.refresh_token:
            creds.refresh(Request())
            check('Gmail トークン', True, '期限切れ→更新済みにゃ')
        else:
            check('Gmail トークン', False, '無効。token.json を削除して再認証にゃ')
    except Exception as e:
        check('Gmail トークン', False, str(e)[:60])
else:
    print(f'  {NG}  token.json なし → python fetch.py で認証してにゃ')

print()

# ── 5. まとめ
ng_count = sum(1 for r in results if r[0] == NG)
print('=' * 50)
if ng_count == 0:
    print('  全項目OKにゃ！python fetch.py で開始できるにゃ')
else:
    print(f'  [NG] が {ng_count} 件あるにゃ。上の案内を見て設定してにゃ')
print('=' * 50)
print()

# ── 6. キー取得先リファレンス
print('[キー取得先まとめにゃ]')
print()
print('  ANTHROPIC_API_KEY')
print('    https://console.anthropic.com/')
print('    → API Keys → Create Key')
print()
print('  credentials.json（Gmail OAuth）')
print('    https://console.cloud.google.com/')
print('    → APIとサービス → 認証情報 → OAuth2クライアントID')
print('    → デスクトップアプリ → ダウンロード → credentials.json にリネーム')
print()
print('  NOTION_TOKEN（任意）')
print('    https://www.notion.so/my-integrations')
print('    → 新しいインテグレーション作成 → シークレットをコピー')
print()
print('  NOTION_PARENT_PAGE_ID（任意）')
print('    Notionで管理したいページを開く')
print('    → URLの https://notion.so/xxxxxxxx の xxxxxxxx 部分にゃ')
print()
