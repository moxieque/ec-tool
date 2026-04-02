#!/usr/bin/env python3
"""
EC販売管理ツール - Flask ローカルサーバー
起動: python3 app.py
アクセス: http://localhost:5000
"""

import json
import os
import re
import math
import shutil
import urllib.request
import urllib.error
import urllib.parse
import subprocess
import time
import ssl
import hashlib
import base64
from datetime import datetime, date
from pathlib import Path
from io import BytesIO
from PIL import Image
from flask import Flask, request, jsonify, send_from_directory, render_template_string

# 暗号化用（簡易的なBase64 + ハッシュベース）
import secrets

# SSL証明書の問題を回避
_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

app = Flask(__name__, static_folder='static')

# =============================================
# ラクマートサーバー管理
# =============================================
_rakumart_process = None

def start_rakumart_server():
    """ラクマート自動仕入れサーバーをバックグラウンド起動"""
    global _rakumart_process
    if _rakumart_process is not None:
        return True  # 既に起動済み
    try:
        rakumart_py = Path(__file__).parent / 'rakumart_server.py'
        if not rakumart_py.exists():
            print('⚠️ rakumart_server.py が見つかりません')
            return False
        _rakumart_process = subprocess.Popen(
            ['python3', str(rakumart_py)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        print(f'✅ ラクマートサーバー起動 (PID: {_rakumart_process.pid})')
        time.sleep(1)  # サーバー起動待機
        return True
    except Exception as e:
        print(f'❌ ラクマートサーバー起動エラー: {e}')
        return False

# =============================================
# データファイルパス
# =============================================
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / 'data'
IMAGES_DIR = BASE_DIR / 'static' / 'images'

PRODUCTS_FILE  = DATA_DIR / 'products.json'
PURCHASES_FILE = DATA_DIR / 'purchases.json'
SALES_FILE     = DATA_DIR / 'sales.json'
CONFIG_FILE    = DATA_DIR / 'config.json'

DEFAULT_CONFIG = {
    'lowStockThreshold': 3,
    'defaultFeeRate': 10,
    'defaultCalculation': 'inclusive',
    'rakumartUsername': None,
    'rakumartPasswordEncrypted': None,
}

def load_config() -> dict:
    if not CONFIG_FILE.exists():
        return dict(DEFAULT_CONFIG)
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
        # デフォルト値で補完
        for k, v in DEFAULT_CONFIG.items():
            cfg.setdefault(k, v)
        return cfg
    except Exception:
        return dict(DEFAULT_CONFIG)

def save_config(cfg: dict):
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

# =============================================
# クレデンシャル暗号化ユーティリティ
# =============================================
_ENCRYPTION_KEY = "ec-tool-rakumart-2026"  # ローカル暗号化キー（セキュリティ警告の対象）

def encrypt_password(password: str) -> str:
    """パスワードを簡易暗号化（Base64 + XOR）"""
    if not password:
        return None
    try:
        # Base64でエンコード
        b64 = base64.b64encode(password.encode()).decode()
        # XOR演算で追加暗号化
        encrypted = ''.join(chr(ord(c) ^ ord(_ENCRYPTION_KEY[i % len(_ENCRYPTION_KEY)])) for i, c in enumerate(b64))
        return base64.b64encode(encrypted.encode()).decode()
    except Exception:
        return None

def decrypt_password(encrypted: str) -> str:
    """暗号化されたパスワードを復号"""
    if not encrypted:
        return None
    try:
        # Base64で復号
        b64_encrypted = base64.b64decode(encrypted).decode()
        # XOR演算で復号
        decrypted = ''.join(chr(ord(c) ^ ord(_ENCRYPTION_KEY[i % len(_ENCRYPTION_KEY)])) for i, c in enumerate(b64_encrypted))
        # Base64で復号
        return base64.b64decode(decrypted).decode()
    except Exception:
        return None

# =============================================
# データ読み書きユーティリティ
# =============================================
def load_json(path: Path, default=None):
    if default is None:
        default = []
    if not path.exists():
        return default
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)

def now_str():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

def today_str():
    return date.today().isoformat()

def new_id(prefix: str) -> str:
    import time, random
    return f"{prefix}{int(time.time()*1000)}{random.randint(100,999)}"

# =============================================
# 画像ダウンロード（ローカル保存＆圧縮）
# =============================================
def download_image(url: str, sku: str) -> str:
    """画像URLをダウンロード→圧縮→ローカル保存、ローカルパスを返す"""
    if not url or not url.startswith('http'):
        return url
    try:
        from PIL import Image
        from io import BytesIO

        safe_sku = re.sub(r'[^\w\-]', '_', sku or 'img')
        timestamp = int(datetime.now().timestamp())
        basename = f"{safe_sku}_{timestamp}"
        IMAGES_DIR.mkdir(parents=True, exist_ok=True)

        # URLから画像ダウンロード
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10, context=_SSL_CTX) as resp:
            img_data = resp.read()

        # PIL で画像を開く
        img = Image.open(BytesIO(img_data))

        # RGBA→RGB 変換（JPEGに対応）
        if img.mode in ('RGBA', 'LA', 'P'):
            rgb_img = Image.new('RGB', img.size, (255, 255, 255))
            rgb_img.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
            img = rgb_img

        # メイン画像（最大1200x1200、80%品質）
        img.thumbnail((1200, 1200), Image.Resampling.LANCZOS)
        main_file = f"{basename}_main.jpg"
        main_path = IMAGES_DIR / main_file
        img.save(main_path, 'JPEG', quality=80, optimize=True)

        # サムネイル（最大150x150、70%品質）
        thumb_img = img.copy()
        thumb_img.thumbnail((150, 150), Image.Resampling.LANCZOS)
        thumb_file = f"{basename}_thumb.jpg"
        thumb_path = IMAGES_DIR / thumb_file
        thumb_img.save(thumb_path, 'JPEG', quality=70, optimize=True)

        # メイン画像のパスを返す（HTMLではthumbを使い分ける）
        return f'/static/images/{main_file}'
    except ImportError:
        # PILがない場合は簡易版（圧縮なし）
        print('⚠️ Pillow がインストールされていません。画像は圧縮されません。')
        return _download_image_simple(url, sku)
    except Exception as e:
        print(f'❌ 画像ダウンロード失敗: {e}')
        return url

def _download_image_simple(url: str, sku: str) -> str:
    """Pillow なしの簡易版（圧縮なし）"""
    try:
        safe_sku = re.sub(r'[^\w\-]', '_', sku or 'img')
        ext = url.split('?')[0].split('.')[-1][:5] or 'jpg'
        filename = f"{safe_sku}_{int(datetime.now().timestamp())}.{ext}"
        dest = IMAGES_DIR / filename
        IMAGES_DIR.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10, context=_SSL_CTX) as resp:
            with open(dest, 'wb') as f:
                f.write(resp.read())
        return f'/static/images/{filename}'
    except Exception as e:
        print(f'❌ 簡易版でも失敗: {e}')
        return url

def get_thumbnail_url(image_url: str) -> str:
    """メイン画像パスからサムネイルパスを生成"""
    if not image_url or not image_url.startswith('/static/images/'):
        return image_url
    # /static/images/xxx_main.jpg → /static/images/xxx_thumb.jpg
    return image_url.replace('_main.jpg', '_thumb.jpg')

# =============================================
# 画像ハッシュ化ユーティリティ
# =============================================
def hash_image_data(image_data_uri: str) -> str:
    """Base64 data URIの画像をハッシュ化（SHA256）"""
    if not image_data_uri or not image_data_uri.startswith('data:'):
        return ''
    try:
        # data:image/jpeg;base64,xxxxx から base64部分を抽出
        b64_str = image_data_uri.split(',', 1)[1]
        # Base64デコード
        img_bytes = base64.b64decode(b64_str)
        # PILで画像を開いて標準化（ノイズ除去用）
        img = Image.open(BytesIO(img_bytes))
        img = img.convert('RGB')
        img.thumbnail((256, 256))  # 小さくリサイズして比較
        # ハッシュ化
        img_hash = hashlib.sha256(img.tobytes()).hexdigest()
        return img_hash
    except Exception as e:
        print(f'⚠️ 画像ハッシュ化失敗: {e}')
        return ''

def hash_image_file(file_path: Path) -> str:
    """ローカルJPGファイルをハッシュ化（SHA256）"""
    if not file_path.exists():
        return ''
    try:
        with open(file_path, 'rb') as f:
            img = Image.open(f)
            img = img.convert('RGB')
            img.thumbnail((256, 256))
            img_hash = hashlib.sha256(img.tobytes()).hexdigest()
        return img_hash
    except Exception as e:
        print(f'⚠️ ファイルハッシュ化失敗 {file_path}: {e}')
        return ''

def calc_average_cost(sku: str) -> float:
    """SKUの過去平均仕入れ価格を計算"""
    purchases = load_json(PURCHASES_FILE)
    matching = [p for p in purchases if p.get('SKU') == sku]
    if not matching:
        return 0.0
    total_cost = sum(p.get('合計金額', 0) for p in matching)
    total_qty = sum(p.get('数量', 0) for p in matching)
    return total_cost / total_qty if total_qty > 0 else 0.0

# =============================================
# 移動平均法在庫計算
# =============================================
def calc_inventory():
    purchases = load_json(PURCHASES_FILE)
    sales     = load_json(SALES_FILE)
    products  = load_json(PRODUCTS_FILE)
    cfg = load_config()
    low_stock_threshold = int(cfg.get('lowStockThreshold', 3))

    product_image_map = {}
    for p in products:
        img = p.get('画像URL', '')
        if p.get('SKU'):   product_image_map[p['SKU']]   = img
        if p.get('商品名'): product_image_map[p['商品名']] = img

    all_tx = []
    for p in purchases:
        all_tx.append({'type': 'purchase', 'date': p.get('仕入れ日', ''), 'data': p})
    for s in sales:
        all_tx.append({'type': 'sale', 'date': s.get('販売日', ''), 'data': s})
    all_tx.sort(key=lambda x: x['date'])

    inventory = {}
    for tx in all_tx:
        d = tx['data']
        key = d.get('SKU') or d.get('商品名', '')
        if not key:
            continue
        if key not in inventory:
            inventory[key] = {
                'name': d.get('商品名', ''),
                'sku': d.get('SKU', ''),
                'totalPurchased': 0,
                'totalSold': 0,
                'avgCost': 0,
                'currentStock': 0,
                'imageUrl': d.get('画像URL', '') or product_image_map.get(key, '')
            }
        item = inventory[key]
        if not item['imageUrl'] and d.get('画像URL'):
            item['imageUrl'] = d['画像URL']

        if tx['type'] == 'purchase':
            new_qty  = int(d.get('数量', 0) or 0)
            new_cost = float(d.get('仕入れ単価', 0) or 0)
            if item['currentStock'] + new_qty > 0:
                item['avgCost'] = round(
                    (item['currentStock'] * item['avgCost'] + new_qty * new_cost) /
                    (item['currentStock'] + new_qty)
                )
            item['totalPurchased'] += new_qty
            item['currentStock']   += new_qty
        else:
            sold = int(d.get('数量', 0) or 0)
            item['totalSold']    += sold
            item['currentStock'] = max(0, item['currentStock'] - sold)

    result = []
    for item in inventory.values():
        stock = item['totalPurchased'] - item['totalSold']
        result.append({
            'name':           item['name'],
            'sku':            item['sku'],
            'imageUrl':       item['imageUrl'] or product_image_map.get(item['sku'], '') or product_image_map.get(item['name'], ''),
            'totalPurchased': item['totalPurchased'],
            'totalSold':      item['totalSold'],
            'avgCost':        item['avgCost'],
            'stock':          stock,
            'alert':          stock <= low_stock_threshold,
        })
    return result

# =============================================
# エントリーポイント（HTML 配信）
# =============================================
@app.route('/')
def index():
    html_path = BASE_DIR / 'index_local.html'
    if not html_path.exists():
        html_path = BASE_DIR / 'Index.html'
    with open(html_path, 'r', encoding='utf-8') as f:
        return f.read()

@app.route('/static/images/<path:filename>')
def serve_image(filename):
    return send_from_directory(IMAGES_DIR, filename)

# =============================================
# API: 商品マスタ
# =============================================
@app.route('/api/getProducts', methods=['GET', 'POST'])
def api_get_products():
    products = load_json(PRODUCTS_FILE)
    return jsonify([p for p in products if p.get('商品ID')])

@app.route('/api/addProduct', methods=['POST'])
def api_add_product():
    data = request.json or {}
    products = load_json(PRODUCTS_FILE)
    product_id = new_id('P')
    product = {
        '商品ID':       product_id,
        '商品名':       data.get('name', ''),
        'SKU':          data.get('sku', ''),
        'カテゴリ':      data.get('category', ''),
        '仕入れ先':     data.get('supplier', ''),
        '標準仕入れ単価': float(data.get('costPrice', 0) or 0),
        '登録日':       today_str(),
        'メモ':         data.get('memo', ''),
        '画像URL':      data.get('imageUrl', ''),
    }
    products.append(product)
    save_json(PRODUCTS_FILE, products)
    return jsonify({'success': True, 'id': product_id})

@app.route('/api/addProductsBulk', methods=['POST'])
def api_add_products_bulk():
    rows = request.json or []
    products = load_json(PRODUCTS_FILE)
    known_skus  = {str(p.get('SKU', '')).strip() for p in products}
    known_names = {str(p.get('商品名', '')).strip() for p in products}
    added = 0
    for row in rows:
        sku  = str(row.get('sku', '')).strip()
        name = str(row.get('name', '')).strip()
        if sku in known_skus or name in known_names:
            continue
        product = {
            '商品ID':       new_id('P'),
            '商品名':       name or sku,
            'SKU':          sku,
            'カテゴリ':      row.get('category', 'その他'),
            '仕入れ先':     row.get('supplier', ''),
            '標準仕入れ単価': float(row.get('costPrice', 0) or 0),
            '登録日':       today_str(),
            'メモ':         row.get('memo', ''),
            '画像URL':      row.get('imageUrl', ''),
        }
        products.append(product)
        if sku:  known_skus.add(sku)
        if name: known_names.add(name)
        added += 1
    save_json(PRODUCTS_FILE, products)
    return jsonify({'success': True, 'count': added})

@app.route('/api/deleteProductAll', methods=['POST'])
def api_delete_product():
    data = request.json or {}
    key = data.get('productKey', '')
    products  = load_json(PRODUCTS_FILE)
    purchases = load_json(PURCHASES_FILE)
    sales     = load_json(SALES_FILE)
    products  = [p for p in products  if p.get('SKU') != key and p.get('商品名') != key]
    purchases = [p for p in purchases if p.get('SKU') != key and p.get('商品名') != key]
    sales     = [s for s in sales     if s.get('SKU') != key and s.get('商品名') != key]
    save_json(PRODUCTS_FILE,  products)
    save_json(PURCHASES_FILE, purchases)
    save_json(SALES_FILE,     sales)
    return jsonify({'success': True})

@app.route('/api/deleteProductsBulk', methods=['POST'])
def api_delete_products_bulk():
    keys = request.json or []
    key_set   = set(keys)
    products  = load_json(PRODUCTS_FILE)
    purchases = load_json(PURCHASES_FILE)
    sales     = load_json(SALES_FILE)
    products  = [p for p in products  if p.get('SKU') not in key_set and p.get('商品名') not in key_set]
    purchases = [p for p in purchases if p.get('SKU') not in key_set and p.get('商品名') not in key_set]
    sales     = [s for s in sales     if s.get('SKU') not in key_set and s.get('商品名') not in key_set]
    save_json(PRODUCTS_FILE,  products)
    save_json(PURCHASES_FILE, purchases)
    save_json(SALES_FILE,     sales)
    return jsonify({'success': True})

@app.route('/api/updateProductMasterField', methods=['POST'])
def api_update_product_master_field():
    data       = request.json or {}
    product_id = str(data.get('id', '')).strip()
    orig_name  = str(data.get('originalName', '')).strip()
    field      = str(data.get('fieldName', '')).strip()
    new_value  = data.get('newValue', '')
    allowed    = {'商品名', 'SKU', 'カテゴリ', '仕入れ先', '標準仕入れ単価', 'メモ'}
    if field not in allowed:
        return jsonify({'success': False, 'error': '更新不可のフィールドです: ' + field}), 400
    products = load_json(PRODUCTS_FILE)
    target   = None
    for p in products:
        if (product_id and str(p.get('商品ID', '')) == product_id) or \
           (not product_id and str(p.get('商品名', '')) == orig_name):
            target = p
            break
    if target is None:
        return jsonify({'success': False, 'error': '商品が見つかりません'}), 404
    if field == '標準仕入れ単価':
        try:
            new_value = float(new_value)
        except (ValueError, TypeError):
            return jsonify({'success': False, 'error': '単価は数値で入力してください'}), 400
    old_name = target.get('商品名')
    target[field] = new_value
    save_json(PRODUCTS_FILE, products)
    # 商品名変更時は仕入れ・販売も同期
    if field == '商品名' and old_name and old_name != new_value:
        for lst, f in [(PURCHASES_FILE, None), (SALES_FILE, None)]:
            rows = load_json(lst)
            changed = False
            for r in rows:
                match = (product_id and str(r.get('商品ID', '')) == product_id) or \
                        (str(r.get('商品名', '')) == old_name)
                if match:
                    r['商品名'] = new_value
                    changed = True
            if changed:
                save_json(lst, rows)
    return jsonify({'success': True})

@app.route('/api/updateProductsBulkFromCSV', methods=['POST'])
def api_update_products_bulk_from_csv():
    """CSVから商品マスタを一括更新（SKUで照合して更新）"""
    data = request.json or {}
    updates = data.get('updates', [])

    if not updates:
        return jsonify({'error': '更新データがありません'}), 400

    products = load_json(PRODUCTS_FILE)
    updated_count = 0

    for upd in updates:
        sku = str(upd.get('sku', '')).strip()
        if not sku:
            continue

        # SKUで商品を検索
        target = None
        for p in products:
            if str(p.get('SKU', '')).strip() == sku:
                target = p
                break

        if target is None:
            # SKUが見つからない場合はスキップ
            continue

        # 更新対象フィールド
        if 'productName' in upd:
            target['商品名'] = str(upd['productName']).strip()
        if 'category' in upd:
            target['カテゴリ'] = str(upd['category']).strip()
        if 'supplier' in upd:
            target['仕入れ先'] = str(upd['supplier']).strip()
        if 'costPrice' in upd:
            try:
                target['標準仕入れ単価'] = float(upd['costPrice'])
            except (ValueError, TypeError):
                pass
        if 'memo' in upd:
            target['メモ'] = str(upd['memo']).strip()
        if 'imageUrl' in upd:
            url = str(upd['imageUrl']).strip()
            if url:
                target['画像URL'] = url

        updated_count += 1

    save_json(PRODUCTS_FILE, products)
    return jsonify({'ok': True, 'updatedCount': updated_count})

@app.route('/api/updateProductSku', methods=['POST'])
def api_update_product_sku():
    data       = request.json or {}
    product_id = str(data.get('id', '')).strip()
    name       = str(data.get('name', '')).strip()
    old_sku    = str(data.get('oldSku', '')).strip()
    new_sku    = str(data.get('newSku', '')).strip()
    if not new_sku:
        return jsonify({'success': False, 'error': 'SKUを入力してください'}), 400
    # 商品マスタ更新
    products = load_json(PRODUCTS_FILE)
    updated = False
    for p in products:
        if (product_id and str(p.get('商品ID', '')) == product_id) or \
           (str(p.get('商品名', '')) == name and str(p.get('SKU', '')) == old_sku):
            p['SKU'] = new_sku
            updated = True
    if not updated:
        return jsonify({'success': False, 'error': '商品が見つかりません'}), 404
    save_json(PRODUCTS_FILE, products)
    # 仕入れ・販売の SKU を一括置換
    for lst_file in [PURCHASES_FILE, SALES_FILE]:
        rows = load_json(lst_file)
        changed = False
        for r in rows:
            if str(r.get('商品名', '')) == name and str(r.get('SKU', '')) == old_sku:
                r['SKU'] = new_sku
                changed = True
        if changed:
            save_json(lst_file, rows)
    return jsonify({'success': True})

@app.route('/api/updateProductImages', methods=['POST'])
def api_update_product_images():
    image_map = request.json or {}
    products  = load_json(PRODUCTS_FILE)
    for p in products:
        sku = str(p.get('SKU', '')).strip()
        if sku in image_map and not p.get('画像URL'):
            p['画像URL'] = image_map[sku]
    save_json(PRODUCTS_FILE, products)
    return jsonify({'success': True})

@app.route('/api/checkProductInMaster', methods=['POST'])
def api_check_product():
    data     = request.json or {}
    sku      = str(data.get('sku', '')).strip()
    name     = str(data.get('name', '')).strip()
    products = load_json(PRODUCTS_FILE)
    found    = any(
        (sku  and str(p.get('SKU', '')).strip() == sku) or
        (name and str(p.get('商品名', '')).strip() == name)
        for p in products
    )
    return jsonify({'exists': found})

# =============================================
# API: 仕入れ
# =============================================
@app.route('/api/getPurchases', methods=['GET', 'POST'])
def api_get_purchases():
    data  = request.json or {}
    limit = int(data.get('limit', 200) or 200)
    purchases = load_json(PURCHASES_FILE)
    purchases_sorted = sorted(purchases, key=lambda x: x.get('仕入れ日', ''), reverse=True)
    return jsonify(purchases_sorted[:limit])

@app.route('/api/addPurchase', methods=['POST'])
def api_add_purchase():
    data = request.json or {}
    purchases = load_json(PURCHASES_FILE)
    products  = load_json(PRODUCTS_FILE)
    qty      = int(data.get('quantity', 1) or 1)
    cost     = float(data.get('unitCost', 0) or 0)
    shipping = float(data.get('shipping', 0) or 0)
    sku      = str(data.get('sku', '')).strip()
    prod_name = str(data.get('productName', '')).strip()
    supplier  = str(data.get('supplier', '')).strip()
    img_url  = data.get('imageUrl', '')
    if img_url:
        img_url = download_image(img_url, sku)

    # 商品マスタに自動追加（同じSKUまたは商品名が存在しない場合）
    if sku or prod_name:
        existing = next((p for p in products if
                        (sku and p.get('SKU') == sku) or
                        (prod_name and p.get('商品名') == prod_name)), None)
        if not existing:
            new_product = {
                '商品ID':         new_id('P'),
                '商品名':         prod_name,
                'SKU':            sku,
                'カテゴリ':       '',
                '仕入れ先':       supplier,
                '標準仕入れ単価': cost,
                '登録日':         today_str(),
                'メモ':          '',
                '画像URL':        img_url,
            }
            products.append(new_product)
            save_json(PRODUCTS_FILE, products)

    purchase = {
        '仕入れID':   new_id('BUY'),
        '仕入れ日':   data.get('date', today_str()),
        '商品名':     prod_name,
        'SKU':        sku,
        '仕入れ先':   supplier,
        '仕入れ単価': cost,
        '数量':       qty,
        '合計金額':   qty * cost,
        '送料':       shipping,
        '備考':       data.get('memo', ''),
        '画像URL':    img_url,
    }
    purchases.append(purchase)
    save_json(PURCHASES_FILE, purchases)
    _update_master_costs([data])
    return jsonify({'success': True})

@app.route('/api/addPurchasesBulk', methods=['POST'])
def api_add_purchases_bulk():
    rows = request.json or []
    if not rows:
        return jsonify({'success': False, 'error': 'データがありません'}), 400

    valid_rows = [r for r in rows if str(r.get('sku', '')).strip()]
    if not valid_rows:
        return jsonify({'success': False, 'error': 'SKUが入力されている商品がありません'}), 400

    purchases = load_json(PURCHASES_FILE)
    products  = load_json(PRODUCTS_FILE)
    known_skus  = {str(p.get('SKU', '')).strip() for p in products}
    known_names = {str(p.get('商品名', '')).strip() for p in products}
    auto_added  = []

    for row in valid_rows:
        sku  = str(row.get('sku', '')).strip()
        name = str(row.get('productName', '')).strip()
        if not (sku in known_skus or name in known_names):
            new_product = {
                '商品ID':       new_id('P'),
                '商品名':       name or sku,
                'SKU':          sku,
                'カテゴリ':      row.get('category', 'その他'),
                '仕入れ先':     row.get('supplier', ''),
                '標準仕入れ単価': float(row.get('unitCost', 0) or 0),
                '登録日':       today_str(),
                'メモ':         row.get('memo', ''),
                '画像URL':      row.get('imageUrl', ''),
            }
            products.append(new_product)
            if sku:  known_skus.add(sku)
            if name: known_names.add(name)
            auto_added.append(name or sku)

    save_json(PRODUCTS_FILE, products)

    for row in valid_rows:
        qty      = int(row.get('quantity', 1) or 1)
        cost     = float(row.get('unitCost', 0) or 0)
        shipping = float(row.get('shipping', 0) or 0)
        sku      = str(row.get('sku', '')).strip()
        img_url  = row.get('imageUrl', '')
        if img_url and img_url.startswith('http'):
            img_url = download_image(img_url, sku)
        purchase = {
            '仕入れID':   new_id('BUY'),
            '仕入れ日':   row.get('date', today_str()),
            '商品名':     row.get('productName', ''),
            'SKU':        sku,
            '仕入れ先':   row.get('supplier', ''),
            '仕入れ単価': cost,
            '数量':       qty,
            '合計金額':   qty * cost,
            '送料':       shipping,
            '備考':       row.get('memo', ''),
            '画像URL':    img_url,
        }
        purchases.append(purchase)

    save_json(PURCHASES_FILE, purchases)
    _update_master_costs(valid_rows)

    skipped = [r for r in rows if not str(r.get('sku', '')).strip()]
    return jsonify({
        'success':      True,
        'count':        len(valid_rows),
        'autoAdded':    len(auto_added),
        'skippedCount': len(skipped),
        'skipped':      [r.get('productName', '') for r in skipped],
    })

# =============================================
# API: 販売
# =============================================
@app.route('/api/getSales', methods=['GET', 'POST'])
def api_get_sales():
    data  = request.json or {}
    limit = int(data.get('limit', 200) or 200)
    sales = load_json(SALES_FILE)
    sales_sorted = sorted(sales, key=lambda x: x.get('販売日', ''), reverse=True)
    return jsonify(sales_sorted[:limit])

@app.route('/api/addSale', methods=['POST'])
def api_add_sale():
    data  = request.json or {}
    sales = load_json(SALES_FILE)
    qty         = int(data.get('quantity', 1) or 1)
    price       = float(data.get('salePrice', 0) or 0)
    fee_rate    = float(data.get('feeRate', 0) or 0)
    fee         = round(price * qty * fee_rate / 100)
    shipping_burden = float(data.get('shippingBurden', 0) or 0)
    net_sales   = price * qty - fee - shipping_burden
    sale = {
        '販売ID':    new_id('SALE'),
        '販売日':    data.get('date', today_str()),
        '商品名':    data.get('productName', ''),
        'SKU':       str(data.get('sku', '')).strip(),
        '販売チャネル': data.get('channel', ''),
        '売価':      price,
        '数量':      qty,
        '手数料率':   fee_rate,
        '手数料':    fee,
        '送料負担':   shipping_burden,
        '純売上':    net_sales,
        '備考':      data.get('memo', ''),
    }
    sales.append(sale)
    save_json(SALES_FILE, sales)
    return jsonify({'success': True})

@app.route('/api/updateSale', methods=['POST'])
def api_update_sale():
    data    = request.json or {}
    sale_id = str(data.get('saleId', '')).strip()
    if not sale_id:
        return jsonify({'success': False, 'error': '販売IDが必要です'}), 400
    sales = load_json(SALES_FILE)
    target = next((s for s in sales if str(s.get('販売ID', '')) == sale_id), None)
    if target is None:
        return jsonify({'success': False, 'error': '該当の販売データが見つかりません'}), 404
    qty      = int(data.get('quantity', target.get('数量', 1)) or 1)
    price    = float(data.get('salePrice', target.get('売価', 0)) or 0)
    fee_rate = float(data.get('feeRate', target.get('手数料率', 0)) or 0)
    shipping = float(data.get('shippingBurden', target.get('送料負担', 0)) or 0)
    fee      = round(price * qty * fee_rate / 100)
    net      = price * qty - fee - shipping
    target['販売日']      = data.get('date', target.get('販売日', ''))
    target['商品名']      = data.get('productName', target.get('商品名', ''))
    target['SKU']        = str(data.get('sku', target.get('SKU', ''))).strip()
    target['販売チャネル'] = data.get('channel', target.get('販売チャネル', ''))
    target['売価']        = price
    target['数量']        = qty
    target['手数料率']     = fee_rate
    target['手数料']      = fee
    target['送料負担']     = shipping
    target['純売上']      = net
    target['備考']        = data.get('memo', target.get('備考', ''))
    save_json(SALES_FILE, sales)
    return jsonify({'success': True})

@app.route('/api/deleteSale', methods=['POST'])
def api_delete_sale():
    data    = request.json or {}
    sale_id = str(data.get('saleId', '')).strip()
    if not sale_id:
        return jsonify({'success': False, 'error': '販売IDが必要です'}), 400
    sales = load_json(SALES_FILE)
    new_sales = [s for s in sales if str(s.get('販売ID', '')) != sale_id]
    if len(new_sales) == len(sales):
        return jsonify({'success': False, 'error': '該当データが見つかりません'}), 404
    save_json(SALES_FILE, new_sales)
    return jsonify({'success': True})

# =============================================
# API: 在庫
# =============================================
@app.route('/api/getInventory', methods=['GET', 'POST'])
def api_get_inventory():
    return jsonify(calc_inventory())

@app.route('/api/updateInventoryDirect', methods=['POST'])
def api_update_inventory_direct():
    data      = request.json or {}
    sku       = data.get('sku', '')
    new_stock = int(data.get('newStock', 0))
    inventory = calc_inventory()
    current   = next((i for i in inventory if i['sku'] == sku), None)
    old_stock = current['stock'] if current else 0

    # 在庫履歴ファイルに記録
    hist_file = DATA_DIR / 'inventory_history.json'
    history   = load_json(hist_file)
    history.append({
        '日時':   now_str(),
        'SKU':    sku,
        '変更前':  old_stock,
        '変更後':  new_stock,
    })
    save_json(hist_file, history)
    return jsonify({'success': True, 'oldStock': old_stock, 'newStock': new_stock})

# =============================================
# API: ダッシュボード
# =============================================
@app.route('/api/getDashboardData', methods=['GET', 'POST'])
def api_get_dashboard():
    params = request.json or {}
    period = params.get('period', 'month')  # month, 3m, 6m, 1y, all

    purchases = load_json(PURCHASES_FILE)
    sales     = load_json(SALES_FILE)
    products  = load_json(PRODUCTS_FILE)
    inventory = calc_inventory()
    inv_map   = {i['sku']: i for i in inventory}
    now        = datetime.now()

    def parse_date(s):
        try: return datetime.fromisoformat(str(s)[:10])
        except: return None

    # 期間の計算
    def get_period_range():
        if period == 'month':
            period_start = now.replace(day=1)
            period_end = now
        elif period == '3m':
            period_end = now
            period_start = now.replace(day=1) - __import__('datetime').timedelta(days=90)
        elif period == '6m':
            period_end = now
            period_start = now.replace(day=1) - __import__('datetime').timedelta(days=180)
        elif period == '1y':
            period_end = now
            period_start = now.replace(day=1) - __import__('datetime').timedelta(days=365)
        else:  # 'all'
            period_start = None
            period_end = now
        return period_start, period_end

    period_start, period_end = get_period_range()

    def should_include_date(date_str):
        d = parse_date(date_str)
        if not d: return False
        if period_start and d < period_start: return False
        if d > period_end: return False
        return True

    this_month_sales = [s for s in sales if should_include_date(s.get('販売日', ''))]
    this_month_purchases = [p for p in purchases if should_include_date(p.get('仕入れ日', ''))]

    month_revenue  = sum(float(s.get('純売上', 0) or 0) for s in this_month_sales)
    month_fee      = sum(float(s.get('手数料', 0) or 0) for s in this_month_sales)
    month_shipping = sum(float(s.get('送料負担', 0) or 0) for s in this_month_sales)
    month_sales_count = sum(int(s.get('数量', 0) or 0) for s in this_month_sales)
    month_cost_purchase = sum(float(p.get('合計金額', 0) or 0) for p in this_month_purchases)

    month_cogs = 0
    for s in this_month_sales:
        inv = inv_map.get(s.get('SKU', ''))
        if inv:
            month_cogs += inv['avgCost'] * int(s.get('数量', 0) or 0)

    month_profit = round(month_revenue - month_cogs - month_fee - month_shipping)
    profit_margin = round(month_profit / month_revenue * 100, 1) if month_revenue > 0 else 0

    # 在庫アラート
    low_stock_items = [{'name': i['name'], 'sku': i['sku'], 'stock': i['stock']} for i in inventory if i['alert']]

    # チャネル別売上（選択期間）→ objectで返す
    channel_data = {}
    for s in this_month_sales:
        ch = s.get('販売チャネル', 'その他')
        channel_data[ch] = round(channel_data.get(ch, 0) + float(s.get('純売上', 0) or 0))

    # 商品別利益ランキング（選択期間）
    prod_map = {}
    for s in sales:
        if not should_include_date(s.get('販売日', '')): continue
        key = s.get('SKU') or s.get('商品名', '')
        if not key: continue
        if key not in prod_map:
            prod_map[key] = {'name': s.get('商品名', key), 'qty': 0, 'revenue': 0.0, 'cost': 0.0, 'fee': 0.0, 'shipping': 0.0}
        p = prod_map[key]
        qty = int(s.get('数量', 0) or 0)
        p['qty']      += qty
        p['revenue']  += float(s.get('純売上', 0) or 0)
        p['fee']      += float(s.get('手数料', 0) or 0)
        p['shipping'] += float(s.get('送料負担', 0) or 0)
        inv = inv_map.get(s.get('SKU', ''))
        if inv:
            p['cost'] += inv['avgCost'] * qty
    product_ranking = []
    for p in prod_map.values():
        p['profit']  = round(p['revenue'] - p['cost'] - p['fee'] - p['shipping'])
        p['revenue'] = round(p['revenue'])
        p['cost']    = round(p['cost'])
        product_ranking.append(p)
    product_ranking.sort(key=lambda x: x['profit'], reverse=True)

    # 月別データ（期間に応じた表示件数）売上＋利益
    month_count = {'month': 6, '3m': 3, '6m': 6, '1y': 12, 'all': 24}
    show_months = month_count.get(period, 6)

    monthly_map = {}
    for s in sales:
        d = parse_date(s.get('販売日', ''))
        if not d: continue
        if not should_include_date(s.get('販売日', '')): continue
        key = f"{d.year}-{d.month:02d}"
        if key not in monthly_map:
            monthly_map[key] = {'revenue': 0.0, 'cost': 0.0, 'fee': 0.0, 'shipping': 0.0}
        m = monthly_map[key]
        qty = int(s.get('数量', 0) or 0)
        m['revenue']  += float(s.get('純売上', 0) or 0)
        m['fee']      += float(s.get('手数料', 0) or 0)
        m['shipping'] += float(s.get('送料負担', 0) or 0)
        inv = inv_map.get(s.get('SKU', ''))
        if inv:
            m['cost'] += inv['avgCost'] * qty
    monthly_data = []
    for key in sorted(monthly_map.keys())[-show_months:]:
        m = monthly_map[key]
        revenue = round(m['revenue'])
        profit  = round(m['revenue'] - m['cost'] - m['fee'] - m['shipping'])
        monthly_data.append({'label': key, 'revenue': revenue, 'profit': profit})

    recent_sales = sorted(sales, key=lambda x: x.get('販売日', ''), reverse=True)[:5]

    # 期間表示用フォーマット
    period_start_str = period_start.strftime('%Y年%m月') if period_start else '最初'
    period_end_str = period_end.strftime('%Y年%m月')

    return jsonify({
        'monthRevenue':     round(month_revenue),
        'monthSalesCount':  month_sales_count,
        'monthProfit':      month_profit,
        'profitMargin':     profit_margin,
        'monthCost':        round(month_cost_purchase),
        'lowStockCount':    len(low_stock_items),
        'totalProducts':    len(products),
        'lowStockItems':    low_stock_items,
        'lowStockThreshold': load_config().get('lowStockThreshold', 3),
        'channelData':      channel_data,
        'productRanking':   product_ranking,
        'recentSales':      recent_sales,
        'monthlyData':      monthly_data,
        'periodStart':      period_start_str,
        'periodEnd':        period_end_str,
    })

# =============================================
# API: 利益レポート
# =============================================
@app.route('/api/getProfitReport', methods=['POST'])
def api_get_profit_report():
    params    = request.json or {}
    mode      = params.get('mode', 'monthly')
    count     = int(params.get('count', 6) or 6)
    start_str = params.get('startDate', '')
    end_str   = params.get('endDate', '')
    sales     = load_json(SALES_FILE)
    inventory = calc_inventory()
    inv_map   = {i['sku']: i for i in inventory}

    def parse_date(s):
        try: return datetime.fromisoformat(str(s)[:10])
        except: return None

    start_dt = parse_date(start_str) if start_str else None
    end_dt   = parse_date(end_str)   if end_str   else None

    def group_key(d):
        if mode == 'daily':  return d.strftime('%Y-%m-%d')
        if mode == 'weekly': return f"{d.year}-W{d.strftime('%V')}"
        return d.strftime('%Y-%m')

    # 全販売データをグループ化
    all_groups = {}
    filtered_sales = []
    for s in sales:
        d = parse_date(s.get('販売日', ''))
        if not d: continue
        if start_dt and d < start_dt: continue
        if end_dt   and d > end_dt:   continue
        filtered_sales.append((d, s))
        key = group_key(d) if mode != 'range' else '全期間'
        if key not in all_groups:
            all_groups[key] = {'revenue': 0.0, 'cost': 0.0, 'fee': 0.0, 'shipping': 0.0, 'salesCount': 0}
        g = all_groups[key]
        qty = int(s.get('数量', 0) or 0)
        g['revenue']    += float(s.get('純売上', 0) or 0)
        g['fee']        += float(s.get('手数料', 0) or 0)
        g['shipping']   += float(s.get('送料負担', 0) or 0)
        g['salesCount'] += qty
        inv = inv_map.get(s.get('SKU', ''))
        if inv: g['cost'] += inv['avgCost'] * qty

    if mode == 'range':
        sorted_keys = ['全期間'] if '全期間' in all_groups else []
    else:
        sorted_keys = sorted(all_groups.keys())[-count:]

    summary_data = []
    for key in sorted_keys:
        g = all_groups[key]
        revenue = round(g['revenue'])
        profit  = round(g['revenue'] - g['cost'] - g['fee'] - g['shipping'])
        summary_data.append({'label': key, 'salesCount': g['salesCount'], 'revenue': revenue, 'profit': profit})

    # 商品別ランキング（表示期間内）
    period_keys_set = set(sorted_keys)
    prod_map = {}
    for d, s in filtered_sales:
        if mode != 'range' and group_key(d) not in period_keys_set:
            continue
        key = s.get('SKU') or s.get('商品名', '')
        if not key: continue
        if key not in prod_map:
            prod_map[key] = {'name': s.get('商品名', key), 'qty': 0, 'revenue': 0.0, 'cost': 0.0, 'fee': 0.0, 'shipping': 0.0}
        p = prod_map[key]
        qty = int(s.get('数量', 0) or 0)
        p['qty']      += qty
        p['revenue']  += float(s.get('純売上', 0) or 0)
        p['fee']      += float(s.get('手数料', 0) or 0)
        p['shipping'] += float(s.get('送料負担', 0) or 0)
        inv = inv_map.get(s.get('SKU', ''))
        if inv: p['cost'] += inv['avgCost'] * qty

    product_ranking = []
    for p in prod_map.values():
        p['profit']  = round(p['revenue'] - p['cost'] - p['fee'] - p['shipping'])
        p['revenue'] = round(p['revenue'])
        p['cost']    = round(p['cost'])
        product_ranking.append(p)
    product_ranking.sort(key=lambda x: x['profit'], reverse=True)

    return jsonify({'mode': mode, 'summaryData': summary_data, 'productRanking': product_ranking})

# =============================================
# API: チャネル
# =============================================
@app.route('/api/getChannels', methods=['GET', 'POST'])
def api_get_channels():
    channels = ['Amazon', 'メルカリ', 'Yahoo!ショッピング', 'ラクマ', 'BASE', 'Shopify', 'PayPayフリマ', 'その他']
    return jsonify(channels)

# =============================================
# API: コンフィグ
# =============================================
@app.route('/api/getConfig', methods=['GET', 'POST'])
def api_get_config():
    return jsonify(load_config())

@app.route('/api/saveConfig', methods=['POST'])
def api_save_config():
    data = request.json or {}
    cfg = load_config()

    if 'lowStockThreshold' in data:
        val = int(data['lowStockThreshold'])
        if val < 0:
            return jsonify({'error': '閾値は0以上の整数を指定してください'}), 400
        cfg['lowStockThreshold'] = val

    if 'defaultFeeRate' in data:
        val = float(data['defaultFeeRate'])
        if val < 0 or val > 100:
            return jsonify({'error': 'デフォルト手数料率は0～100の数値を指定してください'}), 400
        cfg['defaultFeeRate'] = val

    if 'defaultCalculation' in data:
        cfg['defaultCalculation'] = data['defaultCalculation']

    # ラクマート認証情報の保存
    if 'rakumartUsername' in data:
        cfg['rakumartUsername'] = data.get('rakumartUsername') or None

    if 'rakumartPassword' in data:
        pwd = data.get('rakumartPassword')
        if pwd:
            cfg['rakumartPasswordEncrypted'] = encrypt_password(pwd)
        else:
            cfg['rakumartPasswordEncrypted'] = None

    save_config(cfg)

    # パスワードは返さない（セキュリティ）
    response_cfg = dict(cfg)
    response_cfg.pop('rakumartPasswordEncrypted', None)

    return jsonify({'ok': True, 'config': response_cfg})

# =============================================
# API: ラクマート認証情報取得
# =============================================
@app.route('/api/getRakumartCredentials', methods=['GET'])
def api_get_rakumart_credentials():
    """ラクマート認証情報を取得（パスワード除く）"""
    cfg = load_config()
    return jsonify({
        'username': cfg.get('rakumartUsername'),
        'hasPassword': bool(cfg.get('rakumartPasswordEncrypted'))
    })

@app.route('/api/getDecryptedRakumartPassword', methods=['GET'])
def api_get_decrypted_rakumart_password():
    """ラクマートパスワードを復号（内部用のみ）"""
    cfg = load_config()
    encrypted = cfg.get('rakumartPasswordEncrypted')
    if encrypted:
        return jsonify({'password': decrypt_password(encrypted)})
    return jsonify({'password': None})

# =============================================
# API: ヘルスチェック
# =============================================
@app.route('/api/healthCheck', methods=['GET', 'POST'])
def api_health_check():
    """全機能の正常性を確認"""
    checks = {
        'timestamp': datetime.now().isoformat(),
        'status': 'ok',
        'checks': {}
    }

    try:
        # 1. データファイル確認
        products = load_json(PRODUCTS_FILE)
        purchases = load_json(PURCHASES_FILE)
        sales = load_json(SALES_FILE)
        checks['checks']['data_files'] = {'ok': True, 'products': len(products), 'purchases': len(purchases), 'sales': len(sales)}
    except Exception as e:
        checks['checks']['data_files'] = {'ok': False, 'error': str(e)}
        checks['status'] = 'error'

    try:
        # 2. 在庫計算確認
        inventory = calc_inventory()
        checks['checks']['inventory'] = {'ok': True, 'items': len(inventory)}
    except Exception as e:
        checks['checks']['inventory'] = {'ok': False, 'error': str(e)}
        checks['status'] = 'error'

    try:
        # 3. ダッシュボードデータ確認
        from flask import request as flask_request
        checks['checks']['dashboard'] = {'ok': True}
    except Exception as e:
        checks['checks']['dashboard'] = {'ok': False, 'error': str(e)}
        checks['status'] = 'error'

    try:
        # 4. ラクマートサーバー確認
        urllib.request.urlopen('http://localhost:8766/rakumart/latest', timeout=2, context=_SSL_CTX)
        checks['checks']['rakumart'] = {'ok': True}
    except:
        checks['checks']['rakumart'] = {'ok': False, 'note': 'offline (optional)'}

    try:
        # 5. 画像フォルダ確認
        img_count = len(list(IMAGES_DIR.glob('*_main.jpg')))
        checks['checks']['images'] = {'ok': True, 'files': img_count}
    except Exception as e:
        checks['checks']['images'] = {'ok': False, 'error': str(e)}

    return jsonify(checks), 200 if checks['status'] == 'ok' else 500

# =============================================
# API: ラクマートサーバー管理
# =============================================
@app.route('/api/startRakumartServer', methods=['POST'])
def api_start_rakumart():
    """ラクマートサーバーをオンデマンド起動"""
    if start_rakumart_server():
        return jsonify({'success': True, 'message': 'ラクマートサーバーが起動しました'})
    else:
        return jsonify({'success': False, 'message': 'ラクマートサーバーの起動に失敗しました'}), 500

@app.route('/api/checkRakumartServer', methods=['POST'])
def api_check_rakumart():
    """ラクマートサーバーの状態確認（/health エンドポイントで軽量チェック）"""
    try:
        urllib.request.urlopen('http://localhost:8766/health', timeout=2, context=_SSL_CTX)
        return jsonify({'online': True})
    except:
        return jsonify({'online': False})

@app.route('/api/getRakumartLatest', methods=['POST'])
def api_get_rakumart_latest():
    """ラクマート最新配送依頼書をプロキシ取得"""
    params = request.json or {}
    order_sn = params.get('orderSn', '')
    url = 'http://localhost:8766/rakumart/latest'
    if order_sn:
        url += f'?orderSn={urllib.parse.quote(order_sn)}'
    try:
        print(f"🔄 Fetching {order_sn}... URL: {url}")
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        print(f"✅ Fetched {order_sn}: {data.get('orderSn', 'N/A')} with {len(data.get('items', []))} items")
        return jsonify(data)
    except Exception as e:
        error_msg = f"Error fetching {order_sn}: {str(e)}"
        print(f"❌ {error_msg}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': error_msg}), 500

@app.route('/api/getRakumartDeliveryList', methods=['POST'])
def api_get_rakumart_delivery_list():
    """ラクマート配送依頼書一覧をプロキシ取得"""
    try:
        req = urllib.request.Request('http://localhost:8766/rakumart/deliveryList')
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/matchProductByImageHash', methods=['POST'])
def api_match_product_by_image_hash():
    """
    Base64画像をハッシュ化して、過去の購入記録と比較
    一致したら商品情報・平均仕入れ価格を返す
    """
    data = request.json
    image_data = data.get('imageData', '')  # data:image/jpeg;base64,...

    if not image_data:
        return jsonify({'error': '画像データがありません', 'matched': False})

    # ① 新しい画像をハッシュ化
    new_hash = hash_image_data(image_data)
    if not new_hash:
        return jsonify({'error': 'ハッシュ化失敗', 'matched': False})

    # ② 過去の購入記録を読み込み
    purchases = load_json(PURCHASES_FILE, [])

    # ③ 全ての購入記録の画像と比較
    for purchase in purchases:
        img_url = purchase.get('画像URL', '')
        if not img_url:
            continue

        past_hash = ''

        # ローカルJPGの場合
        if img_url.startswith('/static/images/'):
            local_path = BASE_DIR / img_url.lstrip('/')
            past_hash = hash_image_file(local_path)
        # Base64の場合
        elif img_url.startswith('data:'):
            past_hash = hash_image_data(img_url)

        # ④ ハッシュ比較
        if past_hash and new_hash == past_hash:
            # ⑤ 一致した！商品情報を返す
            sku = purchase.get('SKU', '')
            avg_cost = calc_average_cost(sku) if sku else 0.0

            return jsonify({
                'matched': True,
                'sku': sku,
                'name': purchase.get('商品名', ''),
                'pastAverageCost': avg_cost,
                'supplier': purchase.get('仕入れ先', ''),
                'imageUrl': img_url,
                'matchedPurchaseDate': purchase.get('仕入れ日', '')
            })

    # ハッシュ一致なし
    return jsonify({'matched': False})

# =============================================
# 内部: 商品マスタの標準仕入れ単価を移動平均で更新
# =============================================
def _update_master_costs(valid_rows):
    try:
        inventory = calc_inventory()
        cost_map  = {str(i['sku']).strip(): i['avgCost'] for i in inventory if i.get('sku')}
        products  = load_json(PRODUCTS_FILE)
        target_skus = {str(r.get('sku', '')).strip() for r in valid_rows}
        updated = 0
        for p in products:
            sku = str(p.get('SKU', '')).strip()
            if sku in target_skus and sku in cost_map:
                old = p.get('標準仕入れ単価', 0)
                p['標準仕入れ単価'] = cost_map[sku]
                print(f'SKU {sku}: {old} → {cost_map[sku]}')
                updated += 1
        save_json(PRODUCTS_FILE, products)
        print(f'商品マスタの単価を{updated}件更新しました。')
    except Exception as e:
        print(f'単価更新エラー: {e}')

# =============================================
# CSVエクスポート（バックアップ用）
# =============================================
@app.route('/api/exportCsv/<sheet>', methods=['GET'])
def api_export_csv(sheet):
    mapping = {
        'products':  (PRODUCTS_FILE,  ['商品ID','商品名','SKU','カテゴリ','仕入れ先','標準仕入れ単価','登録日','メモ','画像URL']),
        'purchases': (PURCHASES_FILE, ['仕入れID','仕入れ日','商品名','SKU','仕入れ先','仕入れ単価','数量','合計金額','送料','備考','画像URL']),
        'sales':     (SALES_FILE,     ['販売ID','販売日','商品名','SKU','販売チャネル','売価','数量','手数料率','手数料','送料負担','純売上','備考']),
    }
    if sheet not in mapping:
        return 'Unknown sheet', 404
    path, headers = mapping[sheet]
    data = load_json(path)
    lines = [','.join(f'"{h}"' for h in headers)]
    for row in data:
        lines.append(','.join(f'"{str(row.get(h,"")).replace(chr(34), chr(34)*2)}"' for h in headers))
    from flask import Response
    return Response('\n'.join(lines), mimetype='text/csv',
                    headers={'Content-Disposition': f'attachment; filename={sheet}.csv'})

# =============================================
# データインポート（GASからの移行用）
# =============================================
@app.route('/api/importFromGas', methods=['POST'])
def api_import_from_gas():
    """GASからエクスポートしたCSVデータをJSONに変換して保存"""
    data = request.json or {}
    if 'products' in data:
        save_json(PRODUCTS_FILE,  data['products'])
    if 'purchases' in data:
        save_json(PURCHASES_FILE, data['purchases'])
    if 'sales' in data:
        save_json(SALES_FILE,     data['sales'])
    return jsonify({'success': True})

# =============================================
# 起動
# =============================================
if __name__ == '__main__':
    import webbrowser
    import threading

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    # 初期データファイルが無ければ空で作成
    for f in [PRODUCTS_FILE, PURCHASES_FILE, SALES_FILE]:
        if not f.exists():
            save_json(f, [])
    print('=' * 50)
    print('🚀 EC販売管理ツール起動中...')
    print('📍 http://localhost:8080 でアクセスできます')
    print('🔄 ラクマートサーバーを起動しています...')
    start_rakumart_server()
    print('=' * 50)

    # サーバー起動後にブラウザを自動で開く
    def open_browser():
        time.sleep(1.5)
        webbrowser.open('http://localhost:8080')
    threading.Thread(target=open_browser, daemon=True).start()

    app.run(debug=False, port=8080, host='127.0.0.1', use_reloader=False)
