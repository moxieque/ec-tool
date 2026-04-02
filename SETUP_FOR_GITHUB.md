# GitHub リポジトリへのプッシュ手順

このドキュメントは開発者向けです。GitHub Actions で自動ビルドするための初期セットアップ手順を説明しています。

---

## 📋 セットアップ手順

### 1. GitHub にリポジトリを作成

**Web ブラウザで実行：**

1. https://github.com/new にアクセス
2. Repository name: `ec-tool`
3. Description: `EC Sales Management Tool - Python/Flask based inventory and sales management`
4. Visibility: **Public**
5. 他のオプションはデフォルト
6. **Create repository** をクリック

---

### 2. ローカルで git にファイルを追加

ターミナルで実行：

```bash
cd /Users/inamikatsutoshi/Documents/Claude/moxieque-ec-tool

# ファイルを追加
git add .

# コミット
git commit -m "Initial commit: EC Sales Management Tool"
```

---

### 3. リモートリポジトリを追加してプッシュ

```bash
# リモートを追加（YOUR_USERNAME を moxieque に置き換え）
git remote add origin https://github.com/moxieque/ec-tool.git

# ブランチ名を main に変更（必要に応じて）
git branch -M main

# プッシュ
git push -u origin main
```

---

### 4. リリースタグを作成してビルド実行

```bash
# バージョンタグを作成（これで GitHub Actions が自動実行される）
git tag v1.0.0

# タグをプッシュ
git push origin v1.0.0
```

---

## 🚀 ビルド確認

1. GitHub リポジトリを開く: https://github.com/moxieque/ec-tool
2. **Actions** タブをクリック
3. ビルドジョブが実行中であることを確認
4. 完了するまで待つ（5～10分程度）

---

## 📦 ビルド成果物のダウンロード

### 方法1：Artifacts から（最新ビルド）
1. Actions タブで最新の実行結果をクリック
2. **Artifacts** セクションから：
   - `ec-tool-windows` (EXE)
   - `ec-tool-macos` (DMG)

### 方法2：Releases から（正式リリース）
1. **Releases** タブをクリック
2. 最新版のリリースをクリック
3. EXE と DMG をダウンロード

---

## 📝 今後の更新手順

プログラムを更新した場合：

```bash
# 変更をコミット
git add .
git commit -m "Update: 新機能を追加"

# プッシュ
git push origin main

# 新しいバージョンをリリース
git tag v1.0.1
git push origin v1.0.1
```

---

## 🔗 Google Drive への配布

完成した EXE/DMG を Google Drive にアップロード：

1. Google Drive を開く
2. 新しいフォルダ「ec-tool」を作成
3. Releases からダウンロードした EXE と DMG をアップロード
4. 共有リンクを取得
5. ユーザーに配布

---

## ⚠️ トラブルシューティング

### ビルドが失敗する場合

**確認事項：**
1. `app.py` が Python 3.11 互換か
2. すべての依存ライブラリが pip でインストール可能か
3. `.gitignore` で除外されたファイル（`__pycache__` など）がないか

### パッケージサイズが大きい場合

PyInstaller は 100～150MB の EXE を生成します（Flask + Playwright 含む）。サイズが大きい場合は以下で最適化：

```bash
pyinstaller --onefile --windowed --strip app.py
```

---

## 📚 参考リンク

- [PyInstaller 公式ドキュメント](https://pyinstaller.org/)
- [GitHub Actions ドキュメント](https://docs.github.com/ja/actions)
- [GitHub Releases 機能](https://docs.github.com/ja/repositories/releasing-projects-on-github/about-releases)
