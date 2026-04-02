#!/usr/bin/env python3
"""
EC販売管理ツール - ローカルCSVバックアップスクリプト
使用方法:
  python3 backup.py              # 今すぐバックアップ
  python3 backup.py --list       # バックアップ一覧
  python3 backup.py --restore YYYY-MM-DD_HH-MM  # 指定バックアップをlatestにコピー
"""

import os
import sys
import ssl
import shutil
import urllib.request
import urllib.parse
from datetime import datetime
from pathlib import Path

# macOS の Python では SSL 証明書が自動設定されないため対処
ssl._create_default_https_context = ssl._create_unverified_context

# =============================================
# 設定
# =============================================
GAS_URL = "https://script.google.com/macros/s/AKfycbymKxBldscBVtf8f9uEW7sA9dTImtL8P6ymsH3D3gXjqBdlhlybzDOC_oVCGiF0yWSK0Q/exec"
CSV_TOKEN = "mxq2026bk_c9f3a1e8d7"

SHEETS = [
    ("products",  "商品マスタ"),
    ("purchases", "仕入れ"),
    ("sales",     "販売"),
]

SCRIPT_DIR  = Path(__file__).parent
BACKUP_ROOT = SCRIPT_DIR / "backups"
KEEP_COUNT  = 90   # 保持するバックアップ数


# =============================================
# CSV 取得
# =============================================
def fetch_csv(sheet_key: str) -> str:
    """curl を使ってリダイレクトを正しく処理し CSV を取得する"""
    url = GAS_URL + "?action=csv&sheet=" + urllib.parse.quote(sheet_key) + "&token=" + CSV_TOKEN
    import subprocess
    result = subprocess.run(
        ["curl", "-L", "-s", "--max-redirs", "10",
         "-H", "User-Agent: Mozilla/5.0",
         url],
        capture_output=True, text=True, timeout=60
    )
    if result.returncode != 0:
        raise RuntimeError(f"curl error: {result.stderr}")
    content = result.stdout
    # ログインページが返ってきた場合はエラー
    if content.strip().startswith("<!") or "<html" in content[:200].lower():
        raise RuntimeError("Received HTML instead of CSV — check GAS deployment access settings")
    return content


# =============================================
# バックアップ実行
# =============================================
def run_backup():
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    backup_dir = BACKUP_ROOT / timestamp
    backup_dir.mkdir(parents=True, exist_ok=True)

    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] バックアップ開始 → {backup_dir}")

    errors = []
    for sheet_key, sheet_label in SHEETS:
        try:
            print(f"  取得中: {sheet_label} ({sheet_key}) ...", end=" ", flush=True)
            csv_data = fetch_csv(sheet_key)
            out_file = backup_dir / f"{sheet_key}.csv"
            out_file.write_text(csv_data, encoding="utf-8-sig")  # BOM付きでExcel互換
            lines = csv_data.count("\n")
            print(f"OK ({lines} 行, {len(csv_data):,} bytes)")
        except Exception as e:
            print(f"ERROR: {e}")
            errors.append((sheet_label, str(e)))

    if errors:
        print(f"\n警告: {len(errors)}件のエラーが発生しました:")
        for label, msg in errors:
            print(f"  {label}: {msg}")
        # エラーログ保存
        (backup_dir / "errors.txt").write_text(
            "\n".join(f"{l}: {m}" for l, m in errors), encoding="utf-8"
        )
    else:
        # latest ディレクトリを更新（コピー）
        latest_dir = BACKUP_ROOT / "latest"
        if latest_dir.exists():
            shutil.rmtree(latest_dir)
        shutil.copytree(backup_dir, latest_dir)
        print(f"\n  latest/ を更新しました")

    # 古いバックアップを削除
    cleanup_old_backups()

    print(f"\n✓ バックアップ完了: {backup_dir}")
    return len(errors) == 0


# =============================================
# 古いバックアップ削除
# =============================================
def cleanup_old_backups():
    dirs = sorted([
        d for d in BACKUP_ROOT.iterdir()
        if d.is_dir() and d.name not in ("latest",) and d.name[0].isdigit()
    ])
    while len(dirs) > KEEP_COUNT:
        old = dirs.pop(0)
        shutil.rmtree(old)
        print(f"  削除: {old.name} (保持上限 {KEEP_COUNT} 件)")


# =============================================
# バックアップ一覧表示
# =============================================
def list_backups():
    if not BACKUP_ROOT.exists():
        print("バックアップなし")
        return
    dirs = sorted([
        d for d in BACKUP_ROOT.iterdir()
        if d.is_dir() and d.name not in ("latest",) and d.name[0].isdigit()
    ], reverse=True)
    print(f"バックアップ一覧 ({len(dirs)} 件):")
    for d in dirs:
        files = list(d.glob("*.csv"))
        size = sum(f.stat().st_size for f in files)
        print(f"  {d.name}  ({len(files)} files, {size:,} bytes)")


# =============================================
# エントリーポイント
# =============================================
if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--list":
        list_backups()
    elif len(sys.argv) > 2 and sys.argv[1] == "--restore":
        target = BACKUP_ROOT / sys.argv[2]
        if not target.exists():
            print(f"ERROR: {sys.argv[2]} が見つかりません")
            sys.exit(1)
        latest_dir = BACKUP_ROOT / "latest"
        if latest_dir.exists():
            shutil.rmtree(latest_dir)
        shutil.copytree(target, latest_dir)
        print(f"✓ {sys.argv[2]} を latest/ にコピーしました")
    else:
        success = run_backup()
        sys.exit(0 if success else 1)
