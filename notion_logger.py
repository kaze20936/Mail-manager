import logging
import os
from notion_client import Client
from config import Config

logger = logging.getLogger(__name__)

DB_ID_FILE = 'notion_db_id.txt'


class NotionLogger:
    def __init__(self):
        if not Config.NOTION_TOKEN:
            logger.warning("Notion トークン未設定 → Notion連携スキップ")
            self.client = None
            self.database_id = None
            return

        self.client = Client(auth=Config.NOTION_TOKEN)
        self.database_id = self._get_or_create_database()

    def _get_or_create_database(self) -> str | None:
        # 既存のDB IDを使い回す
        if os.path.exists(DB_ID_FILE):
            with open(DB_ID_FILE) as f:
                db_id = f.read().strip()
            logger.info(f"既存 Notion DB 使用: {db_id}")
            return db_id

        if not Config.NOTION_PARENT_PAGE_ID:
            logger.warning("Notion 親ページID未設定 → DB作成スキップ")
            return None

        try:
            res = self.client.databases.create(
                parent={'type': 'page_id', 'page_id': Config.NOTION_PARENT_PAGE_ID},
                title=[{'type': 'text', 'text': {'content': 'Mail Manager - 送信履歴'}}],
                properties={
                    '件名': {'title': {}},
                    '送信者': {'rich_text': {}},
                    'カテゴリ': {
                        'select': {
                            'options': [
                                {'name': '仕事依頼',      'color': 'orange'},
                                {'name': '問い合わせ',    'color': 'blue'},
                                {'name': '請求・支払い',  'color': 'red'},
                                {'name': '通知・自動送信','color': 'gray'},
                                {'name': 'その他',        'color': 'default'},
                            ]
                        }
                    },
                    'ステータス': {
                        'select': {
                            'options': [
                                {'name': '返信済み', 'color': 'green'},
                                {'name': 'スキップ', 'color': 'gray'},
                            ]
                        }
                    },
                    '返信プレビュー': {'rich_text': {}},
                    '受信日時': {'rich_text': {}},
                }
            )
            db_id = res['id']
            with open(DB_ID_FILE, 'w') as f:
                f.write(db_id)
            logger.info(f"Notion DB 作成完了: {db_id}")
            return db_id

        except Exception as e:
            logger.error(f"Notion DB 作成失敗: {e}")
            return None

    def log_sent(self, email_data: dict) -> bool:
        if not self.client or not self.database_id:
            return False

        try:
            preview = (email_data.get('reply_text') or '')[:200]
            sender_str = f"{email_data.get('sender_name', '')} <{email_data.get('sender_email', '')}>"

            self.client.pages.create(
                parent={'database_id': self.database_id},
                properties={
                    '件名': {
                        'title': [{'text': {'content': email_data.get('subject', '(件名なし)')}}]
                    },
                    '送信者': {
                        'rich_text': [{'text': {'content': sender_str}}]
                    },
                    'カテゴリ': {
                        'select': {'name': email_data.get('category', 'その他')}
                    },
                    'ステータス': {
                        'select': {'name': '返信済み'}
                    },
                    '返信プレビュー': {
                        'rich_text': [{'text': {'content': preview}}]
                    },
                    '受信日時': {
                        'rich_text': [{'text': {'content': email_data.get('received_at', '')}}]
                    },
                }
            )
            logger.info(f"Notion 記録完了: {email_data.get('subject', '')}")
            return True

        except Exception as e:
            logger.error(f"Notion 記録失敗: {e}")
            return False
