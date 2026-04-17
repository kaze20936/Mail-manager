import logging
import yaml
from config import Config

logger = logging.getLogger(__name__)


class Classifier:
    def __init__(self):
        self.rules = self._load_rules()

    def _load_rules(self) -> dict:
        try:
            with open(Config.RULES_PATH, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"rules.yaml 読み込み失敗: {e}")
            return {'categories': {'その他': {}}}

    def classify(self, sender_email: str, subject: str) -> str:
        sender_lower = sender_email.lower()
        subject_lower = subject.lower()

        # skip（返信しない）を最優先でチェック
        skip_rules = self.rules.get('skip', {})
        for pattern in skip_rules.get('senders', []):
            if pattern.lower() in sender_lower:
                logger.info(f"[skip] 送信者マッチ: {pattern}")
                return 'skip'
        for keyword in skip_rules.get('subject_keywords', []):
            if keyword.lower() in subject_lower:
                logger.info(f"[skip] 件名マッチ: {keyword}")
                return 'skip'

        # カテゴリ分類
        categories = self.rules.get('categories', {})
        for category, rules in categories.items():
            if category == 'その他' or not rules:
                continue

            for pattern in rules.get('senders', []):
                if pattern.lower() in sender_lower:
                    logger.info(f"[{category}] 送信者マッチ: {pattern}")
                    return category

            for keyword in rules.get('subject_keywords', []):
                if keyword.lower() in subject_lower:
                    logger.info(f"[{category}] 件名マッチ: {keyword}")
                    return category

        return 'その他'
