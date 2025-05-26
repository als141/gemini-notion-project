class NotionGeminiError(Exception):
    """基底カスタム例外クラス"""
    pass

class NotionAPIError(NotionGeminiError):
    """Notion API関連のエラー"""
    def __init__(self, message: str, status_code: int = None):
        super().__init__(message)
        self.status_code = status_code

class GeminiAPIError(NotionGeminiError):
    """Gemini API関連のエラー"""
    def __init__(self, message: str, status_code: int = None):
        super().__init__(message)
        self.status_code = status_code

class PDFProcessingError(NotionGeminiError):
    """PDF処理関連のエラー"""
    pass

class PageNotFoundError(NotionGeminiError):
    """ページが見つからない場合のエラー"""
    pass

class FileNotFoundError(NotionGeminiError):
    """ファイルが見つからない場合のエラー"""
    pass

class ConfigurationError(NotionGeminiError):
    """設定関連のエラー"""
    pass