import google.generativeai as genai
import base64
from typing import Optional
from app.utils.config import config
from app.utils.logger import setup_logger
from app.exceptions.custom_exceptions import GeminiAPIError

logger = setup_logger(__name__)

class GeminiService:
    """Gemini API操作サービス"""
    
    def __init__(self):
        self.api_key = config.GEMINI_API_KEY
        self.model_name = config.GEMINI_MODEL
        
        if not self.api_key:
            raise GeminiAPIError("GEMINI_API_KEY is not set")
        
        # Gemini APIの初期化
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel(self.model_name)
        
        logger.info(f"Gemini service initialized with model: {self.model_name}")
    
    def summarize_pdf(self, pdf_base64: str, filename: str, custom_prompt: Optional[str] = None) -> str:
        """
        PDFファイルを要約する
        
        Args:
            pdf_base64: Base64エンコードされたPDFデータ
            filename: ファイル名
            custom_prompt: カスタムプロンプト（オプション）
            
        Returns:
            要約テキスト
        """
        try:
            # デフォルトプロンプト
            default_prompt = f"""このPDFファイルの内容を基に、発表内容を日本語で300字から500字程度で簡潔にまとめてください。
            
重要なポイント：
- 主要なトピックや結論を含める
- 技術的な内容は分かりやすく説明する
- 読み手にとって価値のある情報を抽出する
- 簡潔で読みやすい形式にまとめる

ファイル名: {filename}"""
            
            prompt = custom_prompt or default_prompt
            
            # PDFデータの準備
            pdf_data = {
                'mime_type': 'application/pdf',
                'data': pdf_base64
            }
            
            logger.info(f"Starting PDF summarization for file: {filename}")
            
            # Gemini APIに送信
            response = self.model.generate_content([prompt, pdf_data])
            
            if not response.text:
                logger.error("Gemini API returned empty response")
                raise GeminiAPIError("Gemini API returned empty response")
            
            summary = response.text.strip()
            logger.info(f"Successfully generated summary (length: {len(summary)} chars)")
            logger.debug(f"Summary preview: {summary[:100]}...")
            
            return summary
            
        except Exception as e:
            logger.error(f"PDF summarization failed: {str(e)}")
            if "google.generativeai" in str(type(e)):
                # Gemini固有のエラー
                raise GeminiAPIError(f"Gemini API error: {str(e)}")
            else:
                # その他のエラー
                raise GeminiAPIError(f"PDF summarization failed: {str(e)}")
    
    def test_connection(self) -> bool:
        """
        Gemini APIへの接続テスト
        
        Returns:
            接続成功時はTrue
        """
        try:
            test_prompt = "こんにちは、テストです。"
            response = self.model.generate_content(test_prompt)
            
            if response.text:
                logger.info("Gemini API connection test successful")
                return True
            else:
                logger.warning("Gemini API connection test returned empty response")
                return False
                
        except Exception as e:
            logger.error(f"Gemini API connection test failed: {str(e)}")
            return False