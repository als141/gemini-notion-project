import requests
from typing import Optional, List, Dict, Any
from app.utils.config import config
from app.utils.logger import setup_logger
from app.models.notion_models import NotionPage, NotionFile, BlockChildren
from app.exceptions.custom_exceptions import NotionAPIError, PageNotFoundError, FileNotFoundError

logger = setup_logger(__name__)

class NotionService:
    """Notion API操作サービス"""
    
    def __init__(self):
        self.api_key = config.NOTION_API_KEY
        self.database_id = config.NOTION_DATABASE_ID
        self.version = config.NOTION_API_VERSION
        self.base_url = "https://api.notion.com/v1"
        
        if not self.api_key:
            raise NotionAPIError("NOTION_API_KEY is not set")
    
    def _get_headers(self) -> Dict[str, str]:
        """APIリクエスト用ヘッダーを取得"""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Notion-Version": self.version
        }
    
    def find_page_by_unique_id(self, unique_id: int) -> Optional[str]:
        """
        ユニークIDでページを検索してページIDを返す
        
        Args:
            unique_id: 検索するユニークID
            
        Returns:
            見つかったページのID、見つからない場合はNone
        """
        url = f"{self.base_url}/databases/{self.database_id}/query"
        
        payload = {
            "filter": {
                "property": config.UNIQUE_ID_PROPERTY_NAME,
                "unique_id": {
                    "equals": unique_id
                }
            }
        }
        
        try:
            response = requests.post(url, json=payload, headers=self._get_headers())
            
            if response.status_code != 200:
                logger.error(f"Database query failed: {response.status_code} - {response.text}")
                raise NotionAPIError(f"Database query failed: {response.status_code}", response.status_code)
            
            data = response.json()
            results = data.get("results", [])
            
            if not results:
                logger.warning(f"No page found with unique_id: {unique_id}")
                return None
            
            if len(results) > 1:
                logger.warning(f"Multiple pages found with unique_id: {unique_id}. Using first one.")
            
            page_id = results[0]["id"]
            logger.info(f"Found page ID: {page_id} for unique_id: {unique_id}")
            return page_id
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {str(e)}")
            raise NotionAPIError(f"Request failed: {str(e)}")
    
    def get_page_details(self, page_id: str) -> NotionPage:
        """
        ページの詳細情報を取得
        
        Args:
            page_id: 取得するページのID
            
        Returns:
            NotionPageオブジェクト
        """
        url = f"{self.base_url}/pages/{page_id}"
        
        try:
            response = requests.get(url, headers=self._get_headers())
            
            if response.status_code == 404:
                raise PageNotFoundError(f"Page not found: {page_id}")
            elif response.status_code != 200:
                logger.error(f"Get page failed: {response.status_code} - {response.text}")
                raise NotionAPIError(f"Get page failed: {response.status_code}", response.status_code)
            
            data = response.json()
            logger.info(f"Retrieved page details for: {page_id}")
            return NotionPage(**data)
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {str(e)}")
            raise NotionAPIError(f"Request failed: {str(e)}")
    
    def get_block_children(self, block_id: str) -> BlockChildren:
        """
        ブロックの子要素を取得
        
        Args:
            block_id: 親ブロックのID
            
        Returns:
            BlockChildrenオブジェクト
        """
        url = f"{self.base_url}/blocks/{block_id}/children"
        
        try:
            response = requests.get(url, headers=self._get_headers())
            
            if response.status_code != 200:
                logger.error(f"Get block children failed: {response.status_code} - {response.text}")
                raise NotionAPIError(f"Get block children failed: {response.status_code}", response.status_code)
            
            data = response.json()
            return BlockChildren(**data)
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {str(e)}")
            raise NotionAPIError(f"Request failed: {str(e)}")
    
    def append_block_children(self, parent_id: str, blocks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        ブロックに子要素を追加
        
        Args:
            parent_id: 親ブロックのID
            blocks: 追加するブロックのリスト
            
        Returns:
            APIレスポンス
        """
        url = f"{self.base_url}/blocks/{parent_id}/children"
        payload = {"children": blocks}
        
        try:
            response = requests.patch(url, json=payload, headers=self._get_headers())
            
            if response.status_code != 200:
                logger.error(f"Append block children failed: {response.status_code} - {response.text}")
                raise NotionAPIError(f"Append block children failed: {response.status_code}", response.status_code)
            
            data = response.json()
            logger.info(f"Successfully appended blocks to: {parent_id}")
            return data
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {str(e)}")
            raise NotionAPIError(f"Request failed: {str(e)}")
    
    def delete_block(self, block_id: str) -> None:
        """
        ブロックを削除
        
        Args:
            block_id: 削除するブロックのID
        """
        url = f"{self.base_url}/blocks/{block_id}"
        
        try:
            response = requests.delete(url, headers=self._get_headers())
            
            if response.status_code == 200:
                logger.info(f"Successfully deleted block: {block_id}")
            else:
                logger.warning(f"Delete block warning: {response.status_code} - {response.text}")
                # 削除失敗でも処理を続行
                
        except requests.exceptions.RequestException as e:
            logger.warning(f"Delete block request failed: {str(e)}")
            # 削除失敗でも処理を続行
    
    def get_pdf_file_from_page(self, page: NotionPage) -> NotionFile:
        """
        ページからPDFファイルを取得
        
        Args:
            page: NotionPageオブジェクト
            
        Returns:
            NotionFileオブジェクト
        """
        files = page.get_files(config.FILE_PROPERTY_NAME)
        
        if not files:
            raise FileNotFoundError(f"No files found in property '{config.FILE_PROPERTY_NAME}'")
        
        # 最初のファイルを返す（通常は1つのPDFファイル）
        return files[0]