import google.generativeai as genai
import base64
from typing import Optional, Tuple, Any
from app.utils.config import config
from app.utils.logger import setup_logger
from app.exceptions.custom_exceptions import GeminiAPIError, FileNotFoundError
from app.models.notion_models import NotionFile
import io
import mimetypes
import time
import requests # Notionからのファイルダウンロードに必要
import tempfile
import os

logger = setup_logger(__name__)

class GeminiService:
    """Gemini API操作サービス"""
    
    def __init__(self):
        self.api_key = config.GEMINI_API_KEY
        self.model_name = config.GEMINI_MODEL
        
        if not self.api_key:
            raise GeminiAPIError("GEMINI_API_KEY is not set")
        
        genai.configure(api_key=self.api_key)
        self.client = genai.GenerativeModel(self.model_name)

        logger.info(f"Gemini service initialized with model: {self.model_name}")

    def _log_token_usage(self, response: Any, operation_name: str) -> None:
        """Gemini APIのトークン使用量をログに出力"""
        try:
            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                usage = response.usage_metadata
                total_tokens = getattr(usage, 'total_token_count', 'N/A')
                prompt_tokens = getattr(usage, 'prompt_token_count', 'N/A')
                candidates_tokens = getattr(usage, 'candidates_token_count', 'N/A')
                logger.info(
                    f"{operation_name} - Token usage: Total={total_tokens}, "
                    f"Prompt={prompt_tokens}, Candidates={candidates_tokens}"
                )
            else:
                logger.info(f"{operation_name} - Token usage metadata not available in response.")
        except Exception as e:
            logger.warning(f"Failed to log token usage for {operation_name}: {str(e)}")

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
            default_prompt = f"""このPDFファイルの内容を基に、発表内容を日本語で300字から500字程度で簡潔にまとめてください。
            
重要なポイント：
- 主要なトピックや結論を含める
- 技術的な内容は分かりやすく説明する
- 読み手にとって価値のある情報を抽出する
- 簡潔で読みやすい形式にまとめる

ファイル名: {filename}"""
            
            prompt = custom_prompt or default_prompt
            
            pdf_part = {
                'mime_type': 'application/pdf',
                'data': pdf_base64
            }
            
            logger.info(f"Starting PDF summarization for file: {filename}")
            
            response = self.client.generate_content([prompt, pdf_part])
            self._log_token_usage(response, "PDF Summarization")
            
            if not response.text:
                logger.error("Gemini API returned empty response for PDF summarization")
                raise GeminiAPIError("Gemini API returned empty response for PDF summarization")
            
            summary = response.text.strip()
            logger.info(f"Successfully generated PDF summary (length: {len(summary)} chars)")
            logger.debug(f"Summary preview: {summary[:100]}...")
            
            return summary
            
        except Exception as e:
            logger.error(f"PDF summarization failed: {str(e)}")
            if "usage_metadata" in str(e).lower():
                raise GeminiAPIError(f"Gemini API error (possibly token related) during PDF summarization: {str(e)}")
            elif "google.generativeai" in str(type(e)):
                raise GeminiAPIError(f"Gemini API error during PDF summarization: {str(e)}")
            else:
                raise GeminiAPIError(f"PDF summarization failed: {str(e)}")
    
    def _upload_file_to_gemini(self, file_content: bytes, file_name: str, mime_type: Optional[str] = None) -> genai.types.File:
        """ファイルをGemini Files APIにアップロードする"""
        try:
            logger.info(f"Uploading file to Gemini: {file_name}")
            
            if not mime_type:
                mime_type, _ = mimetypes.guess_type(file_name)
                if not mime_type:
                    if file_name.lower().endswith(('.mp3', '.wav', '.aac', '.ogg')):
                        mime_type = 'audio/mpeg'
                    elif file_name.lower().endswith(('.mp4', '.mov', '.avi')):
                        mime_type = 'video/mp4'
                    else:
                        mime_type = 'application/octet-stream'
                    logger.info(f"MIME type for {file_name} guessed as {mime_type}")

            with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{file_name}") as tmp_file:
                tmp_file.write(file_content)
                tmp_file_path = tmp_file.name
            
            logger.info(f"Uploading temporary file {tmp_file_path} to Gemini for {file_name}")
            uploaded_file = genai.upload_file(path=tmp_file_path, display_name=file_name, mime_type=mime_type)
            logger.info(f"File {file_name} uploaded to Gemini. URI: {uploaded_file.uri}, Name: {uploaded_file.name}")

            while uploaded_file.state.name == "PROCESSING":
                logger.info(f"File {uploaded_file.name} is still processing. Waiting...")
                time.sleep(5)
                uploaded_file = genai.get_file(name=uploaded_file.name)
            
            if uploaded_file.state.name == "FAILED":
                logger.error(f"File upload failed for {uploaded_file.name}. State: {uploaded_file.state.name}")
                raise GeminiAPIError(f"File upload failed: {uploaded_file.name}")
            
            logger.info(f"File {uploaded_file.name} is ready. State: {uploaded_file.state.name}")
            
            try:
                import os
                os.remove(tmp_file_path)
                logger.info(f"Temporary file {tmp_file_path} deleted.")
            except OSError as e:
                logger.warning(f"Could not delete temporary file {tmp_file_path}: {e}")

            return uploaded_file

        except Exception as e:
            logger.error(f"File upload to Gemini failed for {file_name}: {str(e)}")
            if 'tmp_file_path' in locals() and os.path.exists(tmp_file_path):
                try:
                    os.remove(tmp_file_path)
                except OSError:
                    pass
            raise GeminiAPIError(f"File upload to Gemini failed for {file_name}: {str(e)}")

    def _download_notion_file_content(self, notion_file: NotionFile) -> Tuple[bytes, str]:
        """NotionFileオブジェクトからファイルコンテンツをダウンロードする"""
        try:
            logger.info(f"Downloading file from Notion: {notion_file.name} from {notion_file.url}")
            response = requests.get(notion_file.url, timeout=60)
            response.raise_for_status()
            logger.info(f"Successfully downloaded file: {notion_file.name} ({len(response.content)} bytes)")
            return response.content, notion_file.name
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to download Notion file {notion_file.name}: {str(e)}")
            raise FileNotFoundError(f"Failed to download file from Notion: {notion_file.name} - {str(e)}")

    def generate_minutes_from_pdf_and_audio(
        self,
        pdf_base64: str,
        pdf_filename: str,
        audio_notion_file: NotionFile,
        custom_prompt: Optional[str] = None
    ) -> str:
        """
        PDFファイルと音声ファイルから議事録を生成する

        Args:
            pdf_base64: Base64エンコードされたPDFデータ
            pdf_filename: PDFファイル名
            audio_notion_file: 音声ファイルのNotionFileオブジェクト
            custom_prompt: カスタムプロンプト（オプション）

        Returns:
            議事録テキスト
        """
        try:
            audio_content, audio_filename = self._download_notion_file_content(audio_notion_file)
            
            # NotionFileのtypeプロパティが不適切なので、ファイル名から判定する
            audio_mime_type, _ = mimetypes.guess_type(audio_filename)
            if not audio_mime_type:
                if audio_filename.lower().endswith('.mp3'): audio_mime_type = 'audio/mpeg'
                elif audio_filename.lower().endswith('.wav'): audio_mime_type = 'audio/wav'
                elif audio_filename.lower().endswith('.m4a'): audio_mime_type = 'audio/mp4'
                elif audio_filename.lower().endswith('.ogg'): audio_mime_type = 'audio/ogg'
                else: audio_mime_type = 'audio/mpeg'  # デフォルトを音声ファイルに設定
            logger.info(f"Using MIME type for {audio_filename}: {audio_mime_type}")

            gemini_audio_file = self._upload_file_to_gemini(audio_content, audio_filename, mime_type=audio_mime_type)

            default_prompt = f"""以下のPDFファイルと音声ファイルの内容を総合的に分析し、会議やプレゼンテーションの議事録を作成してください。
議事録には、以下の要素を含めてください：
- 会議の目的と主要な議題
- 発表された主要なポイントや提案
- 議論された内容と、その結果や決定事項
- 今後のアクションアイテムや担当者（もしあれば）
- 全体を通して、具体的で分かりやすい言葉で記述してください。

PDFファイル名: {pdf_filename}
音声ファイル名: {audio_filename}
"""
            prompt = custom_prompt or default_prompt

            pdf_part = {
                'mime_type': 'application/pdf',
                'data': pdf_base64
            }

            logger.info(f"Starting minutes generation using PDF ({pdf_filename}) and Audio ({audio_filename})")
            response = self.client.generate_content(
                [prompt, pdf_part, gemini_audio_file]
            )
            self._log_token_usage(response, "Minutes Generation (PDF+Audio)")

            if not response.text:
                logger.error("Gemini API returned empty response for minutes generation")
                raise GeminiAPIError("Gemini API returned empty response for minutes generation")

            minutes_text = response.text.strip()
            logger.info(f"Successfully generated minutes (length: {len(minutes_text)} chars)")
            return minutes_text

        except FileNotFoundError as e:
            raise
        except Exception as e:
            logger.error(f"Minutes generation failed: {str(e)}")
            if "google.generativeai" in str(type(e)):
                raise GeminiAPIError(f"Gemini API error during minutes generation: {str(e)}")
            else:
                raise GeminiAPIError(f"Minutes generation failed: {str(e)}")

    def test_connection(self) -> bool:
        """
        Gemini APIへの接続テスト
        
        Returns:
            接続成功時はTrue
        """
        try:
            test_prompt = "こんにちは、テストです。"
            response = self.client.generate_content(test_prompt)
            self._log_token_usage(response, "Connection Test")
            
            if response.text:
                logger.info("Gemini API connection test successful")
                return True
            else:
                logger.warning("Gemini API connection test returned empty response")
                return False
                
        except Exception as e:
            logger.error(f"Gemini API connection test failed: {str(e)}")
            return False