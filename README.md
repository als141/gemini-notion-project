# Gemini Notion Project

PDF要約をGemini APIで生成してNotionに投稿するCloud Functionsプロジェクトです。

## 概要

このプロジェクトは以下の機能を提供します：

- PDFファイルからテキストを抽出
- Gemini APIを使用してPDFの要約を生成
- **NEW**: 録音ファイルとPDFを同時に処理して議事録まとめを作成
- **NEW**: 使用トークン総数の詳細表示
- Notionデータベースに要約を投稿
- Google Cloud Functionsとしてデプロイ可能

## 新機能

### 📊 トークン使用量の表示
API呼び出しの詳細で使用トークン数が表示されるようになりました。
- 入力トークン数
- 出力トークン数
- 総トークン数
- PDFと音声ファイル別のトークン数（同時処理時）

### 🎤 録音ファイル処理と議事録まとめ
Notion データベースの「録音ファイル」プロパティに音声ファイルがある場合：
1. PDFのみの要約（従来機能）
2. PDFと録音ファイルを統合した議事録まとめ（新機能）

両方が生成され、Notionページに別々のセクションとして保存されます。

### 📝 対応音声ファイル形式
- MP3
- WAV 
- M4A
- AAC
- OGG
- FLAC

## 前提条件

- Python 3.9以上
- [uv](https://docs.astral.sh/uv/) パッケージマネージャー
- Notion API キー
- Google Gemini API キー

## セットアップ

### 1. uvを使った環境セットアップ

```bash
# プロジェクトの初期化（既存プロジェクトの場合）
uv sync

# 開発用依存関係も含めてインストール
uv sync --extra dev

# 新しい依存関係を追加する場合
uv add package-name

# 開発用依存関係を追加する場合
uv add --dev package-name
```

### 2. 環境変数の設定

`.env`ファイルを作成し、以下の環境変数を設定してください：

```env
NOTION_API_KEY=your_notion_api_key
NOTION_DATABASE_ID=your_notion_database_id
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-2.5-flash-preview-05-20

# Notionプロパティ名（カスタマイズ可能）
UNIQUE_ID_PROPERTY_NAME=ID
FILE_PROPERTY_NAME=スライドPDF
AUDIO_FILE_PROPERTY_NAME=録音ファイル

# 要約セクションタイトル（カスタマイズ可能）
SUMMARY_TOGGLE_H3_TITLE=Summary
MEETING_SUMMARY_TOGGLE_H3_TITLE=議事録まとめ
```

### 3. Notionデータベースの設定

データベースには以下のプロパティが必要です：

**必須プロパティ：**
- `ID` (Number): ユニークID
- `スライドPDF` (Files): PDFファイル

**オプションプロパティ：**
- `録音ファイル` (Files): 議事録の録音ファイル

## 使用方法

### ローカル開発

```bash
# 開発サーバーの起動
uv run python main.py

# テストの実行
uv run pytest

# コードフォーマット
uv run black .

# 型チェック
uv run mypy .

# リンター
uv run flake8 .
```

### API エンドポイント

- ヘルスチェック: `GET /?action=health`
- PDF要約: `GET /?uid=UNIQUE_ID&action=summary`
- PDF要約 (POST): `POST /` with JSON `{"uid": "UNIQUE_ID", "action": "summary"}`

### レスポンス例

#### PDFのみの場合
```json
{
  "success": true,
  "message": "PDF summary completed for page \"サンプル発表\" (unique_id: 123)",
  "details": {
    "page_id": "abc123",
    "page_title": "サンプル発表",
    "pdf_filename": "presentation.pdf",
    "summary_length": 456,
    "has_audio_file": false,
    "token_usage": {
      "input_tokens": 2500,
      "output_tokens": 150,
      "total_tokens": 2650
    }
  }
}
```

#### PDF + 録音ファイルの場合
```json
{
  "success": true,
  "message": "PDF and audio summary completed for page \"議事録サンプル\" (unique_id: 456)",
  "details": {
    "page_id": "def456",
    "page_title": "議事録サンプル",
    "pdf_filename": "slides.pdf",
    "audio_filename": "meeting_recording.mp3",
    "pdf_summary_length": 400,
    "meeting_summary_length": 650,
    "has_audio_file": true,
    "token_usage": {
      "pdf_only": {
        "input_tokens": 2000,
        "output_tokens": 120,
        "total_tokens": 2120
      },
      "meeting_summary": {
        "input_tokens": 8500,
        "output_tokens": 200,
        "total_tokens": 8700,
        "pdf_tokens": 2000,
        "audio_tokens": 6500
      },
      "total_tokens": 10820
    }
  }
}
```

## プロジェクト構造

```
.
├── app/
│   ├── exceptions/
│   │   └── custom_exceptions.py    # カスタム例外クラス
│   ├── handlers/
│   │   └── pdf_summary.py          # 要約処理メインハンドラー
│   ├── services/
│   │   ├── gemini_service.py       # Gemini API操作
│   │   ├── notion_service.py       # Notion API操作
│   │   └── pdf_service.py          # PDF/音声ファイル処理
│   ├── utils/
│   │   └── config.py               # 設定管理
│   └── models/
│       └── notion_models.py        # Notionデータモデル
├── tests/
├── main.py                         # Cloud Functions エントリーポイント
├── pyproject.toml                  # プロジェクト設定とuv管理
├── requirements.txt                # 従来の依存関係ファイル
└── README.md
```

## 技術仕様

### Gemini Files API使用
- 大きな音声ファイル（最大500MB）をサポート
- 一時ファイル作成とクリーンアップ
- アップロード状態の監視

### トークン使用量追跡
- PDF処理のトークン数
- 音声処理のトークン数
- API応答での詳細表示

### エラーハンドリング
- ファイルサイズ制限チェック
- 音声ファイル形式検証
- 適切なクリーンアップ処理

## デプロイ

### Google Cloud Functions

```bash
# Functions Framework を使用してローカルテスト
uv run functions-framework --target=main --port=8080

# gcloud CLI を使用してデプロイ
gcloud functions deploy your-function-name \
  --runtime python39 \
  --trigger-http \
  --entry-point main \
  --allow-unauthenticated \
  --timeout 540 \
  --memory 2GB
```

**注意**: 音声ファイル処理のため、タイムアウトとメモリを増やすことを推奨します。

## 開発

### テストの追加

`tests/`ディレクトリにテストファイルを追加してください。

### 新しい機能の追加

1. `app/`ディレクトリに新しいモジュールを追加
2. 必要に応じてカスタム例外を`app/exceptions/custom_exceptions.py`に追加
3. テストを`tests/`に追加
4. `main.py`でルーティングを更新

## ライセンス

MIT License
