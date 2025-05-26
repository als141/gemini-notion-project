# Gemini Notion Project

PDF要約をGemini APIで生成してNotionに投稿するCloud Functionsプロジェクトです。

## 概要

このプロジェクトは以下の機能を提供します：

- PDFファイルからテキストを抽出
- Gemini APIを使用してPDFの要約を生成
- Notionデータベースに要約を投稿
- Google Cloud Functionsとしてデプロイ可能

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
GEMINI_MODEL=gemini-1.5-flash
```

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

## プロジェクト構造

```
.
├── app/
│   ├── exceptions/
│   │   └── custom_exceptions.py    # カスタム例外クラス
│   ├── handlers/
│   ├── utils/
│   └── ...
├── tests/
│   ├── __init__.py
│   └── test_handlers.py
├── main.py                         # Cloud Functions エントリーポイント
├── pyproject.toml                  # プロジェクト設定とuv管理
├── requirements.txt                # 従来の依存関係ファイル
└── README.md
```

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
  --allow-unauthenticated
```

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
