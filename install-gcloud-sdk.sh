#!/bin/bash

# Google Cloud SDK インストールスクリプト
# Ubuntu/Debian 用

set -e

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

print_info "Google Cloud SDK インストールを開始します..."

# 1. システムの更新
print_info "システムパッケージを更新しています..."
sudo apt-get update

# 2. 必要なパッケージのインストール
print_info "必要なパッケージをインストールしています..."
sudo apt-get install -y apt-transport-https ca-certificates gnupg curl

# 3. Google Cloud SDK リポジトリキーの追加
print_info "Google Cloud SDK リポジトリキーを追加しています..."
curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | sudo gpg --dearmor -o /usr/share/keyrings/cloud.google.gpg

# 4. Google Cloud SDK リポジトリの追加
print_info "Google Cloud SDK リポジトリを追加しています..."
echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] https://packages.cloud.google.com/apt cloud-sdk main" | sudo tee -a /etc/apt/sources.list.d/google-cloud-sdk.list

# 5. パッケージリストの更新
print_info "パッケージリストを更新しています..."
sudo apt-get update

# 6. Google Cloud SDK のインストール
print_info "Google Cloud SDK をインストールしています..."
sudo apt-get install -y google-cloud-cli

# 7. 追加コンポーネントのインストール（オプション）
print_info "追加コンポーネントをインストールしています..."
sudo apt-get install -y google-cloud-cli-gke-gcloud-auth-plugin

# 8. インストール確認
print_info "インストールを確認しています..."
if command -v gcloud &> /dev/null; then
    GCLOUD_VERSION=$(gcloud version --format="value(Google Cloud SDK)")
    print_success "Google Cloud SDK のインストールが完了しました！"
    print_success "バージョン: $GCLOUD_VERSION"
else
    print_error "インストールに失敗しました。"
    exit 1
fi

# 9. 初期設定の案内
print_info "次のステップ："
print_info "1. Google Cloud にログイン: gcloud auth login"
print_info "2. プロジェクト設定: gcloud config set project YOUR_PROJECT_ID"
print_info "3. 設定確認: gcloud config list"

print_success "インストールスクリプトが完了しました！" 