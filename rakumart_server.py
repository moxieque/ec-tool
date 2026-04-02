#!/usr/bin/env python3
"""
ラクマート自動仕入れサーバー
Zaikoreの「ラクマート仕入れ」ボタンから呼び出される

使い方:
  python3 rakumart_server.py

初回: ブラウザが開くのでラクマートにログインしてください（以降は自動）
"""

import json
import re
import os
import ssl
import base64
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from http.server import HTTPServer, BaseHTTPRequestHandler
from playwright.sync_api import sync_playwright

# macOSのSSL証明書問題を回避
_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

PORT = 8766

def fetch_image_as_data_uri(url):
    """画像URLをダウンロードしてbase64 data URIに変換（GASのCSP対応）"""
    if not url:
        return ''
    try:
        req = urllib.request.Request(
            url,
            headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
                'Referer': 'https://www.rakumart.com/'
            }
        )
        with urllib.request.urlopen(req, timeout=8, context=_SSL_CTX) as r:
            data = r.read()
            ct = r.headers.get('Content-Type', 'image/jpeg').split(';')[0].strip()
            if not ct.startswith('image/'):
                ct = 'image/jpeg'
            b64 = base64.b64encode(data).decode('utf-8')
            return f"data:{ct};base64,{b64}"
    except Exception as e:
        print(f"  画像取得失敗: {url[:60]}... → {e}")
        return url  # 失敗時は元URLをそのまま返す
# このスクリプトと同じ場所に専用プロファイルを作成
PROFILE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".rakumart_profile")
LIST_URL    = "https://www.rakumart.com/user/deliveryList?status=received"
LOGIN_URL   = "https://passport.rakumart.com/hk/user/login"

def auto_login_rakumart(page, username: str, password: str) -> bool:
    """ラクマートに自動ログイン（クレデンシャル使用）"""
    try:
        print("🔄 ラクマートに自動ログイン中...")
        page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(1000)

        # ユーザー名入力
        username_field = page.locator("input[placeholder*='会員']").first
        if not username_field.is_visible():
            username_field = page.locator("input[type='text']").first

        if username_field.is_visible():
            username_field.fill("")
            username_field.type(username, delay=50)
            page.wait_for_timeout(500)

        # パスワード入力
        password_field = page.locator("input[type='password']").first
        if password_field.is_visible():
            password_field.fill("")
            password_field.type(password, delay=50)
            page.wait_for_timeout(500)

        # ログインボタンクリック
        login_btn = page.locator("button:has-text('ログイン')").first
        if not login_btn.is_visible():
            login_btn = page.locator("button[type='submit']").first

        if login_btn.is_visible():
            login_btn.click()
            # ログイン完了を待つ
            page.wait_for_url("**/deliveryList**", timeout=30000)
            page.wait_for_timeout(2000)
            print("✅ ラクマート自動ログイン成功")
            return True
        else:
            print("⚠️  ログインボタンが見つかりません")
            return False

    except Exception as e:
        print(f"⚠️  自動ログイン失敗: {e}")
        return False

def scrape_delivery_list(username: str = None, password: str = None):
    """ラクマートから配送依頼書の一覧を取得

    Args:
        username: ラクマート会員ID（あれば自動ログイン試行）
        password: ラクマートパスワード（あれば自動ログイン試行）
    """
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=PROFILE_DIR,
            headless=False,
            args=["--no-first-run", "--no-default-browser-check"],
            viewport={"width": 1280, "height": 900}
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        try:
            # ① 一覧ページへ
            page.goto(LIST_URL, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(3000)

            # ログインチェック
            if "login" in page.url.lower() or "passport" in page.url.lower():
                # クレデンシャルがあれば自動ログインを試みる
                if username and password:
                    if not auto_login_rakumart(page, username, password):
                        # 自動ログイン失敗時は手動ログイン
                        print("⚠️  ラクマートにログインしてください（ブラウザ画面）")
                        page.wait_for_url("**/deliveryList**", timeout=120000)
                        page.wait_for_timeout(2000)
                else:
                    # クレデンシャルなし → 手動ログイン
                    print("⚠️  ラクマートにログインしてください（ブラウザ画面）")
                    page.wait_for_url("**/deliveryList**", timeout=120000)
                    page.wait_for_timeout(2000)

            # 「過去の配送履歴」タブをクリック
            try:
                hist_tab = page.locator("text=過去の配送履歴").first
                if hist_tab.is_visible():
                    hist_tab.click()
                    page.wait_for_timeout(2000)
            except Exception:
                pass

            # ② 配送依頼書の一覧をDOMから抽出
            deliveries = page.evaluate("""() => {
                const items = [];
                document.querySelectorAll('a').forEach(a => {
                    const text = a.textContent.trim();
                    // P20xx... パターンの配送依頼書番号を抽出
                    if (/P20\\d+/.test(text)) {
                        items.push({
                            orderSn: text,
                            href: a.href
                        });
                    }
                });
                // 重複排除
                const seen = new Set();
                return items.filter(item => {
                    if (seen.has(item.orderSn)) return false;
                    seen.add(item.orderSn);
                    return true;
                });
            }""")

            if not deliveries:
                return {"error": "配送依頼書が見つかりません"}

            print(f"✅ {len(deliveries)}件の配送依頼書を取得しました")
            return {
                "success": True,
                "deliveries": deliveries,
                "count": len(deliveries)
            }

        except Exception as e:
            print(f"❌ エラー: {e}")
            return {"error": str(e)}
        finally:
            ctx.close()


def scrape_delivery_by_order_sn(order_sn):
    """指定の配送依頼書番号（orderSn）からデータを取得"""
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=PROFILE_DIR,
            headless=False,
            args=["--no-first-run", "--no-default-browser-check"],
            viewport={"width": 1280, "height": 900}
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        try:
            # ① 一覧ページへ
            page.goto(LIST_URL, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(3000)

            # ログインチェック
            if "login" in page.url.lower() or "passport" in page.url.lower():
                print(f"⚠️  ラクマートにログインしてください（ブラウザ画面）")
                page.wait_for_url("**/deliveryList**", timeout=120000)
                page.wait_for_timeout(2000)

            # 「過去の配送履歴」タブをクリック
            try:
                hist_tab = page.locator("text=過去の配送履歴").first
                if hist_tab.is_visible():
                    hist_tab.click()
                    page.wait_for_timeout(2000)
            except Exception:
                pass

            # ② 指定されたorderSnのリンクを探す
            links = page.evaluate("""() => {
                return Array.from(document.querySelectorAll('a'))
                    .filter(a => a.textContent.trim().includes('""" + order_sn + """'))
                    .map(a => ({ text: a.textContent.trim(), href: a.href }));
            }""")

            if not links:
                return {"error": f"配送依頼書 {order_sn} が見つかりません"}

            detail_url = links[0]["href"]
            print(f"📦 配送依頼書 {order_sn} の詳細ページへ移動...")

            # ③ 詳細ページへ
            page.goto(detail_url, wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(3000)
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(1500)
            page.evaluate("window.scrollTo(0, 0)")
            page.wait_for_timeout(500)

            # ④ 商品データをDOMから抽出（scrape_latest_delivery と同じロジック）
            items = page.evaluate("""() => {
                const rows = document.querySelectorAll('ul');
                const result = [];
                rows.forEach(row => {
                    const purchaseEl = row.querySelector('.totalPurchaseData');
                    if (!purchaseEl) return;
                    const pt = purchaseEl.innerText || '';

                    const noEl   = row.querySelector('.No');
                    const noText = (noEl?.innerText || '').replace(/\\D/g,'');
                    if (!noText || isNaN(parseInt(noText))) return;

                    const specEl   = row.querySelector('.goodsSpecification');
                    const orderEl  = row.querySelector('.orderNumber');
                    const variantEl= row.querySelector('.inputBox');

                    const qtyM    = pt.match(/数量[：:]\\s*(\\d+)/);
                    const priceM  = pt.match(/単価[：:][^（(]*[（(]([^）)]+)/);
                    const subM    = pt.match(/小計[：:][^（(]*[（(]([^）)]+)/);
                    const intlM   = pt.match(/国内運賃[：:][^（(]*[（(]([^）)]+)/);

                    const clean = s => parseInt((s||'0').replace(/[^0-9]/g,'')) || 0;

                    let imgUrl = '';
                    const imgs = Array.from(row.querySelectorAll('img'));
                    for (const img of imgs) {
                        const src = img.getAttribute('data-src') || img.getAttribute('data-lazy-src') || img.src || '';
                        if (!src || src.startsWith('data:') || src === window.location.href) continue;
                        const lower = src.toLowerCase();
                        if (lower.includes('icon') || lower.includes('logo') ||
                            lower.includes('avatar') || lower.includes('flag')) continue;
                        imgUrl = src;
                        break;
                    }

                    result.push({
                        no:           parseInt(noText),
                        orderNo:      (orderEl?.innerText||'').trim(),
                        variantNo:    (variantEl?.innerText||'').trim(),
                        spec:         (specEl?.innerText||'').trim().replace(/\\n+/g,' '),
                        qty:          clean(qtyM?.[1]),
                        unitPriceJpy: clean(priceM?.[1]),
                        subtotalJpy:  clean(subM?.[1]),
                        intlFreightJpy: clean(intlM?.[1]),
                        imgUrl:       imgUrl
                    });
                });
                return result;
            }""")

            if not items:
                return {"error": "商品データが取得できませんでした"}

            # ⑤ 画像URLをbase64 data URIに変換
            print(f"  🖼️  画像を変換中（{sum(1 for i in items if i.get('imgUrl'))}件）...")
            urls = [item.get('imgUrl', '') for item in items]
            with ThreadPoolExecutor(max_workers=5) as executor:
                future_to_idx = {executor.submit(fetch_image_as_data_uri, url): idx
                                 for idx, url in enumerate(urls) if url}
                for future in as_completed(future_to_idx):
                    idx = future_to_idx[future]
                    try:
                        items[idx]['imgUrl'] = future.result()
                    except Exception:
                        pass
            print(f"  ✅ 画像変換完了")

            # ⑤ フッターの国際送料・合計を取得
            footer = page.evaluate("""() => {
                const body = document.body.innerText;
                const m1 = body.match(/国際運賃[：:\\s]*([¥￥]?[\\d,]+)円/);
                const m2 = body.match(/合計商品代金[：:\\s]*([¥￥]?[\\d,]+)円/);
                const clean = s => parseInt((s||'').replace(/[^0-9]/g,'')) || 0;
                return {
                    intlShipping: clean(m1?.[1]),
                    totalProductJpy: clean(m2?.[1])
                };
            }""")

            imgs_found = sum(1 for i in items if i.get('imgUrl'))
            print(f"✅ {len(items)}商品を取得しました（画像あり: {imgs_found}件）")

            return {
                "success":       True,
                "orderSn":       order_sn,
                "detailUrl":     detail_url,
                "items":         items,
                "intlShipping":  footer["intlShipping"],
                "totalProduct":  footer["totalProductJpy"]
            }

        except Exception as e:
            print(f"❌ エラー: {e}")
            return {"error": str(e)}
        finally:
            ctx.close()


def scrape_latest_delivery():
    """ラクマートから最新の配送依頼書データを取得"""
    with sync_playwright() as p:
        # 専用プロファイル（初回ログイン後は再ログイン不要）
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=PROFILE_DIR,
            headless=False,
            args=["--no-first-run", "--no-default-browser-check"],
            viewport={"width": 1280, "height": 900}
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        try:
            # ① 一覧ページへ
            page.goto(LIST_URL, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(3000)

            # ログインチェック（未ログインならログインページになる）
            if "login" in page.url.lower() or "passport" in page.url.lower():
                print("⚠️  ラクマートにログインしてください（ブラウザ画面）")
                page.wait_for_url("**/deliveryList**", timeout=120000)
                page.wait_for_timeout(2000)

            # 「過去の配送履歴」タブをクリック（受領済み）
            try:
                hist_tab = page.locator("text=過去の配送履歴").first
                if hist_tab.is_visible():
                    hist_tab.click()
                    page.wait_for_timeout(2000)
            except Exception:
                pass

            # ② 最新の配送依頼書リンクを取得
            links = page.evaluate("""() => {
                return Array.from(document.querySelectorAll('a'))
                    .filter(a => /P20\\d+/.test(a.textContent.trim()))
                    .map(a => ({ text: a.textContent.trim(), href: a.href }));
            }""")

            if not links:
                return {"error": "配送依頼書が見つかりません。ログイン状態を確認してください。"}

            latest   = links[0]
            order_sn = latest["text"]
            detail_url = latest["href"]
            print(f"📦 最新の配送依頼書: {order_sn}")

            # ③ 詳細ページへ
            page.goto(detail_url, wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(3000)
            # 画像が遅延ロードされる場合はスクロールして読み込みを促す
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(1500)
            page.evaluate("window.scrollTo(0, 0)")
            page.wait_for_timeout(500)

            # ④ 商品データをDOMから抽出
            items = page.evaluate("""() => {
                const rows = document.querySelectorAll('ul');
                const result = [];
                rows.forEach(row => {
                    const purchaseEl = row.querySelector('.totalPurchaseData');
                    if (!purchaseEl) return;
                    const pt = purchaseEl.innerText || '';

                    const noEl   = row.querySelector('.No');
                    const noText = (noEl?.innerText || '').replace(/\\D/g,'');
                    if (!noText || isNaN(parseInt(noText))) return;

                    const specEl   = row.querySelector('.goodsSpecification');
                    const orderEl  = row.querySelector('.orderNumber');
                    const variantEl= row.querySelector('.inputBox');

                    const qtyM    = pt.match(/数量[：:]\\s*(\\d+)/);
                    const priceM  = pt.match(/単価[：:][^（(]*[（(]([^）)]+)/);
                    const subM    = pt.match(/小計[：:][^（(]*[（(]([^）)]+)/);
                    const intlM   = pt.match(/国内運賃[：:][^（(]*[（(]([^）)]+)/);

                    const clean = s => parseInt((s||'0').replace(/[^0-9]/g,'')) || 0;

                    // 商品画像URL取得（遅延ロード対応）
                    let imgUrl = '';
                    const imgs = Array.from(row.querySelectorAll('img'));
                    for (const img of imgs) {
                        // data-src（遅延ロード）または通常のsrcを取得
                        const src = img.getAttribute('data-src') || img.getAttribute('data-lazy-src') || img.src || '';
                        if (!src || src.startsWith('data:') || src === window.location.href) continue;
                        const lower = src.toLowerCase();
                        if (lower.includes('icon') || lower.includes('logo') ||
                            lower.includes('avatar') || lower.includes('flag')) continue;
                        imgUrl = src;
                        break;
                    }

                    result.push({
                        no:           parseInt(noText),
                        orderNo:      (orderEl?.innerText||'').trim(),
                        variantNo:    (variantEl?.innerText||'').trim(),
                        spec:         (specEl?.innerText||'').trim().replace(/\\n+/g,' '),
                        qty:          clean(qtyM?.[1]),
                        unitPriceJpy: clean(priceM?.[1]),
                        subtotalJpy:  clean(subM?.[1]),
                        intlFreightJpy: clean(intlM?.[1]),
                        imgUrl:       imgUrl
                    });
                });
                return result;
            }""")

            if not items:
                return {"error": "商品データが取得できませんでした"}

            # ⑤ 元のCDN URLをimgOrigUrlとして保存（スプレッドシート保存用）
            for item in items:
                if item.get('imgUrl'):
                    item['imgOrigUrl'] = item['imgUrl']

            # ⑤ 画像URLをbase64 data URIに変換（ブラウザ表示用・GASのCSP制限を回避）
            print(f"  🖼️  画像を変換中（{sum(1 for i in items if i.get('imgUrl'))}件）...")
            urls = [item.get('imgUrl', '') for item in items]
            with ThreadPoolExecutor(max_workers=5) as executor:
                future_to_idx = {executor.submit(fetch_image_as_data_uri, url): idx
                                 for idx, url in enumerate(urls) if url}
                for future in as_completed(future_to_idx):
                    idx = future_to_idx[future]
                    try:
                        items[idx]['imgUrl'] = future.result()
                    except Exception:
                        pass
            print(f"  ✅ 画像変換完了")

            # ⑤ フッターの国際送料・合計を取得
            footer = page.evaluate("""() => {
                const body = document.body.innerText;
                const m1 = body.match(/国際運賃[：:\\s]*([¥￥]?[\\d,]+)円/);
                const m2 = body.match(/合計商品代金[：:\\s]*([¥￥]?[\\d,]+)円/);
                const clean = s => parseInt((s||'').replace(/[^0-9]/g,'')) || 0;
                return {
                    intlShipping: clean(m1?.[1]),
                    totalProductJpy: clean(m2?.[1])
                };
            }""")

            imgs_found = sum(1 for i in items if i.get('imgUrl'))
            print(f"✅ {len(items)}商品を取得しました（画像あり: {imgs_found}件）")
            if items and not items[0].get('imgUrl'):
                print("  ⚠️ 画像が取得できませんでした。ページ構造を確認してください。")
            return {
                "success":       True,
                "orderSn":       order_sn,
                "detailUrl":     detail_url,
                "items":         items,
                "intlShipping":  footer["intlShipping"],
                "totalProduct":  footer["totalProductJpy"]
            }

        except Exception as e:
            print(f"❌ エラー: {e}")
            return {"error": str(e)}
        finally:
            ctx.close()


class RakumartHandler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def do_GET(self):
        # パスをクエリ文字列で分割
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(self.path)
        path = parsed.path
        query_params = parse_qs(parsed.query)

        if path == "/rakumart/latest":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._cors()
            self.end_headers()
            try:
                # orderSn パラメータを取得（あれば）
                order_sn = query_params.get('orderSn', [None])[0]
                if order_sn:
                    # 特定の配送依頼書を取得
                    print(f"📦 Fetching specific order: {order_sn}")
                    data = scrape_delivery_by_order_sn(order_sn)
                else:
                    # 最新を取得
                    data = scrape_latest_delivery()
            except Exception as e:
                data = {"error": str(e)}
            self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))
        elif path == "/rakumart/deliveryList":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._cors()
            self.end_headers()
            try:
                # config.json から ラクマート認証情報を取得
                username = None
                password = None
                config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "config.json")
                if os.path.exists(config_path):
                    try:
                        with open(config_path, 'r', encoding='utf-8') as f:
                            cfg = json.load(f)
                            username = cfg.get('rakumartUsername')
                            encrypted_pwd = cfg.get('rakumartPasswordEncrypted')
                            # 簡易復号（app.pyと同じロジック）
                            if encrypted_pwd:
                                try:
                                    _ENCRYPTION_KEY = "ec-tool-rakumart-2026"
                                    b64_encrypted = base64.b64decode(encrypted_pwd).decode()
                                    decrypted = ''.join(chr(ord(c) ^ ord(_ENCRYPTION_KEY[i % len(_ENCRYPTION_KEY)])) for i, c in enumerate(b64_encrypted))
                                    password = base64.b64decode(decrypted).decode()
                                except:
                                    password = None
                    except:
                        pass

                data = scrape_delivery_list(username=username, password=password)
            except Exception as e:
                data = {"error": str(e)}
            self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))
        elif path == "/health":
            self.send_response(200)
            self._cors()
            self.end_headers()
            self.wfile.write(b'{"status":"ok"}')
        else:
            self.send_response(404)
            self.end_headers()

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin",  "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def log_message(self, fmt, *args):
        print(f"  [{self.address_string()}] {fmt % args}")


if __name__ == "__main__":
    os.makedirs(PROFILE_DIR, exist_ok=True)
    print(f"🚀 ラクマートサーバー起動: http://localhost:{PORT}")
    print(f"   プロファイル: {PROFILE_DIR}")
    print(f"   初回はブラウザが開きます。ラクマートにログインしてください。")
    server = HTTPServer(("", PORT), RakumartHandler)
    server.serve_forever()
