import os
from typing import Optional
from dotenv import load_dotenv

# .env ファイルがあれば読み込む（ローカル開発用）
load_dotenv()

class Config:
    """アプリケーション設定クラス"""
    
    # Notion API 設定
    NOTION_API_KEY: str = os.getenv('NOTION_API_KEY', '')
    NOTION_DATABASE_ID: str = os.getenv('NOTION_DATABASE_ID', '')
    NOTION_API_VERSION: str = '2022-06-28'
    
    # Gemini API 設定
    GEMINI_API_KEY: str = os.getenv('GEMINI_API_KEY', '')
    GEMINI_MODEL: str = os.getenv('GEMINI_MODEL', 'gemini-2.5-flash-preview-05-20')
    
    # Notion プロパティ名
    UNIQUE_ID_PROPERTY_NAME: str = os.getenv('UNIQUE_ID_PROPERTY_NAME', 'ID')
    FILE_PROPERTY_NAME: str = os.getenv('FILE_PROPERTY_NAME', 'スライドPDF')
    AUDIO_FILE_PROPERTY_NAME: str = os.getenv('AUDIO_FILE_PROPERTY_NAME', '録音ファイル')
    
    # その他の設定
    SUMMARY_TOGGLE_H3_TITLE: str = os.getenv('SUMMARY_TOGGLE_H3_TITLE', 'Summary')
    MINUTES_TOGGLE_H3_TITLE: str = os.getenv('MINUTES_TOGGLE_H3_TITLE', '議事録')
    
    @classmethod
    def validate(cls) -> None:
        """必須設定の検証"""
        required_vars = [
            ('NOTION_API_KEY', cls.NOTION_API_KEY),
            ('GEMINI_API_KEY', cls.GEMINI_API_KEY),
        ]
        
        missing_vars = [name for name, value in required_vars if not value]
        
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

# 設定インスタンス
config = Config()

# 初期化時に設定を検証
try:
    config.validate()
except ValueError as e:
    print(f"Configuration warning: {e}")