import google.generativeai as genai
import base64
from typing import Optional, Dict, Any, Tuple
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
    
    def summarize_pdf(self, pdf_base64: str, filename: str, custom_prompt: Optional[str] = None) -> Tuple[str, Dict[str, Any]]:
        """
        PDFファイルを要約する
        
        Args:
            pdf_base64: Base64エンコードされたPDFデータ
            filename: ファイル名
            custom_prompt: カスタムプロンプト（オプション）
            
        Returns:
            要約テキストとトークン情報のタプル
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
            
            # トークンカウント
            token_count = self._count_tokens_with_pdf(prompt, pdf_base64)
            
            # Gemini APIに送信
            response = self.model.generate_content([prompt, pdf_data])
            
            if not response.text:
                logger.error("Gemini API returned empty response")
                raise GeminiAPIError("Gemini API returned empty response")
            
            summary = response.text.strip()
            
            # 使用トークン情報を取得
            usage_metadata = self._extract_usage_metadata(response)
            
            logger.info(f"Successfully generated summary (length: {len(summary)} chars)")
            logger.debug(f"Summary preview: {summary[:100]}...")
            
            return summary, {
                'input_tokens': token_count,
                'output_tokens': usage_metadata.get('output_tokens', 0),
                'total_tokens': token_count + usage_metadata.get('output_tokens', 0)
            }
            
        except Exception as e:
            logger.error(f"PDF summarization failed: {str(e)}")
            if "google.generativeai" in str(type(e)):
                # Gemini固有のエラー
                raise GeminiAPIError(f"Gemini API error: {str(e)}")
            else:
                # その他のエラー
                raise GeminiAPIError(f"PDF summarization failed: {str(e)}")
    
    def summarize_pdf_and_audio(self, pdf_base64: str, pdf_filename: str, audio_data: bytes, audio_filename: str, custom_prompt: Optional[str] = None) -> Tuple[str, Dict[str, Any]]:
        """
        PDFファイルと音声ファイルを同時に処理して議事録まとめを作成
        
        Args:
            pdf_base64: Base64エンコードされたPDFデータ
            pdf_filename: PDFファイル名
            audio_data: 音声ファイルのバイナリデータ
            audio_filename: 音声ファイル名
            custom_prompt: カスタムプロンプト（オプション）
            
        Returns:
            議事録まとめテキストとトークン情報のタプル
        """
        try:
            # Files APIを使用して音声ファイルをアップロード
            logger.info(f"Uploading audio file: {audio_filename}")
            
            # 一時ファイルとして保存してからアップロード
            import tempfile
            import os
            
            with tempfile.NamedTemporaryFile(delete=False, suffix=f".{audio_filename.split('.')[-1]}") as temp_file:
                temp_file.write(audio_data)
                temp_file_path = temp_file.name
            
            try:
                # Files APIを使用してアップロード
                audio_file = genai.upload_file(
                    path=temp_file_path,
                    display_name=audio_filename
                )
                
                # アップロード完了を待機
                import time
                while audio_file.state.name == "PROCESSING":
                    logger.info("Waiting for audio file processing...")
                    time.sleep(2)
                    audio_file = genai.get_file(audio_file.name)
                
                if audio_file.state.name == "FAILED":
                    raise GeminiAPIError(f"Audio file upload failed: {audio_file.state.name}")
                
                logger.info(f"Audio file uploaded successfully: {audio_file.name}")
                
                # デフォルトプロンプト
                default_prompt = f"""以下のスライドPDFと録音ファイルを基に、議事録のわかりやすいまとめを日本語で作成してください。

スライドPDF: {pdf_filename}
録音ファイル: {audio_filename}

まとめの要件：
- スライドの内容と録音での議論を統合した包括的なまとめ
- 主要な議論ポイントと決定事項を明確に記載
- 質疑応答があれば重要な内容を含める
- 次のアクションアイテムがあれば記載
- 読みやすい構造（見出し、箇条書きなどを活用）

以下の順序で情報を整理してください：
1. 概要
2. 主要な議論ポイント
3. 決定事項・合意事項
4. 次のアクションアイテム（あれば）"""

                prompt = custom_prompt or default_prompt
                
                # PDFデータの準備
                pdf_data = {
                    'mime_type': 'application/pdf',
                    'data': pdf_base64
                }
                
                logger.info(f"Starting PDF and audio summarization")
                
                # トークンカウント
                pdf_token_count = self._count_tokens_with_pdf(prompt, pdf_base64)
                audio_token_count = self._count_tokens_with_audio_file(audio_file)
                total_input_tokens = pdf_token_count + audio_token_count
                
                # Gemini APIに送信（PDF、音声ファイル、プロンプトを同時に）
                response = self.model.generate_content([prompt, pdf_data, audio_file])
                
                if not response.text:
                    logger.error("Gemini API returned empty response")
                    raise GeminiAPIError("Gemini API returned empty response")
                
                summary = response.text.strip()
                
                # 使用トークン情報を取得
                usage_metadata = self._extract_usage_metadata(response)
                
                logger.info(f"Successfully generated meeting summary (length: {len(summary)} chars)")
                
                return summary, {
                    'input_tokens': total_input_tokens,
                    'output_tokens': usage_metadata.get('output_tokens', 0),
                    'total_tokens': total_input_tokens + usage_metadata.get('output_tokens', 0),
                    'pdf_tokens': pdf_token_count,
                    'audio_tokens': audio_token_count
                }
                
            finally:
                # ファイルをクリーンアップ
                try:
                    os.unlink(temp_file_path)
                    logger.info(f"Deleted temporary file: {temp_file_path}")
                except Exception as e:
                    logger.warning(f"Failed to delete temporary file: {e}")
                
                try:
                    genai.delete_file(audio_file.name)
                    logger.info(f"Deleted uploaded audio file: {audio_file.name}")
                except Exception as e:
                    logger.warning(f"Failed to delete audio file: {e}")
            
        except Exception as e:
            logger.error(f"PDF and audio summarization failed: {str(e)}")
            if "google.generativeai" in str(type(e)):
                # Gemini固有のエラー
                raise GeminiAPIError(f"Gemini API error: {str(e)}")
            else:
                # その他のエラー
                raise GeminiAPIError(f"PDF and audio summarization failed: {str(e)}")
    
    def _count_tokens_with_pdf(self, prompt: str, pdf_base64: str) -> int:
        """PDFを含むコンテンツのトークン数をカウント"""
        try:
            pdf_data = {
                'mime_type': 'application/pdf',
                'data': pdf_base64
            }
            
            response = self.model.count_tokens([prompt, pdf_data])
            return response.total_tokens
        except Exception as e:
            logger.warning(f"Token counting failed: {e}")
            return 0
    
    def _count_tokens_with_audio_file(self, audio_file) -> int:
        """音声ファイルのトークン数をカウント"""
        try:
            response = self.model.count_tokens([audio_file])
            return response.total_tokens
        except Exception as e:
            logger.warning(f"Audio token counting failed: {e}")
            return 0
    
    def _extract_usage_metadata(self, response) -> Dict[str, Any]:
        """レスポンスから使用トークン情報を抽出"""
        try:
            # Gemini APIレスポンスから使用量メタデータを取得
            if hasattr(response, 'usage_metadata'):
                return {
                    'output_tokens': getattr(response.usage_metadata, 'candidates_token_count', 0),
                    'prompt_tokens': getattr(response.usage_metadata, 'prompt_token_count', 0),
                    'total_tokens': getattr(response.usage_metadata, 'total_token_count', 0)
                }
            return {}
        except Exception as e:
            logger.warning(f"Failed to extract usage metadata: {e}")
            return {}
    
    def _get_audio_mime_type(self, filename: str) -> str:
        """ファイル名から音声ファイルのMIMEタイプを推定"""
        filename_lower = filename.lower()
        if filename_lower.endswith('.mp3'):
            return 'audio/mp3'
        elif filename_lower.endswith('.wav'):
            return 'audio/wav'
        elif filename_lower.endswith('.m4a'):
            return 'audio/mp4'
        elif filename_lower.endswith('.aac'):
            return 'audio/aac'
        elif filename_lower.endswith('.ogg'):
            return 'audio/ogg'
        elif filename_lower.endswith('.flac'):
            return 'audio/flac'
        else:
            return 'audio/mpeg'  # デフォルト
    
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