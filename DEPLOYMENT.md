# 📦 Google Cloud Functions デプロイガイド

このドキュメントでは、Gemini-Notion プロジェクトを Google Cloud Functions にデプロイする方法を説明します。

## 🚀 デプロイ方法

### 方法1: 手動デプロイ（推奨・簡単）

#### 1. 前提条件

```bash
# Google Cloud SDKのインストール確認
gcloud --version

# 認証
gcloud auth login

# プロジェクトの設定
gcloud config set project YOUR_PROJECT_ID
```

#### 2. 環境変数の設定

`.env`ファイルを作成し、必要な環境変数を設定：

```bash
cp .env.example .env
# .envファイルを編集して実際の値を設定
```

#### 3. デプロイ実行

```bash
# 実行権限を付与
chmod +x deploy.sh

# デプロイ実行
./deploy.sh [関数名] [リージョン] [プロジェクトID]

# 例：
./deploy.sh gemini-notion-processor asia-northeast1 my-project-id
```

### 方法2: GitHub Actions による自動デプロイ

#### 1. GitHub Secrets の設定

GitHubリポジトリの設定で以下のSecretsを追加：

**必須:**
- `GOOGLE_CLOUD_PROJECT_ID`: Google CloudプロジェクトID
- `GOOGLE_CLOUD_SA_KEY`: サービスアカウントのJSONキー（後述）
- `NOTION_API_KEY`: Notion APIキー
- `NOTION_DATABASE_ID`: NotionデータベースID
- `GEMINI_API_KEY`: Gemini APIキー

**オプション:**
- `PDF_FILE_PROPERTY_NAME`: PDFファイルプロパティ名（デフォルト: "📄ファイル"）
- `AUDIO_FILE_PROPERTY_NAME`: 録音ファイルプロパティ名（デフォルト: "録音ファイル"）
- `SUMMARY_TOGGLE_H3_TITLE`: 要約セクションタイトル（デフォルト: "📄 AI要約"）
- `MEETING_SUMMARY_TOGGLE_H3_TITLE`: 議事録タイトル（デフォルト: "📝 議事録まとめ"）
- `GEMINI_MODEL`: 使用するGeminiモデル（デフォルト: "gemini-2.5-flash-preview-05-20"）

#### 2. サービスアカウントの作成

```bash
# サービスアカウント作成
gcloud iam service-accounts create github-actions \
    --display-name="GitHub Actions for Cloud Functions"

# 権限付与
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
    --member="serviceAccount:github-actions@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/cloudfunctions.developer"

gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
    --member="serviceAccount:github-actions@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/iam.serviceAccountUser"

# JSONキーファイル作成
gcloud iam service-accounts keys create key.json \
    --iam-account=github-actions@YOUR_PROJECT_ID.iam.gserviceaccount.com

# key.jsonの内容をGitHub Secretsの GOOGLE_CLOUD_SA_KEY に設定
cat key.json
```

#### 3. 自動デプロイの実行

mainブランチにプッシュすると自動的にデプロイが実行されます：

```bash
git add .
git commit -m "Add deployment configuration"
git push origin main
```

### 方法3: Cloud Build による自動デプロイ

#### 1. Secret Manager でシークレットを作成

```bash
# 各環境変数をSecret Managerに保存
echo -n "YOUR_NOTION_API_KEY" | gcloud secrets create NOTION_API_KEY --data-file=-
echo -n "YOUR_NOTION_DATABASE_ID" | gcloud secrets create NOTION_DATABASE_ID --data-file=-
echo -n "YOUR_GEMINI_API_KEY" | gcloud secrets create GEMINI_API_KEY --data-file=-
# 他の環境変数も同様に作成
```

#### 2. Cloud Build トリガーの設定

Google Cloud Consoleで以下を設定：

1. Cloud Build > トリガー > トリガーを作成
2. ソース: GitHub リポジトリを選択
3. イベント: mainブランチへのプッシュ
4. 構成: Cloud Build 構成ファイル（cloudbuild.yaml）

## 🔧 設定項目

### 関数の設定

| 項目 | 値 | 説明 |
|------|-----|-----|
| ランタイム | python312 | Python 3.12 |
| メモリ | 1Gi | 大容量ファイル処理のため |
| タイムアウト | 540s (9分) | Gemini API処理時間を考慮 |
| 最大インスタンス数 | 10 | 同時処理制限 |
| リージョン | asia-northeast1 | 東京リージョン |

### 環境変数

| 変数名 | 必須 | 説明 |
|---------|------|-----|
| `NOTION_API_KEY` | ✅ | Notion Integration API キー |
| `NOTION_DATABASE_ID` | ✅ | 対象NotionデータベースのID |
| `GEMINI_API_KEY` | ✅ | Google AI Studio API キー |
| `PDF_FILE_PROPERTY_NAME` | ❌ | PDFファイルプロパティ名 |
| `AUDIO_FILE_PROPERTY_NAME` | ❌ | 録音ファイルプロパティ名 |
| `SUMMARY_TOGGLE_H3_TITLE` | ❌ | 要約セクションのタイトル |
| `MEETING_SUMMARY_TOGGLE_H3_TITLE` | ❌ | 議事録セクションのタイトル |
| `GEMINI_MODEL` | ❌ | 使用するGeminiモデル名 |

## 📋 デプロイ後の確認

### 1. ヘルスチェック

```bash
curl "https://REGION-PROJECT_ID.cloudfunctions.net/FUNCTION_NAME?action=health"
```

### 2. 機能テスト

```bash
# PDF要約テスト（uid=8の例）
curl -X POST "https://REGION-PROJECT_ID.cloudfunctions.net/FUNCTION_NAME" \
  -H "Content-Type: application/json" \
  -d '{"uid": "8"}'
```

### 3. ログの確認

```bash
# Cloud Functions ログの確認
gcloud functions logs read FUNCTION_NAME --region=REGION

# またはGoogle Cloud Console > Cloud Functions > 関数名 > ログ
```

## 🛠️ トラブルシューティング

### よくある問題

#### 1. 認証エラー
```
Error: (gcloud.functions.deploy) PERMISSION_DENIED
```

**解決方法:**
- `gcloud auth login` で再認証
- サービスアカウントの権限確認
- APIの有効化確認

#### 2. 環境変数エラー
```
ConfigurationError: Missing required environment variable
```

**解決方法:**
- `.env`ファイルの内容確認
- GitHub Secrets の設定確認
- Secret Manager の設定確認

#### 3. タイムアウトエラー
```
Function execution timed out
```

**解決方法:**
- タイムアウト時間の増加（最大9分）
- メモリ割り当ての増加
- 処理の最適化

#### 4. メモリ不足
```
Memory limit exceeded
```

**解決方法:**
- メモリ割り当てを2Gi以上に増加
- 大容量ファイルの処理見直し

### デバッグ方法

#### ローカルでのテスト
```bash
# Functions Framework でローカル実行
functions-framework --target=main --debug
```

#### ログレベルの変更
```bash
# デプロイ時にログレベルを設定
gcloud functions deploy FUNCTION_NAME \
  --set-env-vars="LOG_LEVEL=DEBUG" \
  # その他のオプション...
```

## 🔄 更新とロールバック

### 関数の更新
```bash
# コードの更新後、再デプロイ
./deploy.sh

# または特定のバージョンをデプロイ
gcloud functions deploy FUNCTION_NAME --source=.
```

### ロールバック
```bash
# 以前のバージョンに戻す
gcloud functions deploy FUNCTION_NAME --source=gs://BUCKET/previous-version.zip
```

## 📊 監視とメトリクス

### Cloud Monitoring でのメトリクス確認
- 実行時間
- エラー率
- 呼び出し回数
- メモリ使用量

### アラートの設定
- エラー率が5%を超えた場合
- 実行時間が5分を超えた場合
- 呼び出し失敗が連続した場合

## 💰 コスト最適化

### 推奨設定
- **開発環境**: メモリ512Mi、最大インスタンス数5
- **本番環境**: メモリ1Gi、最大インスタンス数10

### コスト削減のヒント
- 不要な環境変数の削除
- 適切なタイムアウト設定
- インスタンス数の調整

---

## 📞 サポート

問題が発生した場合は以下を確認してください：

1. [Google Cloud Functions ドキュメント](https://cloud.google.com/functions/docs)
2. [Cloud Functions 料金](https://cloud.google.com/functions/pricing)
3. [Python ランタイム](https://cloud.google.com/functions/docs/concepts/python-runtime)

以上でデプロイが完了です！ 🎉 