import requests
import base64
from typing import Tuple
from app.utils.logger import setup_logger
from app.models.notion_models import NotionFile
from app.exceptions.custom_exceptions import PDFProcessingError

logger = setup_logger(__name__)

class PDFService:
    """PDF/音声ファイル処理サービス"""
    
    def __init__(self):
        self.max_file_size = 50 * 1024 * 1024  # 50MB制限
        self.max_audio_file_size = 500 * 1024 * 1024  # 500MB制限（音声ファイル用）
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
    
    def download_audio_file(self, notion_file: NotionFile) -> Tuple[bytes, str]:
        """
        Notion音声ファイルをダウンロードする
        
        Args:
            notion_file: NotionFileオブジェクト
            
        Returns:
            Tuple[audio_bytes, filename]
        """
        try:
            logger.info(f"Downloading audio file: {notion_file.name} from {notion_file.url}")
            
            # 音声ファイルをダウンロード
            response = requests.get(notion_file.url, timeout=300)  # 音声ファイルは長時間タイムアウト
            
            if response.status_code != 200:
                raise PDFProcessingError(
                    f"Failed to download audio file: HTTP {response.status_code}"
                )
            
            # ファイルサイズチェック
            content_length = len(response.content)
            if content_length > self.max_audio_file_size:
                raise PDFProcessingError(
                    f"Audio file too large: {content_length} bytes (max: {self.max_audio_file_size})"
                )
            
            logger.info(f"Successfully downloaded audio file: {content_length} bytes")
            
            return response.content, notion_file.name
            
        except requests.exceptions.Timeout:
            logger.error("Audio file download timeout")
            raise PDFProcessingError("Audio file download timeout")
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Audio file download failed: {str(e)}")
            raise PDFProcessingError(f"Audio file download failed: {str(e)}")
        
        except Exception as e:
            logger.error(f"Audio file processing failed: {str(e)}")
            raise PDFProcessingError(f"Audio file processing failed: {str(e)}")
    
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
    
    def validate_audio_content(self, content: bytes, filename: str) -> bool:
        """
        音声ファイルの内容を検証する
        
        Args:
            content: 音声ファイルのバイナリデータ
            filename: ファイル名
            
        Returns:
            有効な音声ファイルの場合True
        """
        try:
            filename_lower = filename.lower()
            
            # MP3ファイルの検証
            if filename_lower.endswith('.mp3') and (content.startswith(b'ID3') or content.startswith(b'\xff\xfb')):
                logger.info("Valid MP3 file detected")
                return True
            
            # WAVファイルの検証
            elif filename_lower.endswith('.wav') and content.startswith(b'RIFF'):
                logger.info("Valid WAV file detected")
                return True
            
            # M4Aファイルの検証
            elif filename_lower.endswith('.m4a') and b'ftyp' in content[:20]:
                logger.info("Valid M4A file detected")
                return True
            
            # その他の音声形式は基本的なサイズチェックのみ
            elif any(filename_lower.endswith(ext) for ext in ['.aac', '.ogg', '.flac']):
                if len(content) > 1000:  # 最低1KB以上
                    logger.info(f"Valid audio file detected: {filename}")
                    return True
            
            logger.warning(f"Invalid or unsupported audio file: {filename}")
            return False
                
        except Exception as e:
            logger.error(f"Audio validation failed: {str(e)}")
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
    
    def get_audio_info(self, audio_bytes: bytes, filename: str) -> dict:
        """
        音声ファイルの基本情報を取得
        
        Args:
            audio_bytes: 音声ファイルのバイナリデータ
            filename: ファイル名
            
        Returns:
            音声ファイル情報の辞書
        """
        try:
            info = {
                'filename': filename,
                'size_bytes': len(audio_bytes),
                'size_mb': round(len(audio_bytes) / (1024 * 1024), 2),
                'is_valid_audio': self.validate_audio_content(audio_bytes, filename),
                'file_type': filename.split('.')[-1].lower() if '.' in filename else 'unknown'
            }
            
            logger.info(f"Audio info: {info}")
            return info
            
        except Exception as e:
            logger.error(f"Failed to get audio info: {str(e)}")
            return {
                'error': str(e),
                'is_valid_audio': False
            }