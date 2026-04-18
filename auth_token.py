"""
別のGmailアカウントでログインしてtoken.jsonを生成するスクリプトにゃ
使い方: python auth_token.py
"""
import os
import sys

# Windows コンソールの文字コードを UTF-8 に強制にゃ
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.send',
]

base = os.path.dirname(os.path.abspath(__file__))
creds_path = os.path.join(base, 'credentials.json')
token_path = os.path.join(base, 'token.json')

if not os.path.exists(creds_path):
    print(f'credentials.json が見つからないにゃ: {creds_path}')
    sys.exit(1)

print('ブラウザが開くにゃ。Googleアカウントでログインしてにゃ！')
flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
creds = flow.run_local_server(port=0)

with open(token_path, 'w', encoding='utf-8') as f:
    f.write(creds.to_json())

print(f'\n認証完了にゃ！ token.json を保存したにゃ: {token_path}')
print('\n以下の内容をアプリの「Gmailアカウント追加」に貼り付けてにゃ:')
print('-' * 60)
with open(token_path, 'r', encoding='utf-8') as f:
    print(f.read())
print('-' * 60)
