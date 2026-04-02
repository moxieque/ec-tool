#!/bin/bash
# ============================================================
#  EC販売管理ツール — 起動スクリプト
#  ダブルクリックするだけで起動できます
# ============================================================

# このスクリプトが置かれているフォルダへ移動
cd "$(dirname "$0")"

echo "================================================"
echo "  EC販売管理ツール 起動スクリプト"
echo "================================================"
echo ""

# ─────────────────────────────────────────
# 1. Python3 の確認・自動インストール
# ─────────────────────────────────────────
echo "▶ Python3 を確認中..."
if ! command -v python3 &>/dev/null; then
  echo ""
  echo "  Python3 が見つかりません。インストーラーを自動ダウンロードします..."
  echo "  （インターネット接続が必要です。しばらくお待ちください）"
  echo ""

  # python.org の最新 macOS 安定版インストーラーURLを取得
  PYTHON_PKG_URL=$(curl -sL https://www.python.org/downloads/ \
    | grep -o 'https://www.python.org/ftp/python/[^"]*macos11\.pkg' \
    | head -1)

  if [ -z "$PYTHON_PKG_URL" ]; then
    # フォールバック：固定バージョン
    PYTHON_PKG_URL="https://www.python.org/ftp/python/3.13.2/python-3.13.2-macos11.pkg"
  fi

  INSTALLER_PATH="/tmp/python_installer.pkg"
  echo "  ダウンロード中: $PYTHON_PKG_URL"
  curl -L --progress-bar -o "$INSTALLER_PATH" "$PYTHON_PKG_URL"

  if [ $? -ne 0 ] || [ ! -f "$INSTALLER_PATH" ]; then
    echo ""
    echo "【エラー】ダウンロードに失敗しました。"
    echo "インターネット接続を確認し、再度お試しください。"
    read -p "Enterキーを押すと閉じます..."
    exit 1
  fi

  echo ""
  echo "  インストーラーを開きます。"
  echo "  ─────────────────────────────────────────"
  echo "  画面の指示に従ってインストールを完了させてください："
  echo "    「続ける」→「続ける」→「同意する」→「インストール」"
  echo "  ─────────────────────────────────────────"
  echo ""
  echo "  ✅ インストールが終わったら、"
  echo "     このウィンドウを閉じて「起動.command」を再度ダブルクリックしてください。"
  echo ""

  open "$INSTALLER_PATH"
  read -p "（インストールが終わったらEnterキーを押してください）"

  # インストール後に再確認
  if ! command -v python3 &>/dev/null; then
    echo ""
    echo "【エラー】Python3 がまだ見つかりません。"
    echo "インストールが完了しているか確認してから、再度「起動.command」をダブルクリックしてください。"
    read -p "Enterキーを押すと閉じます..."
    exit 1
  fi

  echo "  OK: Python3 のインストールが確認できました。起動を続けます..."
  echo ""
fi

PYTHON_VER=$(python3 --version 2>&1)
echo "  OK: $PYTHON_VER"
echo ""

# ─────────────────────────────────────────
# 2. 必要ライブラリのインストール（未導入の場合のみ）
# ─────────────────────────────────────────
echo "▶ 必要なライブラリを確認中..."

NEED_INSTALL=0
python3 -c "import flask" 2>/dev/null        || NEED_INSTALL=1
python3 -c "import flask_cors" 2>/dev/null   || NEED_INSTALL=1
python3 -c "import playwright" 2>/dev/null   || NEED_INSTALL=1

if [ "$NEED_INSTALL" -eq 1 ]; then
  echo "  ライブラリをインストールします（初回のみ・数分かかります）..."
  echo ""
  pip3 install flask flask-cors playwright --quiet --disable-pip-version-check
  if [ $? -ne 0 ]; then
    echo ""
    echo "【エラー】ライブラリのインストールに失敗しました。"
    echo "インターネット接続を確認してください。"
    read -p "Enterキーを押すと閉じます..."
    exit 1
  fi
  echo "  OK: ライブラリをインストールしました"
else
  echo "  OK: ライブラリは導入済みです"
fi
echo ""

# ─────────────────────────────────────────
# 3. Playwright ブラウザのインストール（未導入の場合のみ）
# ─────────────────────────────────────────
PLAYWRIGHT_DIR="$HOME/Library/Caches/ms-playwright"
if [ ! -d "$PLAYWRIGHT_DIR" ] || [ -z "$(ls -A "$PLAYWRIGHT_DIR" 2>/dev/null)" ]; then
  echo "▶ ブラウザコンポーネントをインストール中（初回のみ）..."
  python3 -m playwright install chromium --quiet
  if [ $? -ne 0 ]; then
    echo ""
    echo "【警告】ブラウザのインストールに失敗しました。"
    echo "ラクマート自動取込が使えない場合があります。"
    echo "手動で「python3 -m playwright install chromium」を実行してください。"
    echo ""
  else
    echo "  OK: ブラウザをインストールしました"
    echo ""
  fi
fi

# ─────────────────────────────────────────
# 4. サーバー起動 & ブラウザを自動で開く
# ─────────────────────────────────────────
echo "▶ サーバーを起動中..."
echo ""

# 3秒後にブラウザを開く（サーバー起動を待つ）
(sleep 3 && open "http://localhost:8080") &

python3 app.py

# サーバーが終了したらメッセージを表示
echo ""
echo "================================================"
echo "  サーバーが停止しました。"
echo "  このウィンドウを閉じてください。"
echo "================================================"
read -p ""
