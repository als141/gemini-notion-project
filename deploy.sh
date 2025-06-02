#!/bin/bash

# Cloud Functions デプロイスクリプト
# 使用方法: ./deploy.sh [FUNCTION_NAME] [REGION] [PROJECT_ID]

set -e

# デフォルト値
DEFAULT_FUNCTION_NAME="gemini-notion-processor"
DEFAULT_REGION="asia-northeast1"
DEFAULT_PROJECT=""

# パラメータの設定
FUNCTION_NAME=${1:-$DEFAULT_FUNCTION_NAME}
REGION=${2:-$DEFAULT_REGION}
PROJECT_ID=${3:-$DEFAULT_PROJECT}

# 色付きメッセージ関数
print_info() {
    echo -e "\033[1;34m[INFO]\033[0m $1"
}

print_success() {
    echo -e "\033[1;32m[SUCCESS]\033[0m $1"
}

print_error() {
    echo -e "\033[1;31m[ERROR]\033[0m $1"
}

print_warning() {
    echo -e "\033[1;33m[WARNING]\033[0m $1"
}

# プロジェクトIDの確認
if [ -z "$PROJECT_ID" ]; then
    print_error "Google Cloud Project IDが設定されていません。"
    print_info "以下のいずれかの方法で設定してください："
    print_info "1. 引数で指定: ./deploy.sh $FUNCTION_NAME $REGION YOUR_PROJECT_ID"
    print_info "2. gcloud設定: gcloud config set project YOUR_PROJECT_ID"
    print_info "3. 環境変数: export GOOGLE_CLOUD_PROJECT=YOUR_PROJECT_ID"
    exit 1
fi

print_info "デプロイ設定："
print_info "  関数名: $FUNCTION_NAME"
print_info "  リージョン: $REGION"
print_info "  プロジェクトID: $PROJECT_ID"

# .envファイルの確認
if [ ! -f ".env" ]; then
    print_error ".envファイルが見つかりません。"
    print_info ".env.exampleを参考に.envファイルを作成してください。"
    exit 1
fi

# 必要な環境変数の確認
print_info "環境変数の確認中..."
source .env

required_vars=(
    "NOTION_API_KEY"
    "NOTION_DATABASE_ID" 
    "GEMINI_API_KEY"
)

missing_vars=()
for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        missing_vars+=("$var")
    fi
done

if [ ${#missing_vars[@]} -gt 0 ]; then
    print_error "以下の環境変数が設定されていません："
    for var in "${missing_vars[@]}"; do
        print_error "  - $var"
    done
    exit 1
fi

print_success "環境変数の確認完了"

# gcloud認証の確認
print_info "Google Cloud認証の確認中..."
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q "@"; then
    print_error "Google Cloudに認証されていません。"
    print_info "以下のコマンドで認証してください："
    print_info "  gcloud auth login"
    exit 1
fi

print_success "認証確認完了"

# プロジェクトの設定
print_info "プロジェクトの設定中..."
gcloud config set project $PROJECT_ID

# APIの有効化確認
print_info "必要なAPIの確認中..."
apis=(
    "cloudfunctions.googleapis.com"
    "cloudbuild.googleapis.com"
    "artifactregistry.googleapis.com"
)

for api in "${apis[@]}"; do
    if ! gcloud services list --enabled --filter="name:$api" --format="value(name)" | grep -q "$api"; then
        print_warning "API $api が無効です。有効化しています..."
        gcloud services enable $api
    fi
done

print_success "API確認完了"

# 環境変数の設定文字列を作成
ENV_VARS="NOTION_API_KEY=$NOTION_API_KEY"
ENV_VARS="$ENV_VARS,NOTION_DATABASE_ID=$NOTION_DATABASE_ID"
ENV_VARS="$ENV_VARS,GEMINI_API_KEY=$GEMINI_API_KEY"

# オプション環境変数（設定されている場合のみ追加）
[ ! -z "$PDF_FILE_PROPERTY_NAME" ] && ENV_VARS="$ENV_VARS,PDF_FILE_PROPERTY_NAME=$PDF_FILE_PROPERTY_NAME"
[ ! -z "$AUDIO_FILE_PROPERTY_NAME" ] && ENV_VARS="$ENV_VARS,AUDIO_FILE_PROPERTY_NAME=$AUDIO_FILE_PROPERTY_NAME"
[ ! -z "$SUMMARY_TOGGLE_H3_TITLE" ] && ENV_VARS="$ENV_VARS,SUMMARY_TOGGLE_H3_TITLE=$SUMMARY_TOGGLE_H3_TITLE"
[ ! -z "$MEETING_SUMMARY_TOGGLE_H3_TITLE" ] && ENV_VARS="$ENV_VARS,MEETING_SUMMARY_TOGGLE_H3_TITLE=$MEETING_SUMMARY_TOGGLE_H3_TITLE"
[ ! -z "$GEMINI_MODEL" ] && ENV_VARS="$ENV_VARS,GEMINI_MODEL=$GEMINI_MODEL"

# デプロイ実行
print_info "Cloud Functionsにデプロイ中..."
print_info "これには数分かかる場合があります..."

gcloud functions deploy $FUNCTION_NAME \
    --gen2 \
    --runtime=python312 \
    --region=$REGION \
    --source=. \
    --entry-point=main \
    --trigger-http \
    --timeout=540s \
    --memory=1Gi \
    --max-instances=10 \
    --allow-unauthenticated \
    --set-env-vars="$ENV_VARS"

if [ $? -eq 0 ]; then
    print_success "デプロイが完了しました！"
    
    # 関数URLの取得
    FUNCTION_URL=$(gcloud functions describe $FUNCTION_NAME --region=$REGION --format="value(serviceConfig.uri)")
    print_success "関数URL: $FUNCTION_URL"
    
    # ヘルスチェック
    print_info "ヘルスチェック実行中..."
    if curl -s -f "$FUNCTION_URL?action=health" > /dev/null; then
        print_success "ヘルスチェック成功"
        print_info "テスト用URL例："
        print_info "  ヘルスチェック: $FUNCTION_URL?action=health"
        print_info "  PDF要約: $FUNCTION_URL?uid=8"
    else
        print_warning "ヘルスチェックに失敗しました。設定を確認してください。"
    fi
else
    print_error "デプロイに失敗しました。"
    exit 1
fi

print_success "すべての処理が完了しました！" 