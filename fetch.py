#!/usr/bin/env python3
"""
fetch.py — メールを取得してAI返信文を生成し、DBに保存する

使い方:
  python fetch.py                        # 新着（未読）のみ
  python fetch.py --days 7               # 過去7日分
  python fetch.py --days 30              # 過去30日分
  python fetch.py --query "in:inbox"     # カスタムクエリ
  python fetch.py --all                  # 受信トレイ全件（最大件数まで）
  python fetch.py --days 30 --limit 200  # 過去30日・最大200件
"""
import argparse
import logging
import os
import sys
from datetime import datetime, timedelta

# Windowsコンソールのエンコードをutf-8に強制
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from config import Config
from database import Database
from gmail_client import GmailClient
from imap_client import ImapClient
from classifier import Classifier
from reply_generator import ReplyGenerator

os.makedirs('logs', exist_ok=True)

_stream_handler = logging.StreamHandler(sys.stdout)
_stream_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(Config.LOG_PATH, encoding='utf-8'),
        _stream_handler,
    ]
)
logger = logging.getLogger(__name__)


def build_query(args) -> tuple[str, int]:
    """引数からGmailクエリと取得上限を生成"""
    if args.query:
        return args.query, args.limit

    if args.all:
        return 'in:inbox -from:me', args.limit

    if args.days:
        since = (datetime.now() - timedelta(days=args.days)).strftime('%Y/%m/%d')
        return f'in:inbox after:{since} -from:me', args.limit

    # デフォルト: 未読のみ
    return Config.GMAIL_QUERY, args.limit


def process_emails(emails: list, db: Database, classifier: Classifier, generator: ReplyGenerator):
    new_count  = 0
    skip_count = 0
    err_count  = 0

    for email_data in emails:
        gmail_id = email_data['gmail_id']

        if db.email_exists(gmail_id):
            skip_count += 1
            continue

        try:
            category = classifier.classify(
                email_data['sender_email'],
                email_data.get('subject', '')
            )
            email_data['category'] = category

            if category in ('skip', '通知・自動送信'):
                logger.info(f"スキップ: {email_data.get('subject', '')}")
                email_data['reply_text'] = ''
                email_id = db.save_email(email_data)
                if email_id:
                    db.update_status(email_id, 'skipped')
                skip_count += 1
                continue

            logger.info(f"返信生成中 [{category}]: {email_data.get('subject', '')}")
            email_data['reply_text'] = generator.generate(email_data)

            db.save_email(email_data)
            new_count += 1
            logger.info(f"保存完了: {email_data.get('subject', '')}")

        except Exception as e:
            logger.error(f"処理エラー ({gmail_id}): {e}")
            err_count += 1

    return new_count, skip_count, err_count


def main():
    parser = argparse.ArgumentParser(description='Mail Manager - メール取得・AI返信生成')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--days',  type=int,  metavar='N',
                       help='過去N日分のメールを取得（例: --days 30）')
    group.add_argument('--all',   action='store_true',
                       help='受信トレイの全メールを取得（未読フィルタなし）')
    group.add_argument('--query', type=str,  metavar='QUERY',
                       help='カスタムGmailクエリ（例: --query "from:boss@example.com"）')
    parser.add_argument('--limit', type=int, default=Config.MAX_EMAILS_PER_FETCH,
                        metavar='N', help=f'取得上限（デフォルト: {Config.MAX_EMAILS_PER_FETCH}）')
    args = parser.parse_args()

    query, limit = build_query(args)

    if args.days:
        mode = f'過去 {args.days} 日分'
    elif args.all:
        mode = '受信トレイ全件'
    elif args.query:
        mode = f'カスタムクエリ: {args.query}'
    else:
        mode = '新着（未読）'

    logger.info(f'=== Mail Manager Fetch 開始 [{mode}] 上限:{limit}件 ===')
    logger.info(f'クエリ: {query}')

    db     = Database()

    # アクティブアカウントのプロバイダーに合わせてクライアントを選ぶにゃ
    _active = db.get_active_account()
    if _active and _active.get('provider', 'gmail') != 'gmail':
        gmail = ImapClient(
            username  = _active['email'],
            password  = _active.get('password', ''),
            imap_host = _active.get('imap_host', ''),
            imap_port = int(_active.get('imap_port', 993)),
            smtp_host = _active.get('smtp_host', ''),
            smtp_port = int(_active.get('smtp_port', 587)),
        )
    else:
        _token = _active['token_json'] if _active else None
        gmail  = GmailClient(token_json=_token)
    classifier = Classifier()
    generator  = ReplyGenerator()

    emails = gmail.fetch_new_emails(max_results=limit, query=query)
    logger.info(f'取得メール数: {len(emails)}')

    new_count, skip_count, err_count = process_emails(emails, db, classifier, generator)

    # 取得ログを記録するにゃ
    triggered_by = 'auto' if os.getenv('GITHUB_ACTIONS') else 'manual'
    account_email = _active['email'] if _active else ''
    try:
        db.client.table('fetch_log').insert({
            'new_count':     new_count,
            'skip_count':    skip_count,
            'err_count':     err_count,
            'account_email': account_email,
            'triggered_by':  triggered_by,
        }).execute()
    except Exception as e:
        logger.warning(f'ログ記録失敗にゃ: {e}')

    summary = (
        f'\n取得完了！ [{mode}]\n'
        f'  新規: {new_count} 件\n'
        f'  スキップ: {skip_count} 件\n'
        f'  エラー: {err_count} 件\n'
        f'\n→ python -m streamlit run app.py でWebUIを開いてにゃ！\n'
    )
    logger.info(f'=== 完了 新規:{new_count} スキップ:{skip_count} エラー:{err_count} ===')
    print(summary)


if __name__ == '__main__':
    main()
