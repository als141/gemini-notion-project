from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class NotionFile(BaseModel):
    """Notionファイルオブジェクト"""
    name: str
    url: str
    type: str = Field(description="file or external")

class NotionProperty(BaseModel):
    """Notionプロパティ基底クラス"""
    id: str
    type: str

class TitleProperty(NotionProperty):
    """タイトルプロパティ"""
    title: List[Dict[str, Any]]

class FilesProperty(NotionProperty):
    """ファイルプロパティ"""
    files: List[Dict[str, Any]]

class UniqueIdProperty(NotionProperty):
    """ユニークIDプロパティ"""
    unique_id: Dict[str, int]

class NotionPage(BaseModel):
    """Notionページオブジェクト"""
    id: str
    properties: Dict[str, Dict[str, Any]]
    
    def get_title(self) -> Optional[str]:
        """ページタイトルを取得"""
        for prop_name in ["名前", "Name", "title"]:
            if prop_name in self.properties:
                title_prop = self.properties[prop_name]
                if title_prop.get("title") and len(title_prop["title"]) > 0:
                    return title_prop["title"][0].get("plain_text", "")
        return "無題のページ"
    
    def get_files(self, property_name: str) -> List[NotionFile]:
        """ファイルプロパティからファイルリストを取得"""
        if property_name not in self.properties:
            return []
        
        files_prop = self.properties[property_name]
        if not files_prop.get("files"):
            return []
        
        notion_files = []
        for file_data in files_prop["files"]:
            if file_data["type"] == "file":
                notion_files.append(NotionFile(
                    name=file_data["name"],
                    url=file_data["file"]["url"],
                    type=file_data["type"]
                ))
            elif file_data["type"] == "external":
                notion_files.append(NotionFile(
                    name=file_data["name"],
                    url=file_data["external"]["url"],
                    type=file_data["type"]
                ))
        
        return notion_files

class NotionBlock(BaseModel):
    """Notionブロックオブジェクト"""
    id: str
    type: str
    object: str = "block"
    
class CalloutBlock(NotionBlock):
    """コールアウトブロック"""
    callout: Dict[str, Any]
    
class HeadingBlock(NotionBlock):
    """見出しブロック"""
    heading_3: Optional[Dict[str, Any]] = None
    
class ParagraphBlock(NotionBlock):
    """段落ブロック"""
    paragraph: Dict[str, Any]

class BlockChildren(BaseModel):
    """ブロックの子要素レスポンス"""
    results: List[Dict[str, Any]]
    has_more: bool = False
    next_cursor: Optional[str] = None