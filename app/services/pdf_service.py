import requests
import base64
from typing import Tuple
from app.utils.logger import setup_logger
from app.models.notion_models import NotionFile
from app.exceptions.custom_exceptions import PDFProcessingError

logger = setup_logger(__name__)

class PDFService:
    """PDF処理サービス"""
    
    def __init__(self):
        self.max_file_size = 50 * 1024 * 1024  # 50MB制限
        logger.info("PDF service initialized")
    
    def download_and_encode_pdf(self, notion_file: NotionFile) -> Tuple[str, str]:
        """
        Notion PDFファイルをダウンロードしてBase64エンコードする
        
        Args:
            notion_file: NotionFileオブジェクト
            
        Returns:
            Tuple[base64_data, filename]
        """
        try:
            logger.info(f"Downloading PDF: {notion_file.name} from {notion_file.url}")
            
            # PDFファイルをダウンロード
            response = requests.get(notion_file.url, timeout=60)
            
            if response.status_code != 200:
                raise PDFProcessingError(
                    f"Failed to download PDF: HTTP {response.status_code}"
                )
            
            # ファイルサイズチェック
            content_length = len(response.content)
            if content_length > self.max_file_size:
                raise PDFProcessingError(
                    f"PDF file too large: {content_length} bytes (max: {self.max_file_size})"
                )
            
            logger.info(f"Successfully downloaded PDF: {content_length} bytes")
            
            # Base64エンコード
            base64_data = base64.b64encode(response.content).decode('utf-8')
            
            logger.info(f"Successfully encoded PDF to base64: {len(base64_data)} chars")
            
            return base64_data, notion_file.name
            
        except requests.exceptions.Timeout:
            logger.error("PDF download timeout")
            raise PDFProcessingError("PDF download timeout")
        
        except requests.exceptions.RequestException as e:
            logger.error(f"PDF download failed: {str(e)}")
            raise PDFProcessingError(f"PDF download failed: {str(e)}")
        
        except Exception as e:
            logger.error(f"PDF processing failed: {str(e)}")
            raise PDFProcessingError(f"PDF processing failed: {str(e)}")
    
    def validate_pdf_content(self, content: bytes) -> bool:
        """
        PDFファイルの内容を検証する
        
        Args:
            content: PDFファイルのバイナリデータ
            
        Returns:
            有効なPDFファイルの場合True
        """
        try:
            # PDFファイルの基本的な検証（PDFヘッダーの確認）
            if content.startswith(b'%PDF-'):
                logger.info("Valid PDF header detected")
                return True
            else:
                logger.warning("Invalid PDF header")
                return False
                
        except Exception as e:
            logger.error(f"PDF validation failed: {str(e)}")
            return False
    
    def get_pdf_info(self, base64_data: str) -> dict:
        """
        PDFファイルの基本情報を取得
        
        Args:
            base64_data: Base64エンコードされたPDFデータ
            
        Returns:
            PDFファイル情報の辞書
        """
        try:
            # Base64デコード
            pdf_bytes = base64.b64decode(base64_data)
            
            info = {
                'size_bytes': len(pdf_bytes),
                'size_mb': round(len(pdf_bytes) / (1024 * 1024), 2),
                'is_valid_pdf': self.validate_pdf_content(pdf_bytes),
                'base64_length': len(base64_data)
            }
            
            logger.info(f"PDF info: {info}")
            return info
            
        except Exception as e:
            logger.error(f"Failed to get PDF info: {str(e)}")
            return {
                'error': str(e),
                'is_valid_pdf': False
            }