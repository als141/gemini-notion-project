import logging
import sys
from typing import Optional

def setup_logger(name: str, level: Optional[str] = None) -> logging.Logger:
    """
    ログ設定を行う
    
    Args:
        name: ロガー名
        level: ログレベル (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        
    Returns:
        設定されたロガーイン스タンス
    """
    logger = logging.getLogger(name)
    
    # 既に設定済みの場合は返す
    if logger.handlers:
        return logger
    
    # ログレベルの設定
    log_level = getattr(logging, (level or 'INFO').upper())
    logger.setLevel(log_level)
    
    # ハンドラーの設定
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(log_level)
    
    # フォーマッターの設定
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    handler.setFormatter(formatter)
    
    logger.addHandler(handler)
    
    return logger

# デフォルトロガー
logger = setup_logger(__name__)