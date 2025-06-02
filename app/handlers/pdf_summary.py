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
import re

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
            
            # 5. 録音ファイルの確認
            audio_file = self.notion_service.get_audio_file_from_page(page)
            has_audio = audio_file is not None
            
            if has_audio:
                logger.info(f"Found audio file: {audio_file.name}")
                # PDFと音声ファイルの両方を処理
                return self._process_pdf_and_audio_summary(
                    page_id, page_title, pdf_file, audio_file, unique_id
                )
            else:
                logger.info("No audio file found, processing PDF only")
                # PDFのみを処理
                return self._process_pdf_only_summary(
                    page_id, page_title, pdf_file, unique_id
                )
            
        except NotionGeminiError:
            # カスタム例外はそのまま再発生
            raise
        except Exception as e:
            logger.error(f"Unexpected error in PDF summary process: {str(e)}")
            raise NotionGeminiError(f"PDF summary process failed: {str(e)}")
    
    def _process_pdf_only_summary(self, page_id: str, page_title: str, pdf_file, unique_id: str) -> Dict[str, Any]:
        """PDFのみの要約処理"""
        try:
            # 6. PDFダウンロードとエンコード
            pdf_base64, filename = self.pdf_service.download_and_encode_pdf(pdf_file)
            
            # 7. PDF情報の取得（デバッグ用）
            pdf_info = self.pdf_service.get_pdf_info(pdf_base64)
            logger.info(f"PDF info: {pdf_info}")
            
            # 8. Geminiで要約生成（トークン情報付き）
            summary, token_info = self.gemini_service.summarize_pdf(pdf_base64, filename)
            logger.info(f"Generated summary (length: {len(summary)} chars)")
            logger.info(f"Token usage: {token_info}")
            
            # 9. Notionページに要約を保存
            self._upsert_summary_in_notion(page_id, summary)
            
            # 10. 成功レスポンス
            result = {
                'success': True,
                'message': f'PDF summary completed for page "{page_title}" (unique_id: {unique_id})',
                'details': {
                    'page_id': page_id,
                    'page_title': page_title,
                    'pdf_filename': filename,
                    'summary_length': len(summary),
                    'pdf_info': pdf_info,
                    'has_audio_file': False,
                    'token_usage': token_info
                }
            }
            
            logger.info(f"PDF summary process completed successfully: {result['message']}")
            return result
            
        except Exception as e:
            logger.error(f"PDF only summary failed: {str(e)}")
            raise NotionGeminiError(f"PDF only summary failed: {str(e)}")
    
    def _process_pdf_and_audio_summary(self, page_id: str, page_title: str, pdf_file, audio_file, unique_id: str) -> Dict[str, Any]:
        """PDFと音声ファイルの同時処理"""
        try:
            # 6. PDFダウンロードとエンコード
            pdf_base64, pdf_filename = self.pdf_service.download_and_encode_pdf(pdf_file)
            
            # 7. 音声ファイルダウンロード
            audio_bytes, audio_filename = self.pdf_service.download_audio_file(audio_file)
            
            # 8. ファイル情報の取得
            pdf_info = self.pdf_service.get_pdf_info(pdf_base64)
            audio_info = self.pdf_service.get_audio_info(audio_bytes, audio_filename)
            logger.info(f"PDF info: {pdf_info}")
            logger.info(f"Audio info: {audio_info}")
            
            # 9. PDFのみの要約生成（既存機能）
            pdf_summary, pdf_token_info = self.gemini_service.summarize_pdf(pdf_base64, pdf_filename)
            logger.info(f"Generated PDF summary (length: {len(pdf_summary)} chars)")
            
            # 10. PDFと音声の統合要約生成（新機能）
            meeting_summary, meeting_token_info = self.gemini_service.summarize_pdf_and_audio(
                pdf_base64, pdf_filename, audio_bytes, audio_filename
            )
            logger.info(f"Generated meeting summary (length: {len(meeting_summary)} chars)")
            
            # 11. Notionページに両方の要約を保存
            self._upsert_summary_in_notion(page_id, pdf_summary)
            self._upsert_meeting_summary_in_notion(page_id, meeting_summary)
            
            # 12. 成功レスポンス
            result = {
                'success': True,
                'message': f'PDF and audio summary completed for page "{page_title}" (unique_id: {unique_id})',
                'details': {
                    'page_id': page_id,
                    'page_title': page_title,
                    'pdf_filename': pdf_filename,
                    'audio_filename': audio_filename,
                    'pdf_summary_length': len(pdf_summary),
                    'meeting_summary_length': len(meeting_summary),
                    'pdf_info': pdf_info,
                    'audio_info': audio_info,
                    'has_audio_file': True,
                    'token_usage': {
                        'pdf_only': pdf_token_info,
                        'meeting_summary': meeting_token_info,
                        'total_tokens': pdf_token_info['total_tokens'] + meeting_token_info['total_tokens']
                    }
                }
            }
            
            logger.info(f"PDF and audio summary process completed successfully: {result['message']}")
            return result
            
        except Exception as e:
            logger.error(f"PDF and audio summary failed: {str(e)}")
            raise NotionGeminiError(f"PDF and audio summary failed: {str(e)}")
    
    def _create_blocks_from_markdown(self, markdown_text: str) -> list:
        """
        マークダウンテキストを適切なNotionブロックに変換する
        
        Args:
            markdown_text: マークダウン形式のテキスト
            
        Returns:
            Notionブロックのリスト
        """
        blocks = []
        
        # マークダウンを行ごとに分割
        lines = markdown_text.split('\n')
        
        current_paragraph = []
        current_list_items = []
        list_type = None  # 'bulleted' or 'numbered'
        
        i = 0
        while i < len(lines):
            line = lines[i].rstrip()
            
            # 空行の処理
            if not line.strip():
                # 現在のパラグラフがあれば保存
                if current_paragraph:
                    paragraph_text = '\n'.join(current_paragraph)
                    if paragraph_text.strip():
                        blocks.extend(self._create_paragraph_from_text(paragraph_text))
                    current_paragraph = []
                
                # 現在のリストがあれば保存
                if current_list_items:
                    blocks.extend(self._create_list_blocks(current_list_items, list_type))
                    current_list_items = []
                    list_type = None
                
                i += 1
                continue
            
            # 見出しの処理
            heading_match = re.match(r'^(#{1,6})\s+(.+)$', line)
            if heading_match:
                # 現在の要素を先に保存
                if current_paragraph:
                    paragraph_text = '\n'.join(current_paragraph)
                    if paragraph_text.strip():
                        blocks.extend(self._create_paragraph_from_text(paragraph_text))
                    current_paragraph = []
                
                if current_list_items:
                    blocks.extend(self._create_list_blocks(current_list_items, list_type))
                    current_list_items = []
                    list_type = None
                
                level = len(heading_match.group(1))
                text = heading_match.group(2)
                blocks.append(self._create_heading_block(text, min(level, 3)))
                i += 1
                continue
            
            # 箇条書きの処理（- * +）
            bullet_match = re.match(r'^[\s]*[-*+]\s+(.+)$', line)
            if bullet_match:
                # パラグラフがある場合は先に保存
                if current_paragraph:
                    paragraph_text = '\n'.join(current_paragraph)
                    if paragraph_text.strip():
                        blocks.extend(self._create_paragraph_from_text(paragraph_text))
                    current_paragraph = []
                
                # リストタイプが変わった場合は保存
                if current_list_items and list_type != 'bulleted':
                    blocks.extend(self._create_list_blocks(current_list_items, list_type))
                    current_list_items = []
                
                text = bullet_match.group(1)
                current_list_items.append(text)
                list_type = 'bulleted'
                i += 1
                continue
            
            # 番号付きリストの処理
            numbered_match = re.match(r'^[\s]*\d+\.\s+(.+)$', line)
            if numbered_match:
                # パラグラフがある場合は先に保存
                if current_paragraph:
                    paragraph_text = '\n'.join(current_paragraph)
                    if paragraph_text.strip():
                        blocks.extend(self._create_paragraph_from_text(paragraph_text))
                    current_paragraph = []
                
                # リストタイプが変わった場合は保存
                if current_list_items and list_type != 'numbered':
                    blocks.extend(self._create_list_blocks(current_list_items, list_type))
                    current_list_items = []
                
                text = numbered_match.group(1)
                current_list_items.append(text)
                list_type = 'numbered'
                i += 1
                continue
            
            # 通常のテキスト（パラグラフ）
            else:
                # リストがある場合は先に保存
                if current_list_items:
                    blocks.extend(self._create_list_blocks(current_list_items, list_type))
                    current_list_items = []
                    list_type = None
                
                current_paragraph.append(line)
                i += 1
                continue
        
        # 最後の要素を保存
        if current_paragraph:
            paragraph_text = '\n'.join(current_paragraph)
            if paragraph_text.strip():
                blocks.extend(self._create_paragraph_from_text(paragraph_text))
        
        if current_list_items:
            blocks.extend(self._create_list_blocks(current_list_items, list_type))
        
        logger.info(f"Converted markdown to {len(blocks)} Notion blocks")
        return blocks
    
    def _create_heading_block(self, text: str, level: int) -> dict:
        """見出しブロックを作成"""
        heading_type = f'heading_{level}'
        rich_text = self._parse_rich_text(text)
        
        return {
            'object': 'block',
            'type': heading_type,
            heading_type: {
                'rich_text': rich_text,
                'color': 'default'
            }
        }
    
    def _create_list_blocks(self, items: list, list_type: str) -> list:
        """リストブロックを作成"""
        blocks = []
        block_type = 'bulleted_list_item' if list_type == 'bulleted' else 'numbered_list_item'
        
        for item in items:
            rich_text = self._parse_rich_text(item)
            
            block = {
                'object': 'block',
                'type': block_type,
                block_type: {
                    'rich_text': rich_text,
                    'color': 'default'
                }
            }
            blocks.append(block)
        
        return blocks
    
    def _create_paragraph_from_text(self, text: str, max_length: int = 1800) -> list:
        """
        テキストからパラグラフブロックを作成（長い場合は分割）
        
        Args:
            text: パラグラフテキスト
            max_length: 1つのパラグラフの最大文字数
            
        Returns:
            パラグラフブロックのリスト
        """
        # まずリッチテキストを解析
        rich_text_parts = self._parse_rich_text(text)
        
        # 全体の文字数をチェック
        total_length = sum(len(part.get('text', {}).get('content', '')) for part in rich_text_parts)
        
        if total_length <= max_length:
            # 短い場合はそのまま返す
            return [{
                'object': 'block',
                'type': 'paragraph',
                'paragraph': {
                    'rich_text': rich_text_parts,
                    'color': 'default'
                }
            }]
        
        # 長い場合はプレーンテキストベースで分割
        plain_text = text
        paragraphs = []
        current_text = plain_text
        
        while len(current_text) > max_length:
            # 適切な分割点を探す
            split_point = max_length
            
            # 日本語の句点で分割を試す
            for i in range(max_length, max(0, max_length - 200), -1):
                if current_text[i] in ['。', '．', '\n']:
                    split_point = i + 1
                    break
            
            # 句点が見つからない場合は改行で分割
            if split_point == max_length:
                for i in range(max_length, max(0, max_length - 100), -1):
                    if current_text[i] == '\n':
                        split_point = i + 1
                        break
            
            # それでも見つからない場合は半角スペースで分割
            if split_point == max_length:
                for i in range(max_length, max(0, max_length - 50), -1):
                    if current_text[i] == ' ':
                        split_point = i + 1
                        break
            
            # 分割点が見つからない場合は強制的に分割
            if split_point == max_length:
                split_point = max_length
            
            # パラグラフブロックを作成
            chunk = current_text[:split_point].strip()
            if chunk:
                rich_text_chunk = self._parse_rich_text(chunk)
                paragraphs.append({
                    'object': 'block',
                    'type': 'paragraph',
                    'paragraph': {
                        'rich_text': rich_text_chunk,
                        'color': 'default'
                    }
                })
            
            # 残りのテキストを更新
            current_text = current_text[split_point:].strip()
        
        # 最後の残りテキストがある場合は追加
        if current_text:
            rich_text_final = self._parse_rich_text(current_text)
            paragraphs.append({
                'object': 'block',
                'type': 'paragraph',
                'paragraph': {
                    'rich_text': rich_text_final,
                    'color': 'default'
                }
            })
        
        return paragraphs
    
    def _parse_rich_text(self, text: str) -> list:
        """
        マークダウン形式のテキストをNotionのrich_textオブジェクトに変換
        
        Args:
            text: マークダウン形式のテキスト
            
        Returns:
            rich_textオブジェクトのリスト
        """
        # シンプルなマークダウンパーサー（太字、斜体、コード）
        parts = []
        current_pos = 0
        
        # マークダウンパターン（優先度順）
        patterns = [
            (r'\*\*\*(.*?)\*\*\*', {'bold': True, 'italic': True}),  # 太字+斜体
            (r'\*\*(.*?)\*\*', {'bold': True}),                       # 太字
            (r'\*(.*?)\*', {'italic': True}),                         # 斜体
            (r'`(.*?)`', {'code': True}),                            # インラインコード
        ]
        
        while current_pos < len(text):
            # 次のマークダウンパターンを探す
            next_match = None
            next_pattern = None
            next_annotations = None
            
            for pattern, annotations in patterns:
                match = re.search(pattern, text[current_pos:])
                if match and (next_match is None or match.start() < next_match.start()):
                    next_match = match
                    next_pattern = pattern
                    next_annotations = annotations
            
            if next_match is None:
                # マークダウンパターンが見つからない場合、残りのテキストを追加
                remaining_text = text[current_pos:]
                if remaining_text:
                    parts.append({
                        'type': 'text',
                        'text': {'content': remaining_text},
                        'annotations': {
                            'bold': False,
                            'italic': False,
                            'strikethrough': False,
                            'underline': False,
                            'code': False,
                            'color': 'default'
                        }
                    })
                break
            
            # マークダウンの前のテキストを追加
            before_text = text[current_pos:current_pos + next_match.start()]
            if before_text:
                parts.append({
                    'type': 'text',
                    'text': {'content': before_text},
                    'annotations': {
                        'bold': False,
                        'italic': False,
                        'strikethrough': False,
                        'underline': False,
                        'code': False,
                        'color': 'default'
                    }
                })
            
            # マークダウンパターンの内容を追加
            content = next_match.group(1)
            annotations = {
                'bold': next_annotations.get('bold', False),
                'italic': next_annotations.get('italic', False),
                'strikethrough': False,
                'underline': False,
                'code': next_annotations.get('code', False),
                'color': 'default'
            }
            
            parts.append({
                'type': 'text',
                'text': {'content': content},
                'annotations': annotations
            })
            
            # 位置を更新
            current_pos += next_match.end()
        
        # 空の部品を除去
        parts = [part for part in parts if part['text']['content']]
        
        # partsが空の場合は、空のテキストを返す
        if not parts:
            parts = [{
                'type': 'text',
                'text': {'content': ''},
                'annotations': {
                    'bold': False,
                    'italic': False,
                    'strikethrough': False,
                    'underline': False,
                    'code': False,
                    'color': 'default'
                }
            }]
        
        return parts
    
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
            
            # 6. 要約をマークダウンから適切なブロックに変換して追加
            summary_blocks = self._create_blocks_from_markdown(summary)
            self.notion_service.append_block_children(toggle_h3_block_id, summary_blocks)
            logger.info("Successfully saved summary to Notion")
            
        except Exception as e:
            logger.error(f"Failed to save summary to Notion: {str(e)}")
            raise NotionGeminiError(f"Failed to save summary to Notion: {str(e)}")
    
    def _upsert_meeting_summary_in_notion(self, page_id: str, summary: str) -> None:
        """
        Notionページに議事録まとめを保存する
        
        Args:
            page_id: ページID
            summary: 議事録まとめテキスト
        """
        try:
            logger.info(f"Saving meeting summary to Notion page: {page_id}")
            
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
            
            # 3. コールアウト内の議事録まとめトグルH3を探す
            callout_children = self.notion_service.get_block_children(callout_block_id)
            toggle_h3_block_id = None
            
            for block in callout_children.results:
                if (block.get('type') == 'heading_3' and 
                    block.get('heading_3', {}).get('is_toggleable') == True):
                    rich_text = block.get('heading_3', {}).get('rich_text', [])
                    if rich_text and rich_text[0].get('text', {}).get('content') == config.MEETING_SUMMARY_TOGGLE_H3_TITLE:
                        toggle_h3_block_id = block['id']
                        logger.info(f"Found existing meeting summary toggle H3 block: {toggle_h3_block_id}")
                        break
            
            # 4. 議事録まとめトグルH3ブロックがない場合は作成
            if not toggle_h3_block_id:
                logger.info(f"Creating new meeting summary toggle H3 block: {config.MEETING_SUMMARY_TOGGLE_H3_TITLE}")
                h3_data = {
                    'object': 'block',
                    'type': 'heading_3',
                    'heading_3': {
                        'rich_text': [{
                            'type': 'text',
                            'text': {'content': config.MEETING_SUMMARY_TOGGLE_H3_TITLE}
                        }],
                        'is_toggleable': True,
                        'color': 'default'
                    }
                }
                
                response = self.notion_service.append_block_children(callout_block_id, [h3_data])
                toggle_h3_block_id = response['results'][0]['id']
                logger.info(f"Created new meeting summary toggle H3 block: {toggle_h3_block_id}")
            
            # 5. トグルH3の既存の子ブロックを削除
            h3_children = self.notion_service.get_block_children(toggle_h3_block_id)
            if h3_children.results:
                logger.info(f"Deleting {len(h3_children.results)} existing child blocks")
                for child_block in h3_children.results:
                    self.notion_service.delete_block(child_block['id'])
            
            # 6. 議事録まとめをマークダウンから適切なブロックに変換して追加
            meeting_summary_blocks = self._create_blocks_from_markdown(summary)
            self.notion_service.append_block_children(toggle_h3_block_id, meeting_summary_blocks)
            logger.info("Successfully saved meeting summary to Notion")
            
        except Exception as e:
            logger.error(f"Failed to save meeting summary to Notion: {str(e)}")
            raise NotionGeminiError(f"Failed to save meeting summary to Notion: {str(e)}")
    
    def _create_paragraph_blocks(self, text: str, max_length: int = 1800) -> list:
        """
        長いテキストを複数のパラグラフブロックに分割する（後方互換性のため保持）
        
        Args:
            text: 分割するテキスト
            max_length: 1つのパラグラフの最大文字数（Notion制限の2000より少し小さく設定）
            
        Returns:
            パラグラフブロックのリスト
        """
        return self._create_paragraph_from_text(text, max_length)
    
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