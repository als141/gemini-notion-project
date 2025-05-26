import functions_framework
from flask import Request, jsonify
import traceback
from typing import Dict, Any

from app.handlers.pdf_summary import PDFSummaryHandler
from app.utils.logger import setup_logger
from app.utils.config import config
from app.exceptions.custom_exceptions import (
    NotionGeminiError,
    NotionAPIError,
    GeminiAPIError,
    PDFProcessingError, 
    PageNotFoundError,
    FileNotFoundError,
    ConfigurationError
)

# ロガーの設定
logger = setup_logger(__name__)

# ハンドラーインスタンス（関数の外で初期化）
pdf_handler = None

def get_pdf_handler():
    """PDFハンドラーのシングルトン取得"""
    global pdf_handler
    if pdf_handler is None:
        try:
            pdf_handler = PDFSummaryHandler()
        except Exception as e:
            logger.error(f"Failed to initialize PDF handler: {str(e)}")
            raise ConfigurationError(f"Service initialization failed: {str(e)}")
    return pdf_handler

@functions_framework.http
def main(request: Request) -> Dict[str, Any]:
    """
    Cloud Functions のメインエントリーポイント
    
    Args:
        request: HTTPリクエスト
        
    Returns:
        JSONレスポンス
    """
    # CORS ヘッダーの設定
    headers = {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type',
        'Content-Type': 'application/json'
    }
    
    try:
        logger.info(f"Received request: {request.method} {request.url}")
        logger.info(f"Request args: {request.args}")
        
        # OPTIONSリクエスト（プリフライト）の処理
        if request.method == 'OPTIONS':
            return ('', 204, headers)
        
        # ルーティング処理
        if request.method == 'GET':
            return handle_get_request(request, headers)
        elif request.method == 'POST':
            return handle_post_request(request, headers)
        else:
            return jsonify({
                'success': False,
                'error': f'Method {request.method} not allowed'
            }), 405, headers
            
    except Exception as e:
        logger.error(f"Unhandled error in main function: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'details': str(e) if logger.level <= 10 else None  # DEBUGレベルの場合のみ詳細表示
        }), 500, headers

def handle_get_request(request: Request, headers: Dict[str, str]) -> tuple:
    """GETリクエストの処理（GASのdoGet相当）"""
    try:
        # パラメータの取得
        unique_id = request.args.get('uid')
        action = request.args.get('action', 'summary')  # デフォルトはsummary
        
        if action == 'health':
            return handle_health_check(headers)
        elif action == 'summary':
            return handle_pdf_summary_request(unique_id, headers)
        elif action == 'minutes':
            return handle_pdf_and_audio_minutes_request(unique_id, headers)
        else:
            return jsonify({
                'success': False,
                'error': f'Unknown action: {action}'
            }), 400, headers
            
    except Exception as e:
        logger.error(f"Error in GET request handling: {str(e)}")
        return handle_error_response(e, headers)

def handle_post_request(request: Request, headers: Dict[str, str]) -> tuple:
    """POSTリクエストの処理"""
    try:
        # JSONデータの取得
        if request.is_json:
            data = request.get_json()
            unique_id = data.get('uid') or data.get('unique_id')
            action = data.get('action', 'summary')
        else:
            # フォームデータの場合
            unique_id = request.form.get('uid') or request.form.get('unique_id')
            action = request.form.get('action', 'summary')
        
        if action == 'health':
            return handle_health_check(headers)
        elif action == 'summary':
            return handle_pdf_summary_request(unique_id, headers)
        elif action == 'minutes':
            return handle_pdf_and_audio_minutes_request(unique_id, headers)
        else:
            return jsonify({
                'success': False,
                'error': f'Unknown action: {action}'
            }), 400, headers
            
    except Exception as e:
        logger.error(f"Error in POST request handling: {str(e)}")
        return handle_error_response(e, headers)

def handle_pdf_summary_request(unique_id: str, headers: Dict[str, str]) -> tuple:
    """PDF要約リクエストの処理"""
    if not unique_id:
        return jsonify({
            'success': False,
            'error': 'Missing required parameter: uid (unique_id)'
        }), 400, headers
    
    try:
        handler = get_pdf_handler()
        result = handler.process_pdf_summary(unique_id)
        
        return jsonify(result), 200, headers
        
    except Exception as e:
        logger.error(f"Error in PDF summary processing: {str(e)}")
        return handle_error_response(e, headers)

def handle_pdf_and_audio_minutes_request(unique_id: str, headers: Dict[str, str]) -> tuple:
    """PDFと音声による議事録作成リクエストの処理"""
    if not unique_id:
        return jsonify({
            'success': False,
            'error': 'Missing required parameter: uid (unique_id)'
        }), 400, headers
    
    try:
        handler = get_pdf_handler()
        result = handler.process_pdf_and_audio_minutes(unique_id)
        
        return jsonify(result), 200, headers
        
    except Exception as e:
        logger.error(f"Error in PDF and audio minutes processing: {str(e)}")
        return handle_error_response(e, headers)

def handle_health_check(headers: Dict[str, str]) -> tuple:
    """ヘルスチェック処理"""
    try:
        handler = get_pdf_handler()
        health_status = handler.health_check()
        
        status_code = 200 if health_status['overall'] else 503
        
        return jsonify({
            'success': health_status['overall'],
            'health': health_status,
            'config': {
                'notion_database_id': config.NOTION_DATABASE_ID,
                'gemini_model': config.GEMINI_MODEL,
                'has_notion_key': bool(config.NOTION_API_KEY),
                'has_gemini_key': bool(config.GEMINI_API_KEY)
            }
        }), status_code, headers
        
    except Exception as e:
        logger.error(f"Error in health check: {str(e)}")
        return handle_error_response(e, headers)

def handle_error_response(error: Exception, headers: Dict[str, str]) -> tuple:
    """エラーレスポンスの生成"""
    if isinstance(error, PageNotFoundError):
        return jsonify({
            'success': False,
            'error': 'Page not found',
            'details': str(error)
        }), 404, headers
    
    elif isinstance(error, FileNotFoundError):
        return jsonify({
            'success': False,
            'error': 'File not found',
            'details': str(error)
        }), 404, headers
    
    elif isinstance(error, (NotionAPIError, GeminiAPIError)):
        status_code = getattr(error, 'status_code', 500)
        return jsonify({
            'success': False,
            'error': 'API error',
            'details': str(error)
        }), status_code, headers
    
    elif isinstance(error, PDFProcessingError):
        return jsonify({
            'success': False,
            'error': 'PDF processing error',
            'details': str(error)
        }), 400, headers
    
    elif isinstance(error, ConfigurationError):
        return jsonify({
            'success': False,
            'error': 'Configuration error',
            'details': str(error)
        }), 500, headers
    
    elif isinstance(error, ValueError):
        return jsonify({
            'success': False,
            'error': 'Invalid parameter',
            'details': str(error)
        }), 400, headers
    
    else:
        # その他のエラー
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'details': str(error)
        }), 500, headers

# ローカル開発用のテスト関数
if __name__ == '__main__':
    from flask import Flask
    app = Flask(__name__)
    
    @app.route('/', methods=['GET', 'POST', 'OPTIONS'])
    def test_main():
        from flask import request
        return main(request)
    
    print("Starting local development server...")
    print("Test URLs:")
    print("- Health check: http://localhost:8080/?action=health")
    print("- PDF summary: http://localhost:8080/?uid=YOUR_UNIQUE_ID&action=summary")
    print("- PDF & Audio minutes: http://localhost:8080/?uid=YOUR_UNIQUE_ID&action=minutes")
    
    app.run(host='0.0.0.0', port=8080, debug=True)