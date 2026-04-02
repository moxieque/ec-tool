# Moxieque EC販売管理ツール — セッション引き継ぎ資料
作成日: 2026-04-02（最終更新）

---

## 📁 プロジェクト構成

```
moxieque-ec-tool/
├── index_local.html     ← フロントエンド（Flask版・本番）★メイン編集対象
├── app.py               ← Flaskサーバー（ポート8080）
├── rakumart_server.py   ← ラクマート連携サーバー（ポート8766）
├── data/
│   ├── products.json        商品マスタデータ
│   ├── purchases.json       仕入れデータ
│   ├── sales.json           販売データ
│   ├── inventory_history.json 在庫編集履歴
│   └── config.json          設定ファイル（lowStockThreshold等）
├── static/images/       商品画像置き場
├── backup.py            バックアップスクリプト
├── Code.gs              ※旧GAS版（未使用）
└── Index.html           ※旧GAS版HTML（未使用）
```

> ⚠️ **重要**: 本番で使用するのは `index_local.html` + `app.py` のFlask構成。

---

## 🚀 サーバー起動方法

```bash
cd /Users/inamikatsutoshi/Documents/Claude/moxieque-ec-tool
python3 app.py
# → http://localhost:8080 でアクセス
# → rakumart_server.py (ポート8766) は app.py が自動起動
```

---

## ✅ 実装済み機能（完了）

### タブ構成（7タブ）
| タブ | 機能 |
|------|------|
| 📊 ダッシュボード | 月次売上・仕入れ・粗利サマリー（期間選択：今月/3ヶ月/6ヶ月/1年/全期間） |
| 📥 仕入れ管理 | ラクマート一括 / 個別登録 / CSV一括 |
| 📤 販売登録 | 販売登録・編集・削除・原価リアルタイム表示 |
| 📦 在庫一覧 | 在庫数直接編集・履歴記録・僅少警告 |
| 💰 利益レポート | 月次・商品別・チャネル別レポート |
| 🏷️ 商品マスタ | 商品登録・一覧・CSVダウンロード・CSVアップロード |
| ⚙️ 設定 | アラート閾値・デフォルト手数料率・バックアップ |

### 今セッションで完了した機能
- ✅ **過去の配送依頼書から一括仕入れ** — 複数選択チェックボックス → 「🚀 一括取得」で全商品を按分フォームへ反映
- ✅ **設定タブ実装** — 在庫アラート閾値・デフォルト手数料率・売上計算方式・ラクマートサーバー状態・バックアップダウンロード
- ✅ **Rakumart サーバー修正** — `scrape_delivery_by_order_sn()` 関数追加、クエリ文字列パース対応

### 過去セッションで完了した機能
- ラクマート仕入れ自動取込（Playwright + rakumart_server.py）
- 按分仕入れ（国際送料の按分計算）+ スキップ機能
- 在庫数リアルタイム直接編集（変更履歴自動記録）
- 移動平均法による原価計算
- 販売登録時の商品原価・粗利リアルタイム表示
- ダッシュボード期間選択（プルダウン）
- 商品マスタCSVダウンロード・アップロード（UTF-8 BOM対応）
- エラーハンドリング強化（showToast・showOfflineBanner）
- ラクマートサーバー状態表示（仕入れ管理タブ内）

### APIエンドポイント一覧（app.py）
| エンドポイント | 機能 |
|---------------|------|
| /api/getProducts | 商品マスタ取得 |
| /api/addProduct | 商品登録 |
| /api/addProductsBulk | 商品一括登録 |
| /api/deleteProductAll | 商品削除 |
| /api/deleteProductsBulk | 商品一括削除 |
| /api/updateProductMasterField | 商品フィールド更新 |
| /api/updateProductsBulkFromCSV | CSVから商品一括更新 |
| /api/getPurchases | 仕入れ一覧取得 |
| /api/addPurchase | 仕入れ登録 |
| /api/addPurchasesBulk | 仕入れ一括登録（按分） |
| /api/getSales | 販売一覧取得 |
| /api/addSale | 販売登録 |
| /api/updateSale | 販売編集 |
| /api/deleteSale | 販売削除 |
| /api/getInventory | 在庫一覧（移動平均原価含む） |
| /api/updateInventoryDirect | 在庫数直接更新 |
| /api/getDashboardData | ダッシュボードデータ（period パラメータ対応） |
| /api/getProfitReport | 利益レポート |
| /api/getChannels | 販売チャネル一覧 |
| /api/getConfig | 設定取得 |
| /api/saveConfig | 設定保存 |
| /api/startRakumartServer | ラクマートサーバー起動 |
| /api/checkRakumartServer | ラクマートサーバー死活確認 |
| /api/getRakumartLatest | 配送依頼書取得プロキシ（orderSn パラメータ対応） |
| /api/getRakumartDeliveryList | 配送依頼書一覧プロキシ |
| /api/matchProductByImageHash | 画像ハッシュで商品照合 |
| /api/exportCsv/<sheet> | CSVエクスポート |

---

## 🔲 次のセッションでやること

### 🎯 最優先：取扱説明書（配布用マニュアル）の作成

- **形式**: HTML形式（印刷時にPDF化可能なスタイル）
- **保存場所**: `moxieque-ec-tool/manual/index.html`（新規フォルダ）
- **対象読者**: 非エンジニアのEC事業者
- **作成方法**: Claude に依頼、スクリーンショットは手動キャプチャでよい

#### 必須ページ構成
1. **はじめに** — このツールで何ができるか（概要）
2. **インストール・起動方法** — Python/pip インストール、起動コマンド
3. **ダッシュボードの見方** — 期間選択、各指標の説明
4. **仕入れ管理** — ラクマート自動取込・按分計算・CSV取込の手順
5. **販売登録** — 販売入力・編集・削除
6. **在庫一覧** — 在庫数編集・アラートの見方
7. **利益レポート** — 各レポートの読み方
8. **商品マスタ** — 商品登録・CSV操作
9. **設定** — 各設定項目の説明
10. **ラクマート連携設定** — 初回ログイン手順
11. **バックアップ・復元** — データの守り方
12. **トラブルシューティング** — よくある問題と対処法

#### スタイル要件
- 日本語・シンプルで読みやすいレイアウト
- 目次（左サイドバーまたはアンカーリンク）
- 各操作手順はナンバリング
- 重要事項はボックス囲い（注意・ヒント）
- 印刷 / PDF 化できるスタイル

---

## 🐛 既知の問題・注意点

1. **一括取得の動作**: 複数配送依頼書の「一括取得」は動作するが、各スクレイピングに20〜30秒かかる。UI 上はローディングが表示される。
2. **GAS版ファイル残存**: `Index.html` と `Code.gs` はFlask移行後も残っている（未使用）。
3. **ラクマートサーバー**: `rakumart_server.py` は別プロセス（ポート8766）で起動。`app.py` から自動起動。初回はブラウザでログインが必要。
4. **画像パス**: 商品画像は `static/images/` に保存。別PCへの移行時はフォルダごとコピーが必要。
5. **データ保存形式**: JSONファイル（`data/`フォルダ）。複数人同時使用は非対応。
6. **バックアップ復元**: 設定タブの「バックアップから復元」ボタンは UI のみ実装済み。実際の復元処理（`/api/restoreFromBackup`）は未実装。

---

## 💡 技術メモ

- **原価計算**: 移動平均法（`app.py` の `calculate_inventory()` 関数）
- **フロントエンドのAPI呼び出し**: `fetch('/api/エンドポイント', {method:'POST', ...})` を共通 `api()` 関数でラップ（15秒タイムアウト付き）
- **商品選択値の形式**: `名前||SKU||未使用||avgCost||画像URL` （パイプ区切り）
- **粗利計算**: `_saleCostPrice` グローバル変数に選択商品の原価を保持、`calcSaleTotal()` で計算
- **在庫履歴**: `data/inventory_history.json` に記録（日時・SKU・変更前後）
- **設定ファイル**: `data/config.json`（`lowStockThreshold`, `defaultFeeRate`, `defaultCalculation`）
- **ラクマート過去配送依頼書取得**: `scrape_delivery_by_order_sn(order_sn)` — rakumart_server.py に追加済み。クエリ文字列は urllib.parse.urlparse で分割。
- **按分仕入れのデータ構造**: `_abnPurchaseData` グローバル配列。各要素に `name`, `sku`, `qty`, `baseUnitCost`, `supplier`, `memo`, `imageUrl` などを格納。

---

## 📊 データ量（2026-04-02時点）

| データ | 件数 |
|--------|------|
| 商品マスタ | 約40件 |
| 仕入れ | 複数件 |
| 販売 | 数件 |
| 配送依頼書履歴 | 10件（ラクマート） |
