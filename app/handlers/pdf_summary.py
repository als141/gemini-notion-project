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
            self._upsert_summary_in_notion(page_id, summary)
            
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
    
    def _upsert_summary_in_notion(self, page_id: str, summary: str) -> None:
        """
        Notionページに要約を保存する
        
        Args:
            page_id: ページID
            summary: 要約テキスト
        """
        try:
            logger.info(f"Saving summary to Notion page: {page_id}")
            
            # 1. ページの子ブロックを取得してコールアウトを探す
            page_children = self.notion_service.get_block_children(page_id)
            callout_block_id = None
            
            for block in page_children.results:
                if block.get('type') == 'callout':
                    callout_block_id = block['id']
                    logger.info(f"Found existing callout block: {callout_block_id}")
                    break
            
            # 2. コールアウトブロックがない場合は作成
            if not callout_block_id:
                logger.info("Creating new callout block")
                callout_data = {
                    'object': 'block',
                    'type': 'callout',
                    'callout': {
                        'rich_text': [],
                        'icon': {'type': 'emoji', 'emoji': '💡'},
                        'color': 'gray_background'
                    }
                }
                
                response = self.notion_service.append_block_children(page_id, [callout_data])
                callout_block_id = response['results'][0]['id']
                logger.info(f"Created new callout block: {callout_block_id}")
            
            # 3. コールアウト内のトグルH3を探す
            callout_children = self.notion_service.get_block_children(callout_block_id)
            toggle_h3_block_id = None
            
            for block in callout_children.results:
                if (block.get('type') == 'heading_3' and 
                    block.get('heading_3', {}).get('is_toggleable') == True):
                    rich_text = block.get('heading_3', {}).get('rich_text', [])
                    if rich_text and rich_text[0].get('text', {}).get('content') == config.SUMMARY_TOGGLE_H3_TITLE:
                        toggle_h3_block_id = block['id']
                        logger.info(f"Found existing toggle H3 block: {toggle_h3_block_id}")
                        break
            
            # 4. トグルH3ブロックがない場合は作成
            if not toggle_h3_block_id:
                logger.info(f"Creating new toggle H3 block: {config.SUMMARY_TOGGLE_H3_TITLE}")
                h3_data = {
                    'object': 'block',
                    'type': 'heading_3',
                    'heading_3': {
                        'rich_text': [{
                            'type': 'text',
                            'text': {'content': config.SUMMARY_TOGGLE_H3_TITLE}
                        }],
                        'is_toggleable': True,
                        'color': 'default'
                    }
                }
                
                response = self.notion_service.append_block_children(callout_block_id, [h3_data])
                toggle_h3_block_id = response['results'][0]['id']
                logger.info(f"Created new toggle H3 block: {toggle_h3_block_id}")
            
            # 5. トグルH3の既存の子ブロックを削除
            h3_children = self.notion_service.get_block_children(toggle_h3_block_id)
            if h3_children.results:
                logger.info(f"Deleting {len(h3_children.results)} existing child blocks")
                for child_block in h3_children.results:
                    self.notion_service.delete_block(child_block['id'])
            
            # 6. 新しい要約パラグラフを追加
            paragraph_data = {
                'object': 'block',
                'type': 'paragraph',
                'paragraph': {
                    'rich_text': [{
                        'type': 'text',
                        'text': {'content': summary}
                    }],
                    'color': 'default'
                }
            }
            
            self.notion_service.append_block_children(toggle_h3_block_id, [paragraph_data])
            logger.info("Successfully saved summary to Notion")
            
        except Exception as e:
            logger.error(f"Failed to save summary to Notion: {str(e)}")
            raise NotionGeminiError(f"Failed to save summary to Notion: {str(e)}")
    
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