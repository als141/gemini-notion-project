from typing import Dict, Any
from app.services.notion_service import NotionService
from app.services.gemini_service import GeminiService
from app.services.pdf_service import PDFService
from app.utils.config import config
from app.utils.logger import setup_logger
from app.exceptions.custom_exceptions import (
    NotionGeminiError, 
    PageNotFoundError, 
    FileNotFoundError,
    ConfigurationError
)
from app.models.notion_models import NotionFile

logger = setup_logger(__name__)

class PDFSummaryHandler:
    """PDF要約処理のメインハンドラー"""
    
    def __init__(self):
        try:
            self.notion_service = NotionService()
            self.gemini_service = GeminiService()
            self.pdf_service = PDFService()
            logger.info("PDF Summary Handler initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize PDF Summary Handler: {str(e)}")
            raise ConfigurationError(f"Service initialization failed: {str(e)}")
    
    def process_pdf_summary(self, unique_id: str) -> Dict[str, Any]:
        """
        PDFサマリー処理のメイン関数
        
        Args:
            unique_id: NotionページのユニークID
            
        Returns:
            処理結果の辞書
        """
        try:
            logger.info(f"Starting PDF summary process for unique_id: {unique_id}")
            
            # 1. ユニークIDの検証と変換
            try:
                unique_id_int = int(unique_id)
            except ValueError:
                raise ValueError(f"Invalid unique_id format: {unique_id}. Must be a number.")
            
            # 2. NotionページIDの検索
            page_id = self.notion_service.find_page_by_unique_id(unique_id_int)
            if not page_id:
                raise PageNotFoundError(f"Page not found for unique_id: {unique_id}")
            
            # 3. ページ詳細の取得
            page = self.notion_service.get_page_details(page_id)
            page_title = page.get_title()
            logger.info(f"Processing page: {page_title} (ID: {page_id})")
            
            # 4. PDFファイルの取得
            try:
                pdf_file = self.notion_service.get_pdf_file_from_page(page)
                logger.info(f"Found PDF file: {pdf_file.name}")
            except FileNotFoundError as e:
                raise FileNotFoundError(f"PDF file not found in page '{page_title}': {str(e)}")
            
            # 5. PDFダウンロードとエンコード
            pdf_base64, filename = self.pdf_service.download_and_encode_pdf(pdf_file)
            
            # 6. PDF情報の取得（デバッグ用）
            pdf_info = self.pdf_service.get_pdf_info(pdf_base64)
            logger.info(f"PDF info: {pdf_info}")
            
            # 7. Geminiで要約生成
            summary = self.gemini_service.summarize_pdf(pdf_base64, filename)
            logger.info(f"Generated summary (length: {len(summary)} chars)")
            
            # 8. Notionページに要約を保存
            self._upsert_content_in_notion(page_id, summary, config.SUMMARY_TOGGLE_H3_TITLE)
            
            # 9. 成功レスポンス
            result = {
                'success': True,
                'message': f'PDF summary completed for page "{page_title}" (unique_id: {unique_id})',
                'details': {
                    'page_id': page_id,
                    'page_title': page_title,
                    'pdf_filename': filename,
                    'summary_length': len(summary),
                    'pdf_info': pdf_info
                }
            }
            
            logger.info(f"PDF summary process completed successfully: {result['message']}")
            return result
            
        except NotionGeminiError:
            # カスタム例外はそのまま再発生
            raise
        except Exception as e:
            logger.error(f"Unexpected error in PDF summary process: {str(e)}")
            raise NotionGeminiError(f"PDF summary process failed: {str(e)}")
    
    def process_pdf_and_audio_minutes(self, unique_id: str) -> Dict[str, Any]:
        """
        PDFと音声ファイルから議事録を生成し、Notionに保存する処理
        """
        try:
            logger.info(f"Starting PDF and audio minutes process for unique_id: {unique_id}")

            try:
                unique_id_int = int(unique_id)
            except ValueError:
                raise ValueError(f"Invalid unique_id format: {unique_id}. Must be a number.")

            page_id = self.notion_service.find_page_by_unique_id(unique_id_int)
            if not page_id:
                raise PageNotFoundError(f"Page not found for unique_id: {unique_id}")

            page = self.notion_service.get_page_details(page_id)
            page_title = page.get_title()
            logger.info(f"Processing page for minutes: {page_title} (ID: {page_id})")

            try:
                pdf_file_obj = self.notion_service.get_pdf_file_from_page(page)
                logger.info(f"Found PDF file: {pdf_file_obj.name}")
            except FileNotFoundError as e:
                raise FileNotFoundError(f"PDF file not found in page '{page_title}': {str(e)}")
            
            pdf_base64, pdf_filename = self.pdf_service.download_and_encode_pdf(pdf_file_obj)

            try:
                audio_file_obj = self.notion_service.get_audio_file_from_page(page)
                logger.info(f"Found audio file: {audio_file_obj.name}")
            except FileNotFoundError as e:
                raise FileNotFoundError(f"Audio file not found in page '{page_title}': {str(e)}")

            minutes_text = self.gemini_service.generate_minutes_from_pdf_and_audio(
                pdf_base64, pdf_filename, audio_file_obj
            )
            logger.info(f"Generated minutes (length: {len(minutes_text)} chars)")

            self._upsert_content_in_notion(page_id, minutes_text, config.MINUTES_TOGGLE_H3_TITLE)
            
            result = {
                'success': True,
                'message': f'PDF and audio minutes processing completed for page "{page_title}" (unique_id: {unique_id})',
                'details': {
                    'page_id': page_id,
                    'page_title': page_title,
                    'pdf_filename': pdf_filename,
                    'audio_filename': audio_file_obj.name,
                    'minutes_length': len(minutes_text)
                }
            }
            logger.info(f"PDF and audio minutes process completed successfully: {result['message']}")
            return result

        except NotionGeminiError:
            raise
        except Exception as e:
            logger.error(f"Error in PDF and audio minutes processing: {str(e)}")
            raise NotionGeminiError(f"PDF and audio minutes processing failed: {str(e)}")

    def _upsert_content_in_notion(self, page_id: str, content: str, toggle_title: str) -> None:
        """
        Notionページにコンテンツを指定されたトグルブロック内に保存する（2000文字で分割）
        
        Args:
            page_id: ページID
            content: 保存するテキストコンテンツ
            toggle_title: トグルブロックのタイトル
        """
        try:
            logger.info(f"Saving content (toggle: '{toggle_title}') to Notion page: {page_id}")
            
            page_children = self.notion_service.get_block_children(page_id)
            callout_block_id = None
            
            for block in page_children.results:
                if block.get('type') == 'callout':
                    callout_block_id = block['id']
                    logger.info(f"Found existing callout block: {callout_block_id}")
                    break
            
            if not callout_block_id:
                logger.info("Creating new callout block")
                callout_data = {
                    'object': 'block',
                    'type': 'callout',
                    'callout': {
                        'rich_text': [],
                        'icon': {'type': 'emoji', 'emoji': '💡'}, # 共通アイコン、必要なら変更
                        'color': 'gray_background'
                    }
                }
                response = self.notion_service.append_block_children(page_id, [callout_data])
                callout_block_id = response['results'][0]['id']
                logger.info(f"Created new callout block: {callout_block_id}")
            
            callout_children = self.notion_service.get_block_children(callout_block_id)
            toggle_h3_block_id = None
            
            for block in callout_children.results:
                if (block.get('type') == 'heading_3' and 
                    block.get('heading_3', {}).get('is_toggleable') == True):
                    rich_text_list = block.get('heading_3', {}).get('rich_text', [])
                    if rich_text_list and rich_text_list[0].get('text', {}).get('content') == toggle_title:
                        toggle_h3_block_id = block['id']
                        logger.info(f"Found existing toggle H3 block ('{toggle_title}'): {toggle_h3_block_id}")
                        break
            
            if not toggle_h3_block_id:
                logger.info(f"Creating new toggle H3 block: {toggle_title}")
                h3_data = {
                    'object': 'block',
                    'type': 'heading_3',
                    'heading_3': {
                        'rich_text': [{'type': 'text', 'text': {'content': toggle_title}}],
                        'is_toggleable': True,
                        'color': 'default'
                    }
                }
                response = self.notion_service.append_block_children(callout_block_id, [h3_data])
                toggle_h3_block_id = response['results'][0]['id']
                logger.info(f"Created new toggle H3 block ('{toggle_title}'): {toggle_h3_block_id}")
            
            h3_children = self.notion_service.get_block_children(toggle_h3_block_id)
            if h3_children.results:
                logger.info(f"Deleting {len(h3_children.results)} existing child blocks from toggle '{toggle_title}'")
                for child_block in h3_children.results:
                    self.notion_service.delete_block(child_block['id'])
            
            # コンテンツを2000文字のチャンクに分割
            MAX_LENGTH = 2000
            content_chunks = [content[i:i + MAX_LENGTH] for i in range(0, len(content), MAX_LENGTH)]
            
            paragraph_blocks_data = []
            for chunk in content_chunks:
                paragraph_blocks_data.append({
                    'object': 'block',
                    'type': 'paragraph',
                    'paragraph': {
                        'rich_text': [{'type': 'text', 'text': {'content': chunk}}],
                        'color': 'default'
                    }
                })
            
            if paragraph_blocks_data:
                self.notion_service.append_block_children(toggle_h3_block_id, paragraph_blocks_data)
            
            logger.info(f"Successfully saved content (toggle: '{toggle_title}') to Notion")
            
        except Exception as e:
            logger.error(f"Failed to save content (toggle: '{toggle_title}') to Notion: {str(e)}")
            raise NotionGeminiError(f"Failed to save content to Notion (toggle: '{toggle_title}'): {str(e)}")

    def health_check(self) -> Dict[str, Any]:
        """
        サービスのヘルスチェック
        
        Returns:
            ヘルスチェック結果
        """
        results = {
            'notion_api': False,
            'gemini_api': False,
            'overall': False
        }
        
        try:
            # Gemini API テスト
            results['gemini_api'] = self.gemini_service.test_connection()
            
            # Notion API テスト（設定の確認）
            if self.notion_service.api_key and self.notion_service.database_id:
                results['notion_api'] = True
            
            results['overall'] = results['notion_api'] and results['gemini_api']
            
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
        
        return results