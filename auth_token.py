"""
別のGmailアカウントでログインしてtoken.jsonを生成するスクリプトにゃ
使い方: python auth_token.py
"""
import os, json
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
    exit(1)

print('ブラウザが開くにゃ。切り替えたいGoogleアカウントでログインしてにゃ！')
flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
creds = flow.run_local_server(port=0)

with open(token_path, 'w') as f:
    f.write(creds.to_json())

print(f'\n認証完了にゃ！ token.json を保存したにゃ: {token_path}')
print('\nStreamlit Cloud に反映する場合は以下の内容を GMAIL_TOKEN_JSON に貼り付けてにゃ:')
print('-' * 60)
with open(token_path, 'r') as f:
    print(f.read())
print('-' * 60)
