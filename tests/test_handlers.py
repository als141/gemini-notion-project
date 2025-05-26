import pytest
import unittest.mock as mock
from unittest.mock import Mock, patch, MagicMock

# テスト対象のインポート
from app.handlers.pdf_summary import PDFSummaryHandler
from app.exceptions.custom_exceptions import (
    PageNotFoundError, 
    FileNotFoundError, 
    ConfigurationError
)
from app.models.notion_models import NotionPage, NotionFile

class TestPDFSummaryHandler:
    """PDFSummaryHandlerのテストクラス"""
    
    @pytest.fixture
    def handler(self):
        """テスト用のハンドラーインスタンス"""
        with patch('app.handlers.pdf_summary.NotionService'), \
             patch('app.handlers.pdf_summary.GeminiService'), \
             patch('app.handlers.pdf_summary.PDFService'):
            return PDFSummaryHandler()
    
    @pytest.fixture
    def mock_notion_page(self):
        """テスト用のNotionPageオブジェクト"""
        return NotionPage(
            id="test-page-id",
            properties={
                "名前": {
                    "title": [{"plain_text": "テストページ"}]
                },
                "スライドPDF": {
                    "files": [{
                        "name": "test.pdf",
                        "type": "file",
                        "file": {"url": "https://example.com/test.pdf"}
                    }]
                }
            }
        )
    
    @pytest.fixture  
    def mock_notion_file(self):
        """テスト用のNotionFileオブジェクト"""
        return NotionFile(
            name="test.pdf",
            url="https://example.com/test.pdf",
            type="file"
        )
    
    def test_process_pdf_summary_success(self, handler, mock_notion_page, mock_notion_file):
        """PDF要約処理の正常系テスト"""
        # モックの設定
        handler.notion_service.find_page_by_unique_id.return_value = "test-page-id"
        handler.notion_service.get_page_details.return_value = mock_notion_page
        handler.notion_service.get_pdf_file_from_page.return_value = mock_notion_file
        handler.pdf_service.download_and_encode_pdf.return_value = ("base64data", "test.pdf")
        handler.pdf_service.get_pdf_info.return_value = {"size_bytes": 1000, "is_valid_pdf": True}
        handler.gemini_service.summarize_pdf.return_value = "これはテスト要約です。"
        
        # プライベートメソッドをモック
        with patch.object(handler, '_upsert_summary_in_notion'):
            result = handler.process_pdf_summary("123")
        
        # 結果の検証
        assert result["success"] is True
        assert "テストページ" in result["message"]
        assert result["details"]["page_id"] == "test-page-id"
        assert result["details"]["pdf_filename"] == "test.pdf"
        assert result["details"]["summary_length"] == len("これはテスト要約です。")
        
        # メソッドの呼び出し確認
        handler.notion_service.find_page_by_unique_id.assert_called_once_with(123)
        handler.notion_service.get_page_details.assert_called_once_with("test-page-id")
        handler.gemini_service.summarize_pdf.assert_called_once()
    
    def test_process_pdf_summary_invalid_unique_id(self, handler):
        """無効なユニークIDのテスト"""
        with pytest.raises(ValueError, match="Invalid unique_id format"):
            handler.process_pdf_summary("invalid_id")
    
    def test_process_pdf_summary_page_not_found(self, handler):
        """ページが見つからない場合のテスト"""
        handler.notion_service.find_page_by_unique_id.return_value = None
        
        with pytest.raises(PageNotFoundError, match="Page not found for unique_id"):
            handler.process_pdf_summary("123")
    
    def test_process_pdf_summary_file_not_found(self, handler, mock_notion_page):
        """PDFファイルが見つからない場合のテスト"""
        handler.notion_service.find_page_by_unique_id.return_value = "test-page-id"
        handler.notion_service.get_page_details.return_value = mock_notion_page
        handler.notion_service.get_pdf_file_from_page.side_effect = FileNotFoundError("No PDF file")
        
        with pytest.raises(FileNotFoundError, match="PDF file not found"):
            handler.process_pdf_summary("123")
    
    def test_health_check_all_services_ok(self, handler):
        """ヘルスチェック - 全サービス正常"""
        handler.gemini_service.test_connection.return_value = True
        handler.notion_service.api_key = "test-key"
        handler.notion_service.database_id = "test-db-id"
        
        result = handler.health_check()
        
        assert result["notion_api"] is True
        assert result["gemini_api"] is True
        assert result["overall"] is True
    
    def test_health_check_gemini_service_fail(self, handler):
        """ヘルスチェック - Geminiサービス失敗"""
        handler.gemini_service.test_connection.return_value = False
        handler.notion_service.api_key = "test-key"
        handler.notion_service.database_id = "test-db-id"
        
        result = handler.health_check()
        
        assert result["notion_api"] is True
        assert result["gemini_api"] is False
        assert result["overall"] is False
    
    def test_health_check_notion_service_fail(self, handler):
        """ヘルスチェック - Notionサービス失敗"""
        handler.gemini_service.test_connection.return_value = True
        handler.notion_service.api_key = ""  # 空文字列
        handler.notion_service.database_id = "test-db-id"
        
        result = handler.health_check()
        
        assert result["notion_api"] is False
        assert result["gemini_api"] is True
        assert result["overall"] is False


class TestNotionPageModel:
    """NotionPageモデルのテスト"""
    
    def test_get_title_with_name_property(self):
        """'名前'プロパティからタイトル取得"""
        page = NotionPage(
            id="test-id",
            properties={
                "名前": {
                    "title": [{"plain_text": "テストタイトル"}]
                }
            }
        )
        
        assert page.get_title() == "テストタイトル"
    
    def test_get_title_with_no_title(self):
        """タイトルがない場合のデフォルト値"""
        page = NotionPage(
            id="test-id",
            properties={}
        )
        
        assert page.get_title() == "無題のページ"
    
    def test_get_files_with_file_property(self):
        """ファイルプロパティからファイル取得"""
        page = NotionPage(
            id="test-id",
            properties={
                "スライドPDF": {
                    "files": [{
                        "name": "test.pdf",
                        "type": "file",
                        "file": {"url": "https://example.com/test.pdf"}
                    }]
                }
            }
        )
        
        files = page.get_files("スライドPDF")
        
        assert len(files) == 1
        assert files[0].name == "test.pdf"
        assert files[0].url == "https://example.com/test.pdf"
        assert files[0].type == "file"
    
    def test_get_files_with_no_files(self):
        """ファイルがない場合"""
        page = NotionPage(
            id="test-id",
            properties={}
        )
        
        files = page.get_files("スライドPDF")
        
        assert files == []


# テスト実行用のメイン関数
if __name__ == "__main__":
    pytest.main([__file__, "-v"])