#!/bin/bash
# EC販売管理ツール - cron バックアップ設定スクリプト
# 使用方法: bash setup_cron.sh [--remove]

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKUP_SCRIPT="$SCRIPT_DIR/backup.py"
LOG_FILE="$SCRIPT_DIR/backups/backup.log"
PYTHON="$(which python3)"

CRON_COMMENT="# ec-tool-backup"
# 毎日 02:00 に実行
CRON_LINE="0 2 * * * $PYTHON $BACKUP_SCRIPT >> $LOG_FILE 2>&1 $CRON_COMMENT"

if [ "$1" = "--remove" ]; then
    echo "cron ジョブを削除中..."
    crontab -l 2>/dev/null | grep -v "$CRON_COMMENT" | crontab -
    echo "✓ 削除しました"
    exit 0
fi

# バックアップディレクトリを作成
mkdir -p "$SCRIPT_DIR/backups"

# 現在の crontab を取得し、既存エントリを除いて新規追加
(crontab -l 2>/dev/null | grep -v "$CRON_COMMENT"; echo "$CRON_LINE") | crontab -

echo "✓ cron ジョブを設定しました"
echo "  スケジュール: 毎日 02:00"
echo "  スクリプト:   $BACKUP_SCRIPT"
echo "  ログ:         $LOG_FILE"
echo ""
echo "現在の設定:"
crontab -l | grep -v "^#" | grep backup
echo ""
echo "今すぐ実行: python3 $BACKUP_SCRIPT"
echo "一覧表示:   python3 $BACKUP_SCRIPT --list"
echo "cron削除:   bash $0 --remove"
