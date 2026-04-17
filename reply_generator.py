import logging
import os
import anthropic
from config import Config

logger = logging.getLogger(__name__)

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), 'templates')

FILENAME_MAP = {
    '仕事依頼':     '仕事依頼.txt',
    '問い合わせ':   '問い合わせ.txt',
    '請求・支払い': '請求支払い.txt',
    '通知・自動送信': 'その他.txt',
    'その他':       'その他.txt',
}

SYSTEM_PROMPT = """あなたはビジネスメールの返信文を生成するアシスタントです。
以下のルールで返信文を作成してください：
- 丁寧かつ簡潔な日本語
- 具体的な日時・金額・固有名詞が不明な箇所は【　】でプレースホルダーを残す
- 署名・会社名は含めない
- テンプレートの構成を参考にしつつ、メール内容に自然に合わせる
- 返信文のみを出力（説明や前置きは不要）"""


class ReplyGenerator:
    def __init__(self):
        self.client = anthropic.Anthropic(api_key=Config.ANTHROPIC_API_KEY)

    def _load_template(self, category: str) -> str:
        filename = FILENAME_MAP.get(category, 'その他.txt')
        filepath = os.path.join(TEMPLATE_DIR, filename)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception:
            return '【送信者名】様\n\nご連絡いただきありがとうございます。\n\n【返信内容】\n\nよろしくお願いいたします。'

    def generate(self, email_data: dict) -> str:
        category    = email_data.get('category', 'その他')
        template    = self._load_template(category)
        sender_name = email_data.get('sender_name', '') or email_data.get('sender_email', '')

        prompt = f"""以下のメールへの返信文を生成してください。

カテゴリ: {category}
送信者: {sender_name}
件名: {email_data.get('subject', '')}

【受信メール本文】
{email_data.get('body', '')}

【参考テンプレート】
{template}

テンプレートをベースに、メール内容に合わせた自然な返信文を生成してください。"""

        try:
            response = self.client.messages.create(
                model=Config.CLAUDE_MODEL,
                max_tokens=1024,
                system=SYSTEM_PROMPT,
                messages=[{'role': 'user', 'content': prompt}]
            )
            return response.content[0].text.strip()

        except Exception as e:
            logger.error(f"Claude API エラー: {e} → テンプレートで代替")
            display_name = sender_name.split('<')[0].strip() or '担当者'
            return template.replace('【送信者名】', display_name)
