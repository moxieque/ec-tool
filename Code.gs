// =============================================
// EC販売管理ツール - Google Apps Script
// =============================================

const SPREADSHEET_ID = ''; // ← デプロイ後に自動設定される
const SHEETS = {
  PRODUCTS: '商品マスタ',
  PURCHASES: '仕入れ',
  SALES: '販売',
  INVENTORY: '在庫'
};

// =============================================
// Webアプリ エントリーポイント
// =============================================
// バックアップ用シークレットトークン（URLに含まれる場合のみCSVを返す）
const CSV_TOKEN = 'mxq2026bk_c9f3a1e8d7';

function doGet(e) {
  // CSV エクスポートエンドポイント: ?action=csv&sheet=products|purchases|sales&token=CSV_TOKEN
  if (e && e.parameter && e.parameter.action === 'csv' && e.parameter.token === CSV_TOKEN) {
    return exportCsv_(e.parameter.sheet);
  }
  return HtmlService.createHtmlOutputFromFile('Index')
    .setTitle('EC販売管理ツール')
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL);
}

function exportCsv_(sheetKey) {
  const sheetMap = {
    products:  SHEETS.PRODUCTS,
    purchases: SHEETS.PURCHASES,
    sales:     SHEETS.SALES
  };
  const sheetName = sheetMap[sheetKey] || sheetKey;
  const ss = getSpreadsheet();
  const sheet = ss.getSheetByName(sheetName);
  if (!sheet) {
    return ContentService.createTextOutput('Sheet not found: ' + sheetName)
      .setMimeType(ContentService.MimeType.TEXT);
  }
  const data = sheet.getDataRange().getValues();
  const csv = data.map(row =>
    row.map(cell => {
      const s = cell instanceof Date
        ? Utilities.formatDate(cell, 'Asia/Tokyo', 'yyyy-MM-dd')
        : String(cell === null || cell === undefined ? '' : cell);
      return '"' + s.replace(/"/g, '""') + '"';
    }).join(',')
  ).join('\n');
  return ContentService.createTextOutput(csv).setMimeType(ContentService.MimeType.CSV);
}

// =============================================
// スプレッドシート取得（スタンドアロン対応）
// =============================================
function getSpreadsheet() {
  const props = PropertiesService.getScriptProperties();
  let ssId = props.getProperty('SPREADSHEET_ID');
  if (ssId) {
    try { return SpreadsheetApp.openById(ssId); } catch(e) {}
  }
  // 新規作成
  const ss = SpreadsheetApp.create('EC販売管理ツール - データ');
  props.setProperty('SPREADSHEET_ID', ss.getId());
  return ss;
}

// =============================================
// 初期セットアップ
// =============================================
function setup() {
  const ss = getSpreadsheet();

  // 商品マスタシート
  let productSheet = ss.getSheetByName(SHEETS.PRODUCTS);
  if (!productSheet) {
    productSheet = ss.insertSheet(SHEETS.PRODUCTS);
    productSheet.appendRow(['商品ID', '商品名', 'SKU', 'カテゴリ', '仕入れ先', '標準仕入れ単価', '登録日', 'メモ', '画像URL']);
    productSheet.getRange(1, 1, 1, 9).setFontWeight('bold').setBackground('#4a86e8').setFontColor('white');
    productSheet.setFrozenRows(1);
  }

  // 仕入れシート
  let purchaseSheet = ss.getSheetByName(SHEETS.PURCHASES);
  if (!purchaseSheet) {
    purchaseSheet = ss.insertSheet(SHEETS.PURCHASES);
    purchaseSheet.appendRow(['仕入れID', '仕入れ日', '商品名', 'SKU', '仕入れ先', '仕入れ単価', '数量', '合計金額', '送料', '備考', '画像URL']);
    purchaseSheet.getRange(1, 1, 1, 11).setFontWeight('bold').setBackground('#4a86e8').setFontColor('white');
    purchaseSheet.setFrozenRows(1);
  }

  // 販売シート
  let salesSheet = ss.getSheetByName(SHEETS.SALES);
  if (!salesSheet) {
    salesSheet = ss.insertSheet(SHEETS.SALES);
    salesSheet.appendRow(['販売ID', '販売日', '商品名', 'SKU', '販売チャネル', '売価', '数量', '手数料率', '手数料', '送料負担', '純売上', '備考']);
    salesSheet.getRange(1, 1, 1, 12).setFontWeight('bold').setBackground('#4a86e8').setFontColor('white');
    salesSheet.setFrozenRows(1);
  }

  // 在庫履歴シート
  let historySheet = ss.getSheetByName('在庫履歴');
  if (!historySheet) {
    historySheet = ss.insertSheet('在庫履歴');
    historySheet.appendRow(['日時', 'SKU', '商品名', '変更前', '変更後']);
    historySheet.getRange(1, 1, 1, 5).setFontWeight('bold').setBackground('#4a86e8').setFontColor('white');
    historySheet.setFrozenRows(1);
  }

  return { success: true, message: 'セットアップ完了！' };
}

// =============================================
// 商品マスタ
// =============================================
function getProducts() {
  const ss = getSpreadsheet();
  const sheet = ss.getSheetByName(SHEETS.PRODUCTS);
  if (!sheet) return [];

  const data = sheet.getDataRange().getValues();
  if (data.length <= 1) return [];

  const headers = data[0];
  return data.slice(1).map(row => {
    const obj = {};
    headers.forEach((h, i) => obj[h] = row[i]);
    return obj;
  }).filter(p => p['商品ID']);
}

function addProduct(data) {
  const ss = getSpreadsheet();
  const sheet = ss.getSheetByName(SHEETS.PRODUCTS);
  if (!sheet) { setup(); return addProduct(data); }

  ensureImageCols();
  const id = 'P' + new Date().getTime();
  const now = new Date();
  sheet.appendRow([
    id,
    data.name,
    data.sku || '',
    data.category || '',
    data.supplier || '',
    parseFloat(data.costPrice) || 0,
    now,
    data.memo || '',
    data.imageUrl || ''
  ]);
  return { success: true, id: id };
}

// =============================================
// 仕入れ管理
// =============================================
function getPurchases(limit) {
  const ss = getSpreadsheet();
  const sheet = ss.getSheetByName(SHEETS.PURCHASES);
  if (!sheet) return [];

  const data = sheet.getDataRange().getValues();
  if (data.length <= 1) return [];

  const headers = data[0];
  let rows = data.slice(1).map(row => {
    const obj = {};
    headers.forEach((h, i) => {
      obj[h] = row[i] instanceof Date ? Utilities.formatDate(row[i], 'Asia/Tokyo', 'yyyy-MM-dd') : row[i];
    });
    return obj;
  }).filter(p => p['仕入れID']);

  rows.reverse(); // 新しい順
  if (limit) rows = rows.slice(0, limit);
  return rows;
}

// 商品マスタ存在チェック（SKUまたは商品名で照合）
function checkProductInMaster(sku, name) {
  const products = getProducts();
  if (!products.length) throw new Error('商品マスタが空です。先に商品マスタへ商品を登録してください。');
  const skuTrim = (sku || '').trim();
  const nameTrim = (name || '').trim();
  const exists = products.some(p =>
    (skuTrim && p['SKU'] === skuTrim) || p['商品名'] === nameTrim
  );
  if (!exists) throw new Error(`商品マスタ未登録: "${nameTrim}" (SKU: ${skuTrim || 'なし'}) — 先に商品マスタへ登録してください。`);
}

function addPurchase(data) {
  // 商品マスタチェック
  checkProductInMaster(data.sku, data.productName);

  const ss = getSpreadsheet();
  let sheet = ss.getSheetByName(SHEETS.PURCHASES);
  if (!sheet) { setup(); sheet = ss.getSheetByName(SHEETS.PURCHASES); }

  const id = 'BUY' + new Date().getTime();
  const qty = parseInt(data.quantity) || 1;
  const unitCost = parseFloat(data.unitCost) || 0;
  const total = qty * unitCost;
  const shipping = parseFloat(data.shipping) || 0;
  const salePrice = parseFloat(data.salePrice) || '';

  ensureImageCols();
  ensureSalePriceCol();
  const imgUrl = data.imageUrl ? uploadImageToDrive(data.imageUrl, data.sku || '', true) : '';
  sheet.appendRow([
    id,
    new Date(data.date),
    data.productName,
    data.sku || '',
    data.supplier || '',
    unitCost,
    qty,
    total,
    shipping,
    data.memo || '',
    imgUrl,
    salePrice
  ]);
  return { success: true, id: id };
}

// =============================================
// 販売管理
// =============================================
function getSales(limit) {
  const ss = getSpreadsheet();
  const sheet = ss.getSheetByName(SHEETS.SALES);
  if (!sheet) return [];

  const data = sheet.getDataRange().getValues();
  if (data.length <= 1) return [];

  const headers = data[0];
  let rows = data.slice(1).map(row => {
    const obj = {};
    headers.forEach((h, i) => {
      obj[h] = row[i] instanceof Date ? Utilities.formatDate(row[i], 'Asia/Tokyo', 'yyyy-MM-dd') : row[i];
    });
    return obj;
  }).filter(s => s['販売ID']);

  rows.reverse();
  if (limit) rows = rows.slice(0, limit);
  return rows;
}

function addSale(data) {
  const ss = getSpreadsheet();
  let sheet = ss.getSheetByName(SHEETS.SALES);
  if (!sheet) { setup(); sheet = ss.getSheetByName(SHEETS.SALES); }

  const id = 'SALE' + new Date().getTime();
  const qty = parseInt(data.quantity) || 1;
  const price = parseFloat(data.price) || 0;
  const feeRate = parseFloat(data.feeRate) || 0;
  const fee = Math.round(price * qty * feeRate / 100);
  const shippingCost = parseFloat(data.shippingCost) || 0;
  const netSales = price * qty - fee - shippingCost;

  sheet.appendRow([
    id,
    new Date(data.date),
    data.productName,
    data.sku || '',
    data.channel,
    price,
    qty,
    feeRate,
    fee,
    shippingCost,
    netSales,
    data.memo || ''
  ]);
  return { success: true, id: id };
}

// =============================================
// 在庫計算（移動平均法）
// =============================================
function getInventory() {
  const purchases = getPurchases();
  const sales = getSales();
  const products = getProducts();

  // 商品マスタの画像URLマップ（SKU/商品名 → imageUrl）
  const productImageMap = {};
  products.forEach(p => {
    const img = p['画像URL'] || '';
    if (p['SKU'])   productImageMap[p['SKU']]   = img;
    if (p['商品名']) productImageMap[p['商品名']] = img;
  });

  // 仕入れ・販売を日付順（古い順）に統合して処理
  const allTx = [];
  purchases.forEach(p => allTx.push({ type: 'purchase', date: p['仕入れ日'], data: p }));
  sales.forEach(s => allTx.push({ type: 'sale', date: s['販売日'], data: s }));
  allTx.sort((a, b) => new Date(a.date) - new Date(b.date));

  const inventory = {};

  allTx.forEach(tx => {
    const d = tx.data;
    const key = d['SKU'] || d['商品名'];
    if (!inventory[key]) {
      inventory[key] = {
        name: d['商品名'],
        sku: d['SKU'],
        totalPurchased: 0,
        totalSold: 0,
        avgCost: 0,
        currentStock: 0,  // 移動平均計算用の現在庫数
        imageUrl: d['画像URL'] || productImageMap[key] || ''
      };
    }
    const item = inventory[key];

    // 画像URLが取れていなければ仕入れデータから補完
    if (!item.imageUrl && d['画像URL']) item.imageUrl = d['画像URL'];

    if (tx.type === 'purchase') {
      const newQty = parseInt(d['数量']) || 0;
      const newUnitCost = parseFloat(d['仕入れ単価']) || 0;
      // 移動平均法: (現在庫×現平均単価 + 新仕入数×新単価) / (現在庫 + 新仕入数)
      if (item.currentStock + newQty > 0) {
        item.avgCost = Math.round(
          (item.currentStock * item.avgCost + newQty * newUnitCost) /
          (item.currentStock + newQty)
        );
      }
      item.totalPurchased += newQty;
      item.currentStock += newQty;
    } else {
      const soldQty = parseInt(d['数量']) || 0;
      item.totalSold += soldQty;
      item.currentStock = Math.max(0, item.currentStock - soldQty);
      // 移動平均法では販売時に平均単価は変わらない
    }
  });

  return Object.values(inventory).map(item => {
    let imageUrl = item.imageUrl || productImageMap[item.sku] || productImageMap[item.name] || '';
    // Drive URL をサムネイル URL に変換（CORS 対応）
    if (imageUrl && imageUrl.startsWith('https://drive.google.com/uc?id=')) {
      const m = imageUrl.match(/id=([^&]+)/);
      if (m) {
        imageUrl = `https://drive.google.com/thumbnail?id=${m[1]}&sz=s200`;
      }
    }
    return {
      name: item.name,
      sku: item.sku,
      imageUrl: imageUrl,
      totalPurchased: item.totalPurchased,
      totalSold: item.totalSold,
      avgCost: item.avgCost,
      stock: item.totalPurchased - item.totalSold,
      alert: (item.totalPurchased - item.totalSold) <= 3
    };
  });
}

// =============================================
// 在庫管理（直接編集機能）
// =============================================
function updateInventoryDirect(sku, newStock) {
  if (!sku || newStock === undefined) {
    throw new Error('SKU と新在庫数が必須です');
  }

  // 現在の在庫を計算（購入 - 販売）
  const purchases = getPurchases(1000).filter(p => p['SKU'] === sku);
  const sales = getSales(1000).filter(s => s['SKU'] === sku);

  let totalPurchased = 0;
  if (purchases.length > 0) {
    totalPurchased = purchases.reduce((sum, p) => sum + (parseInt(p['数量']) || 0), 0);
  }

  let totalSold = 0;
  if (sales.length > 0) {
    totalSold = sales.reduce((sum, s) => sum + (parseInt(s['数量']) || 0), 0);
  }

  const currentStock = totalPurchased - totalSold;

  // 履歴に記録
  addInventoryHistory(sku, currentStock, newStock);

  return { success: true, oldStock: currentStock, newStock: newStock };
}

function addInventoryHistory(sku, oldStock, newStock) {
  const ss = getSpreadsheet();
  let historySheet = ss.getSheetByName('在庫履歴');

  if (!historySheet) {
    historySheet = ss.insertSheet('在庫履歴');
    historySheet.appendRow(['日時', 'SKU', '商品名', '変更前', '変更後']);
    historySheet.getRange(1, 1, 1, 5).setFontWeight('bold').setBackground('#4a86e8').setFontColor('white');
    historySheet.setFrozenRows(1);
  }

  // 商品名を取得
  const products = getProducts().filter(p => p['SKU'] === sku);
  const productName = products.length > 0 ? products[0]['商品名'] : '不明';

  const now = new Date();
  historySheet.appendRow([now, sku, productName, oldStock, newStock]);
}

// =============================================
// ダッシュボードデータ
// =============================================
function getDashboardData() {
  const purchases = getPurchases();
  const sales = getSales();
  const inventory = getInventory();

  const now = new Date();
  const thisMonth = now.getMonth();
  const thisYear = now.getFullYear();

  // 当月フィルター
  const thisMonthSales = sales.filter(s => {
    const d = new Date(s['販売日']);
    return d.getMonth() === thisMonth && d.getFullYear() === thisYear;
  });

  const thisMonthPurchases = purchases.filter(p => {
    const d = new Date(p['仕入れ日']);
    return d.getMonth() === thisMonth && d.getFullYear() === thisYear;
  });

  // 当月売上集計
  const monthRevenue = thisMonthSales.reduce((sum, s) => sum + (parseFloat(s['純売上']) || 0), 0);
  const monthCost = thisMonthPurchases.reduce((sum, p) => sum + (parseFloat(p['合計金額']) || 0), 0);
  const monthSalesCount = thisMonthSales.reduce((sum, s) => sum + (parseInt(s['数量']) || 0), 0);

  // 利益計算（当月販売の原価を算出）
  const inventoryMap = {};
  inventory.forEach(item => {
    const key = item.sku || item.name;
    inventoryMap[key] = item.avgCost;
  });

  const monthProfit = thisMonthSales.reduce((sum, s) => {
    const key = s['SKU'] || s['商品名'];
    const avgCost = inventoryMap[key] || 0;
    const qty = parseInt(s['数量']) || 0;
    const netSales = parseFloat(s['純売上']) || 0;
    return sum + (netSales - avgCost * qty);
  }, 0);

  // 月別売上グラフ用データ（過去6ヶ月）
  const monthlyData = [];
  for (let i = 5; i >= 0; i--) {
    const d = new Date(thisYear, thisMonth - i, 1);
    const m = d.getMonth();
    const y = d.getFullYear();
    const label = `${y}/${(m + 1).toString().padStart(2, '0')}`;

    const mSales = sales.filter(s => {
      const sd = new Date(s['販売日']);
      return sd.getMonth() === m && sd.getFullYear() === y;
    });
    const mRevenue = mSales.reduce((sum, s) => sum + (parseFloat(s['純売上']) || 0), 0);
    const mProfit = mSales.reduce((sum, s) => {
      const key = s['SKU'] || s['商品名'];
      const avgCost = inventoryMap[key] || 0;
      const qty = parseInt(s['数量']) || 0;
      const netSales = parseFloat(s['純売上']) || 0;
      return sum + (netSales - avgCost * qty);
    }, 0);

    monthlyData.push({ label, revenue: Math.round(mRevenue), profit: Math.round(mProfit) });
  }

  // 商品別利益ランキング（全期間）
  const productProfit = {};
  sales.forEach(s => {
    const key = s['商品名'];
    if (!productProfit[key]) productProfit[key] = { name: key, revenue: 0, cost: 0, profit: 0, qty: 0 };
    const avgCost = inventoryMap[s['SKU'] || s['商品名']] || 0;
    const qty = parseInt(s['数量']) || 0;
    const netSales = parseFloat(s['純売上']) || 0;
    productProfit[key].revenue += netSales;
    productProfit[key].cost += avgCost * qty;
    productProfit[key].profit += netSales - avgCost * qty;
    productProfit[key].qty += qty;
  });

  const productRanking = Object.values(productProfit)
    .sort((a, b) => b.profit - a.profit)
    .slice(0, 10)
    .map(p => ({ ...p, revenue: Math.round(p.revenue), cost: Math.round(p.cost), profit: Math.round(p.profit) }));

  // チャネル別売上
  const channelData = {};
  thisMonthSales.forEach(s => {
    const ch = s['販売チャネル'] || '不明';
    if (!channelData[ch]) channelData[ch] = 0;
    channelData[ch] += parseFloat(s['純売上']) || 0;
  });

  const lowStockItems = inventory.filter(i => i.alert && i.stock >= 0);

  return {
    monthRevenue: Math.round(monthRevenue),
    monthCost: Math.round(monthCost),
    monthProfit: Math.round(monthProfit),
    monthSalesCount,
    profitMargin: monthRevenue > 0 ? Math.round(monthProfit / monthRevenue * 100) : 0,
    totalProducts: inventory.length,
    lowStockCount: lowStockItems.length,
    monthlyData,
    productRanking,
    channelData,
    recentSales: sales.slice(0, 5),
    lowStockItems
  };
}

// =============================================
// 利益レポート（モード対応）
// =============================================
function getProfitReport(params) {
  const mode  = (params && params.mode)  || 'monthly';
  const count = parseInt((params && params.count) || 6) || 6;
  const startParam = params && params.startDate ? params.startDate : null;
  const endParam   = params && params.endDate   ? params.endDate   : null;

  const purchases = getPurchases();
  const sales     = getSales();
  const inventory = getInventory();

  // 移動平均コストマップ
  const inventoryMap = {};
  inventory.forEach(item => {
    inventoryMap[item.sku  || item.name] = item.avgCost;
    inventoryMap[item.name || item.sku]  = item.avgCost;
  });

  // 日付→ラベル変換
  function toLabel(dateStr) {
    const d = new Date(dateStr);
    if (mode === 'monthly') {
      return d.getFullYear() + '/' + String(d.getMonth()+1).padStart(2,'0');
    }
    if (mode === 'weekly') {
      const day = d.getDay() || 7;
      const mon = new Date(d); mon.setDate(d.getDate() - day + 1);
      const sun = new Date(mon); sun.setDate(mon.getDate() + 6);
      const fmt = x => (x.getMonth()+1)+'/'+x.getDate();
      return mon.getFullYear() + ' W' + fmt(mon) + '-' + fmt(sun);
    }
    if (mode === 'daily' || mode === 'range') {
      return Utilities.formatDate(d, 'Asia/Tokyo', 'yyyy/MM/dd');
    }
    return '';
  }

  // フィルタ範囲
  const now = new Date();
  let filterStart, filterEnd;
  if (mode === 'range' && startParam && endParam) {
    filterStart = new Date(startParam);
    filterEnd   = new Date(endParam); filterEnd.setHours(23,59,59,999);
  } else {
    filterEnd = new Date(now); filterEnd.setHours(23,59,59,999);
    if (mode === 'monthly') {
      filterStart = new Date(now.getFullYear(), now.getMonth() - count + 1, 1);
    } else if (mode === 'weekly') {
      const day = now.getDay() || 7;
      filterStart = new Date(now); filterStart.setDate(now.getDate() - day + 1 - (count-1)*7);
    } else {
      filterStart = new Date(now); filterStart.setDate(now.getDate() - count + 1);
      filterStart.setHours(0,0,0,0);
    }
  }

  // 期間リスト生成（range 以外）
  function buildPeriods() {
    const list = [];
    if (mode === 'monthly') {
      for (let i = count-1; i >= 0; i--) {
        const d = new Date(now.getFullYear(), now.getMonth()-i, 1);
        list.push(d.getFullYear() + '/' + String(d.getMonth()+1).padStart(2,'0'));
      }
    } else if (mode === 'weekly') {
      const day = now.getDay() || 7;
      const thisMon = new Date(now); thisMon.setDate(now.getDate() - day + 1);
      thisMon.setHours(0,0,0,0);
      for (let i = count-1; i >= 0; i--) {
        const mon = new Date(thisMon); mon.setDate(thisMon.getDate() - i*7);
        const sun = new Date(mon); sun.setDate(mon.getDate()+6);
        const fmt = x => (x.getMonth()+1)+'/'+x.getDate();
        list.push(mon.getFullYear() + ' W' + fmt(mon) + '-' + fmt(sun));
      }
    } else if (mode === 'daily') {
      for (let i = count-1; i >= 0; i--) {
        const d = new Date(now); d.setDate(now.getDate()-i); d.setHours(12,0,0,0);
        list.push(Utilities.formatDate(d, 'Asia/Tokyo', 'yyyy/MM/dd'));
      }
    }
    return list;
  }

  // 集計
  const summaryMap = {};
  const productProfit = {};

  sales.forEach(s => {
    const d = new Date(s['販売日']);
    if (d < filterStart || d > filterEnd) return;
    const label = (mode === 'range') ? 'range' : toLabel(s['販売日']);
    if (!summaryMap[label]) summaryMap[label] = { label, revenue: 0, profit: 0, salesCount: 0 };
    const key      = s['SKU'] || s['商品名'];
    const avgCost  = inventoryMap[key] || 0;
    const qty      = parseInt(s['数量']) || 0;
    const netSales = parseFloat(s['純売上']) || 0;
    const profit   = netSales - avgCost * qty;
    summaryMap[label].revenue    += netSales;
    summaryMap[label].profit     += profit;
    summaryMap[label].salesCount += qty;
    // 商品別
    if (!productProfit[key]) productProfit[key] = { name: s['商品名'], revenue: 0, cost: 0, profit: 0, qty: 0 };
    productProfit[key].revenue += netSales;
    productProfit[key].cost    += avgCost * qty;
    productProfit[key].profit  += profit;
    productProfit[key].qty     += qty;
  });

  let summaryData;
  if (mode === 'range') {
    const p = summaryMap['range'] || { revenue: 0, profit: 0, salesCount: 0 };
    p.label = (startParam || '') + ' 〜 ' + (endParam || '');
    summaryData = [p];
  } else {
    const periods = buildPeriods();
    summaryData = periods.map(p => summaryMap[p] || { label: p, revenue: 0, profit: 0, salesCount: 0 });
  }
  summaryData = summaryData.map(m => ({
    label: m.label, revenue: Math.round(m.revenue),
    profit: Math.round(m.profit), salesCount: m.salesCount
  }));

  const productRanking = Object.values(productProfit)
    .sort((a,b) => b.profit - a.profit).slice(0, 10)
    .map(p => ({ ...p, revenue: Math.round(p.revenue), cost: Math.round(p.cost), profit: Math.round(p.profit) }));

  return { summaryData, productRanking, mode };
}

// =============================================
// 画像URL列の自動追加・更新
// =============================================
function ensureImageCols() {
  const ss = getSpreadsheet();
  const targets = [
    { name: SHEETS.PRODUCTS,  col: '画像URL' },
    { name: SHEETS.PURCHASES, col: '画像URL' }
  ];
  targets.forEach(t => {
    const sheet = ss.getSheetByName(t.name);
    if (!sheet) return;
    const lastCol = sheet.getLastColumn();
    if (lastCol === 0) return;
    const headers = sheet.getRange(1, 1, 1, lastCol).getValues()[0];
    if (!headers.includes(t.col)) {
      sheet.getRange(1, lastCol + 1).setValue(t.col);
    }
  });
}

function ensureSalePriceCol() {
  const ss = getSpreadsheet();
  const sheet = ss.getSheetByName(SHEETS.PURCHASES);
  if (!sheet) return;
  const lastCol = sheet.getLastColumn();
  if (lastCol === 0) return;
  const headers = sheet.getRange(1, 1, 1, lastCol).getValues()[0];
  if (!headers.includes('販売価格')) {
    sheet.getRange(1, lastCol + 1).setValue('販売価格');
  }
}

// =============================================
// 画像圧縮機能
// =============================================
function compressImage(imageUrl, maxWidth) {
  try {
    if (!imageUrl || imageUrl.startsWith('data:')) {
      return null;
    }
    // 画像をダウンロード
    const res = UrlFetchApp.fetch(imageUrl, { muteHttpExceptions: true });
    if (res.getResponseCode() !== 200) return null;

    const blob = res.getBlob();
    const img = Images.newImage(blob);

    // 現在のサイズを取得
    const origWidth = img.getWidth();
    const origHeight = img.getHeight();

    // maxWidth に合わせてアスペクト比を維持して計算
    if (origWidth <= maxWidth) {
      // 既に小さい場合はそのまま
      return blob;
    }

    const scale = maxWidth / origWidth;
    const newWidth = Math.round(origWidth * scale);
    const newHeight = Math.round(origHeight * scale);

    // 画像をリサイズ
    const resized = img.resize(newWidth, newHeight);
    return resized.getAsBlob();
  } catch(e) {
    console.log('画像圧縮エラー: ' + e.message);
    return null;
  }
}

// =============================================
// Google Drive 画像アップロード（重複防止付き）
// =============================================
// 在庫一覧用の画像マップを取得（Drive URL は直接返す、CDN URL は base64変換）
// 注：Drive の圧縮版画像が保存されている想定のため、Drive URL は直接返す
function fetchInventoryImages(urls) {
  // 後方互換性のため、このまま返す
  // 実装は Index.html で src に直接指定する方針に変更
  const result = {};
  (urls || []).forEach(function(url) {
    if (url) result[url] = url;
  });
  return result;
}

function getImageFolder_() {
  const name = 'EC商品画像';
  const folders = DriveApp.getFoldersByName(name);
  if (folders.hasNext()) return folders.next();
  return DriveApp.createFolder(name);
}

function uploadImageToDrive(imageUrl, sku, compress) {
  if (typeof compress === 'undefined') compress = true;

  // すでにDrive URL / data URI / 空 の場合はそのまま返す
  if (!imageUrl ||
      imageUrl.startsWith('data:') ||
      imageUrl.startsWith('https://drive.google.com') ||
      imageUrl.startsWith('https://lh3.googleusercontent.com')) {
    return imageUrl;
  }
  try {
    const folder = getImageFolder_();
    // SKUがある場合：既存ファイルの重複チェック（拡張子違いも含む）
    if (sku) {
      const exts = ['jpg', 'jpeg', 'png', 'webp', 'gif'];
      for (const ext of exts) {
        const iter = folder.getFilesByName(sku + '.' + ext);
        if (iter.hasNext()) {
          const f = iter.next();
          f.setSharing(DriveApp.Access.ANYONE_WITH_LINK, DriveApp.Permission.VIEW);
          return 'https://drive.google.com/uc?id=' + f.getId();
        }
      }
    }
    // 画像をダウンロード
    const res = UrlFetchApp.fetch(imageUrl, { muteHttpExceptions: true });
    if (res.getResponseCode() !== 200) return imageUrl;
    let blob = res.getBlob();

    // 圧縮処理（compress = true の場合）
    if (compress) {
      const compressedBlob = compressImage(imageUrl, 200);
      if (compressedBlob) {
        blob = compressedBlob;
      }
    }

    const ct = blob.getContentType() || 'image/jpeg';
    const ext = ct.includes('png') ? 'png' : ct.includes('gif') ? 'gif' : ct.includes('webp') ? 'webp' : 'jpg';
    const fileName = sku ? (sku + '.' + ext) : ('product_' + new Date().getTime() + '.' + ext);
    // 取得後に同名ファイルが存在する場合も重複チェック
    if (sku) {
      const iter2 = folder.getFilesByName(fileName);
      if (iter2.hasNext()) {
        const f = iter2.next();
        f.setSharing(DriveApp.Access.ANYONE_WITH_LINK, DriveApp.Permission.VIEW);
        return 'https://drive.google.com/uc?id=' + f.getId();
      }
    }
    blob.setName(fileName);
    const file = folder.createFile(blob);
    file.setSharing(DriveApp.Access.ANYONE_WITH_LINK, DriveApp.Permission.VIEW);
    return 'https://drive.google.com/uc?id=' + file.getId();
  } catch (e) {
    console.log('Drive画像保存失敗: ' + e.message);
    return imageUrl; // フォールバック：元URLを返す
  }
}

function updateProductImages(imageMap) {
  // { sku: imageUrl } → 商品マスタの画像URLを更新（未設定のものだけ）
  const ss = getSpreadsheet();
  const sheet = ss.getSheetByName(SHEETS.PRODUCTS);
  if (!sheet) return;
  const lastCol = sheet.getLastColumn();
  if (lastCol === 0) return;
  const data = sheet.getDataRange().getValues();
  const headers = data[0];
  const skuIdx = headers.indexOf('SKU');
  let imgIdx = headers.indexOf('画像URL');
  if (skuIdx === -1) return;
  if (imgIdx === -1) {
    imgIdx = headers.length;
    sheet.getRange(1, imgIdx + 1).setValue('画像URL');
  }
  for (let i = 1; i < data.length; i++) {
    const sku = String(data[i][skuIdx] || '').trim();
    if (sku && imageMap[sku] && !data[i][imgIdx]) {
      const driveUrl = uploadImageToDrive(imageMap[sku], sku);
      sheet.getRange(i + 1, imgIdx + 1).setValue(driveUrl);
    }
  }
}

// =============================================
// 商品削除（商品マスタ・仕入れ・販売の全データ）
// =============================================
function deleteProductAll(productKey) {
  const ss = getSpreadsheet();
  const keyTrim = String(productKey || '').trim();
  if (!keyTrim) throw new Error('商品キーが指定されていません');

  let deleted = { products: 0, purchases: 0, sales: 0 };

  // 各シートでSKUまたは商品名が一致する行を後ろから削除
  const targets = [
    { sheetName: SHEETS.PRODUCTS,  skuCol: 'SKU', nameCol: '商品名',  key: 'products'  },
    { sheetName: SHEETS.PURCHASES, skuCol: 'SKU', nameCol: '商品名',  key: 'purchases' },
    { sheetName: SHEETS.SALES,     skuCol: 'SKU', nameCol: '商品名',  key: 'sales'     }
  ];

  targets.forEach(t => {
    const sheet = ss.getSheetByName(t.sheetName);
    if (!sheet || sheet.getLastRow() < 2) return;
    const data = sheet.getDataRange().getValues();
    const headers = data[0];
    const skuIdx  = headers.indexOf(t.skuCol);
    const nameIdx = headers.indexOf(t.nameCol);
    for (let i = data.length - 1; i >= 1; i--) {
      const sku  = skuIdx  >= 0 ? String(data[i][skuIdx]  || '').trim() : '';
      const name = nameIdx >= 0 ? String(data[i][nameIdx] || '').trim() : '';
      if ((sku && sku === keyTrim) || (name && name === keyTrim)) {
        sheet.deleteRow(i + 1);
        deleted[t.key]++;
      }
    }
  });

  return deleted;
}

// 複数商品を一括削除（シートを1回だけ読んで処理）
function deleteProductsBulk(productKeys) {
  if (!productKeys || !productKeys.length) throw new Error('削除対象が選択されていません');
  const keySet = new Set(productKeys.map(k => String(k).trim()));
  const ss = getSpreadsheet();
  let total = { products: 0, purchases: 0, sales: 0 };
  const targets = [
    { sheetName: SHEETS.PRODUCTS,  skuCol: 'SKU', nameCol: '商品名', key: 'products'  },
    { sheetName: SHEETS.PURCHASES, skuCol: 'SKU', nameCol: '商品名', key: 'purchases' },
    { sheetName: SHEETS.SALES,     skuCol: 'SKU', nameCol: '商品名', key: 'sales'     }
  ];
  targets.forEach(t => {
    const sheet = ss.getSheetByName(t.sheetName);
    if (!sheet || sheet.getLastRow() < 2) return;
    const data = sheet.getDataRange().getValues();
    const headers = data[0];
    const skuIdx  = headers.indexOf(t.skuCol);
    const nameIdx = headers.indexOf(t.nameCol);
    for (let i = data.length - 1; i >= 1; i--) {
      const sku  = skuIdx  >= 0 ? String(data[i][skuIdx]  || '').trim() : '';
      const name = nameIdx >= 0 ? String(data[i][nameIdx] || '').trim() : '';
      if ((sku && keySet.has(sku)) || (name && keySet.has(name))) {
        sheet.deleteRow(i + 1);
        total[t.key]++;
      }
    }
  });
  return { success: true, count: productKeys.length, deleted: total };
}

// =============================================
// チャネルマスタ
// =============================================
function getChannels() {
  return ['メルカリ', 'メルカリShops', 'Amazon', '楽天', 'Yahoo!ショッピング', 'BASE', 'BOOTH', '自社EC', 'その他'];
}

// =============================================
// 一括取込
// =============================================
function addProductsBulk(rows) {
  const ss = getSpreadsheet();
  let sheet = ss.getSheetByName(SHEETS.PRODUCTS);
  if (!sheet) { setup(); sheet = ss.getSheetByName(SHEETS.PRODUCTS); }

  const now = new Date();
  ensureImageCols();
  rows.forEach(data => {
    const id = 'P' + new Date().getTime() + Math.floor(Math.random() * 10000);
    sheet.appendRow([
      id,
      data.name || '',
      data.sku || '',
      data.category || '',
      data.supplier || '',
      parseFloat(data.costPrice) || 0,
      now,
      data.memo || '',
      data.imageUrl || ''
    ]);
  });
  return { success: true, count: rows.length };
}

function addPurchasesBulk(rows) {
  // SKU未入力行はスキップ（警告のみ）
  const skuMissing = rows.filter(data => !String(data.sku || '').trim());
  const validRows = rows.filter(data => String(data.sku || '').trim());

  if (!validRows.length) throw new Error('SKUが入力されている商品がありません。');

  const ss = getSpreadsheet();

  // 商品マスタに存在しない商品は自動登録
  let productSheet = ss.getSheetByName(SHEETS.PRODUCTS);
  if (!productSheet) { setup(); productSheet = ss.getSheetByName(SHEETS.PRODUCTS); }

  ensureImageCols();
  const products = getProducts();
  const autoAdded = [];
  const knownSkus = new Set(products.map(p => String(p['SKU'] || '').trim()));
  const knownNames = new Set(products.map(p => String(p['商品名'] || '').trim()));

  validRows.forEach(data => {
    const skuTrim = String(data.sku || '').trim();
    const nameTrim = String(data.productName || '').trim();
    const exists = (skuTrim && knownSkus.has(skuTrim)) || (nameTrim && knownNames.has(nameTrim));
    if (!exists) {
      // 商品マスタへ自動登録
      const id = 'P' + new Date().getTime() + Math.floor(Math.random() * 10000);
      productSheet.appendRow([
        id,
        nameTrim || skuTrim,
        skuTrim,
        data.category || 'その他',
        data.supplier || '',
        parseFloat(data.unitCost) || 0,
        new Date(data.date),
        data.memo || '',
        data.imageUrl || ''
      ]);
      autoAdded.push(nameTrim || skuTrim);
      // 同バッチ内の重複登録を防ぐ
      if (skuTrim) knownSkus.add(skuTrim);
      if (nameTrim) knownNames.add(nameTrim);
    }
  });

  let purchaseSheet = ss.getSheetByName(SHEETS.PURCHASES);
  if (!purchaseSheet) { setup(); purchaseSheet = ss.getSheetByName(SHEETS.PURCHASES); }

  const imageMap = {};  // SKU → imageUrl（商品マスタ更新用）
  validRows.forEach(data => {
    const id = 'BUY' + new Date().getTime() + Math.floor(Math.random() * 10000);
    const qty = parseInt(data.quantity) || 1;
    const unitCost = parseFloat(data.unitCost) || 0;
    const shipping = parseFloat(data.shipping) || 0;
    const skuStr = String(data.sku || '').trim();
    const rawImgUrl = data.imageUrl || '';
    const imgUrl = rawImgUrl ? uploadImageToDrive(rawImgUrl, skuStr, true) : '';

    purchaseSheet.appendRow([
      id,
      new Date(data.date),
      data.productName || '',
      data.sku || '',
      data.supplier || '',
      unitCost,
      qty,
      qty * unitCost,
      shipping,
      data.memo || '',
      imgUrl
    ]);
    if (imgUrl && skuStr) imageMap[skuStr] = imgUrl;
  });

  // 商品マスタの画像URLを自動更新（未設定のものだけ）
  if (Object.keys(imageMap).length > 0) {
    updateProductImages(imageMap);
  }

  // 【Plan B】商品マスタの「標準仕入れ単価」を最新の移動平均単価で更新
  try {
    updateProductMasterCosts(validRows);
  } catch (e) {
    console.error('商品マスタの単価更新に失敗:', e.message);
    // エラーでも仕入れ登録自体は成功とする（ロールバックなし）
  }

  return {
    success: true,
    count: validRows.length,
    autoAdded: autoAdded.length,
    skippedCount: skuMissing.length,
    skipped: skuMissing.map(r => r.productName || '')
  };
}

// =============================================
// 商品マスタの「標準仕入れ単価」を自動更新（Plan B実装）
// =============================================
function updateProductMasterCosts(validRows) {
  // validRows: 新規に登録された仕入れデータの配列
  // 各要素は { sku: "...", productName: "...", unitCost: ..., ... } という形式

  // 最新の在庫情報（移動平均単価を含む）を取得
  const inventory = getInventory();

  // SKU → avgCost のマップを構築
  const costMap = {};
  inventory.forEach(item => {
    if (item.sku) {
      costMap[String(item.sku).trim()] = item.avgCost;
    }
  });

  // 商品マスタシートを取得
  const ss = getSpreadsheet();
  const productSheet = ss.getSheetByName(SHEETS.PRODUCTS);
  if (!productSheet) {
    console.warn('商品マスタシートが見つかりません');
    return;
  }

  // 商品マスタの全行を読み込み
  const masterData = productSheet.getDataRange().getValues();
  if (masterData.length <= 1) {
    console.warn('商品マスタが空です');
    return;
  }

  const headers = masterData[0];
  const skuColIndex = headers.indexOf('SKU');      // 通常は列インデックス 2 (3列目)
  const costColIndex = headers.indexOf('標準仕入れ単価');  // 通常は列インデックス 5 (6列目)

  if (skuColIndex === -1 || costColIndex === -1) {
    console.error('必要な列が見つかりません。SKU=' + skuColIndex + ', 標準仕入れ単価=' + costColIndex);
    return;
  }

  // 更新対象のSKUセット（validRowsから抽出）
  const targetSkus = new Set(
    validRows
      .map(r => String(r.sku || '').trim())
      .filter(sku => sku.length > 0)
  );

  // 商品マスタの行をループして更新
  let updateCount = 0;
  for (let i = 1; i < masterData.length; i++) {
    const row = masterData[i];
    const sku = String(row[skuColIndex] || '').trim();

    // このSKUが今回の仕入れに含まれているか確認
    if (targetSkus.has(sku) && costMap[sku] !== undefined) {
      const oldCost = row[costColIndex];
      const newCost = costMap[sku];

      // スプレッドシートの行 i+1 (ヘッダを含めるため), 列 costColIndex+1 (1-indexed)
      productSheet.getRange(i + 1, costColIndex + 1).setValue(newCost);

      console.log(`SKU ${sku}: ${oldCost} → ${newCost}`);
      updateCount++;
    }
  }

  console.log(`商品マスタの単価を${updateCount}件更新しました。`);
}

// =============================================
// 商品マスタ一括登録（P2026020218484289用）
// =============================================
function importProductsMasterP2026020218484289() {
  const rows = [
    {name:"商品1",sku:"Abc1",category:"その他",supplier:"中国代行業者",costPrice:"29",memo:"注文:2025123013354270-品番1"},
    {name:"商品2",sku:"Abc2",category:"その他",supplier:"中国代行業者",costPrice:"766",memo:"注文:2026012020065996-品番1"},
    {name:"商品3",sku:"Abc3",category:"その他",supplier:"中国代行業者",costPrice:"1845",memo:"注文:2026012020065996-品番2"},
    {name:"商品4",sku:"Abc4",category:"その他",supplier:"中国代行業者",costPrice:"766",memo:"注文:2026012020065996-品番3"},
    {name:"商品5",sku:"Abc5",category:"その他",supplier:"中国代行業者",costPrice:"710",memo:"注文:2026012020065996-品番4"},
    {name:"商品6",sku:"Abc6",category:"その他",supplier:"中国代行業者",costPrice:"710",memo:"注文:2026012020065996-品番5"},
    {name:"商品7",sku:"Abc7",category:"その他",supplier:"中国代行業者",costPrice:"1845",memo:"注文:2026012020065996-品番6"},
    {name:"商品8",sku:"Abc8",category:"その他",supplier:"中国代行業者",costPrice:"660",memo:"注文:2026012020065996-品番7"},
    {name:"商品9",sku:"Abc9",category:"その他",supplier:"中国代行業者",costPrice:"624",memo:"注文:2026012020065996-品番8"},
    {name:"商品10",sku:"Abc10",category:"その他",supplier:"中国代行業者",costPrice:"753",memo:"注文:2026012020065996-品番9"},
    {name:"商品11",sku:"Abc11",category:"その他",supplier:"中国代行業者",costPrice:"753",memo:"注文:2026012020065996-品番10"},
    {name:"商品12",sku:"Abc12",category:"その他",supplier:"中国代行業者",costPrice:"654",memo:"注文:2026012020065996-品番11"},
    {name:"商品13",sku:"Abc13",category:"その他",supplier:"中国代行業者",costPrice:"1278",memo:"注文:2026012020065996-品番12"},
    {name:"商品14",sku:"Abc14",category:"その他",supplier:"中国代行業者",costPrice:"964",memo:"注文:2026012020065996-品番13"},
    {name:"商品15",sku:"Abc15",category:"その他",supplier:"中国代行業者",costPrice:"1647",memo:"注文:2026012020065996-品番14"},
    {name:"商品16",sku:"Abc16",category:"その他",supplier:"中国代行業者",costPrice:"1647",memo:"注文:2026012020065996-品番15"},
    {name:"商品17",sku:"Abc17",category:"その他",supplier:"中国代行業者",costPrice:"1750",memo:"注文:2026012020065996-品番16"},
    {name:"商品18",sku:"Abc18",category:"その他",supplier:"中国代行業者",costPrice:"8",memo:"注文:2026012020065996-品番17"},
    {name:"商品19",sku:"Abc19",category:"その他",supplier:"中国代行業者",costPrice:"643",memo:"注文:2026012020065996-品番18"},
    {name:"商品20",sku:"Abc20",category:"その他",supplier:"中国代行業者",costPrice:"828",memo:"注文:2026012020065996-品番19"}
  ];
  const result = addProductsBulk(rows);
  Logger.log('完了: ' + result.count + '件登録');
  return result;
}

// =============================================
// テスト関数
// =============================================
function testAddProduct() {
  try {
    // setup を実行
    setup();
    Logger.log('✅ setup() 完了');

    // テスト商品を登録
    const testData = {
      name: 'テスト商品',
      sku: 'TEST-SKU',
      category: 'テストカテゴリ',
      supplier: 'テスト仕入れ先',
      costPrice: '1000',
      memo: 'テスト用商品'
    };

    addProduct(testData);
    Logger.log('✅ addProduct() 完了');

    // 商品マスタを確認
    const products = getProducts();
    Logger.log('📊 登録済み商品数: ' + products.length);

    const testProduct = products.find(p => p['SKU'] === 'TEST-SKU');
    if (testProduct) {
      Logger.log('✅ テスト商品が見つかりました: ' + JSON.stringify(testProduct));
    } else {
      Logger.log('❌ テスト商品が見つかりません');
    }

    return { success: true, message: 'テスト完了', products: products.length };
  } catch (e) {
    Logger.log('❌ エラー: ' + e.message);
    return { success: false, error: e.message };
  }
}
