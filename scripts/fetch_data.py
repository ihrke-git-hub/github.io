#!/usr/bin/env python3
"""日経225銘柄の前日比ヒートマップHTML生成スクリプト"""

import csv
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import yfinance as yf
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
CSV_PATH = BASE_DIR / "data" / "nikkei225.csv"
OUTPUT_PATH = BASE_DIR / "heatmap" / "index.html"


def load_stock_list():
    """CSVから銘柄リストを読み込む"""
    stocks = []
    with open(CSV_PATH, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            stocks.append({
                "code": row["code"],
                "name": row["name"],
                "sector": row["sector"],
            })
    return stocks


def fetch_price_data(stocks):
    """yfinanceで全銘柄の株価データを取得し前日比を計算する"""
    tickers = [s["code"] for s in stocks]
    ticker_str = " ".join(tickers)

    # 直近5営業日分を取得（前日比計算に2日分必要、余裕を持って5日）
    data = yf.download(ticker_str, period="5d", group_by="ticker", progress=False)

    results = []
    for stock in stocks:
        code = stock["code"]
        try:
            if len(tickers) == 1:
                ticker_data = data
            else:
                ticker_data = data[code]

            closes = ticker_data["Close"].dropna()
            if len(closes) >= 2:
                prev_close = closes.iloc[-2]
                last_close = closes.iloc[-1]
                change_pct = ((last_close - prev_close) / prev_close) * 100
                results.append({
                    **stock,
                    "price": float(last_close),
                    "change_pct": float(change_pct),
                })
            else:
                results.append({**stock, "price": None, "change_pct": None})
        except Exception:
            results.append({**stock, "price": None, "change_pct": None})

    return results


def get_color(change_pct):
    """前日比に応じた背景色を返す"""
    if change_pct is None:
        return "#9E9E9E"
    if change_pct >= 3:
        return "#00873E"
    elif change_pct >= 1:
        return "#4CAF50"
    elif change_pct >= 0:
        return "#C8E6C9"
    elif change_pct >= -1:
        return "#FFCDD2"
    elif change_pct >= -3:
        return "#F44336"
    else:
        return "#B71C1C"


def get_text_color(change_pct):
    """背景色に応じた文字色を返す"""
    if change_pct is None:
        return "#FFFFFF"
    if change_pct >= 3 or change_pct <= -3:
        return "#FFFFFF"
    if change_pct >= 1 or change_pct <= -1:
        return "#FFFFFF"
    return "#333333"


def generate_html(results, updated_at):
    """ヒートマップHTMLを生成する"""
    # 業種ごとにグループ化
    sectors = {}
    for r in results:
        sector = r["sector"]
        if sector not in sectors:
            sectors[sector] = []
        sectors[sector].append(r)

    # 業種の表示順（証券コード順でソート）
    sector_order = sorted(sectors.keys(), key=lambda s: min(r["code"] for r in sectors[s]))

    # タイルHTML生成
    tiles_by_sector = {}
    for sector in sector_order:
        tiles = []
        for r in sorted(sectors[sector], key=lambda x: x["code"]):
            bg = get_color(r["change_pct"])
            fg = get_text_color(r["change_pct"])
            change_str = f'{r["change_pct"]:+.2f}%' if r["change_pct"] is not None else "N/A"
            price_str = f'¥{r["price"]:,.0f}' if r["price"] is not None else ""
            code_short = r["code"].replace(".T", "")
            tiles.append(
                f'<div class="tile" data-sector="{r["sector"]}" '
                f'data-code="{code_short}" '
                f'data-change="{r["change_pct"] if r["change_pct"] is not None else 0}" '
                f'style="background-color:{bg};color:{fg}">'
                f'<div class="tile-name">{r["name"]}</div>'
                f'<div class="tile-code">{code_short}</div>'
                f'<div class="tile-change">{change_str}</div>'
                f'<div class="tile-price">{price_str}</div>'
                f'</div>'
            )
        tiles_by_sector[sector] = tiles

    # JSON data for sorting
    json_data = json.dumps([{
        "code": r["code"].replace(".T", ""),
        "name": r["name"],
        "sector": r["sector"],
        "change_pct": r["change_pct"],
        "price": r["price"],
    } for r in results], ensure_ascii=False)

    # セクターごとのHTMLブロック
    sector_blocks = ""
    for sector in sector_order:
        tiles_html = "\n".join(tiles_by_sector[sector])
        sector_blocks += f"""
        <div class="sector-group" data-sector="{sector}">
            <h2 class="sector-title">{sector}</h2>
            <div class="grid">
                {tiles_html}
            </div>
        </div>
        """

    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>日経225 ヒートマップ</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Helvetica Neue", Arial, "Hiragino Sans", "Hiragino Kaku Gothic ProN", Meiryo, sans-serif;
            background: #1a1a2e;
            color: #e0e0e0;
            padding: 16px;
        }}
        .header {{
            text-align: center;
            margin-bottom: 20px;
        }}
        .header h1 {{
            font-size: 1.6rem;
            color: #ffffff;
            margin-bottom: 4px;
        }}
        .header .updated {{
            font-size: 0.85rem;
            color: #aaa;
        }}
        .controls {{
            display: flex;
            justify-content: center;
            gap: 8px;
            margin-bottom: 20px;
            flex-wrap: wrap;
        }}
        .controls button {{
            padding: 8px 16px;
            border: 1px solid #555;
            background: #2a2a4a;
            color: #e0e0e0;
            border-radius: 6px;
            cursor: pointer;
            font-size: 0.85rem;
            transition: background 0.2s;
        }}
        .controls button:hover {{
            background: #3a3a6a;
        }}
        .controls button.active {{
            background: #4a4a8a;
            border-color: #7a7aff;
        }}
        .legend {{
            display: flex;
            justify-content: center;
            gap: 4px;
            margin-bottom: 20px;
            flex-wrap: wrap;
            font-size: 0.75rem;
        }}
        .legend-item {{
            display: flex;
            align-items: center;
            gap: 4px;
        }}
        .legend-color {{
            width: 16px;
            height: 16px;
            border-radius: 3px;
        }}
        .sector-group {{
            margin-bottom: 24px;
        }}
        .sector-title {{
            font-size: 1rem;
            color: #ccc;
            border-bottom: 1px solid #444;
            padding-bottom: 4px;
            margin-bottom: 8px;
        }}
        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(110px, 1fr));
            gap: 4px;
        }}
        .tile {{
            padding: 8px 6px;
            border-radius: 6px;
            text-align: center;
            cursor: default;
            transition: transform 0.15s, box-shadow 0.15s;
            min-height: 80px;
            display: flex;
            flex-direction: column;
            justify-content: center;
        }}
        .tile:hover {{
            transform: scale(1.08);
            box-shadow: 0 4px 12px rgba(0,0,0,0.4);
            z-index: 10;
            position: relative;
        }}
        .tile-name {{
            font-size: 0.75rem;
            font-weight: 700;
            line-height: 1.2;
            margin-bottom: 2px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}
        .tile-code {{
            font-size: 0.65rem;
            opacity: 0.8;
        }}
        .tile-change {{
            font-size: 0.9rem;
            font-weight: 700;
            margin-top: 2px;
        }}
        .tile-price {{
            font-size: 0.6rem;
            opacity: 0.7;
            margin-top: 1px;
        }}
        /* flat mode (no sector grouping) */
        .flat-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(110px, 1fr));
            gap: 4px;
        }}
        @media (max-width: 600px) {{
            .grid, .flat-grid {{
                grid-template-columns: repeat(auto-fill, minmax(90px, 1fr));
            }}
            .tile {{ min-height: 70px; padding: 6px 4px; }}
            .tile-name {{ font-size: 0.65rem; }}
            .tile-change {{ font-size: 0.8rem; }}
            .header h1 {{ font-size: 1.2rem; }}
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>日経225 前日比ヒートマップ</h1>
        <div class="updated">最終更新: {updated_at}</div>
    </div>

    <div class="legend">
        <div class="legend-item"><div class="legend-color" style="background:#B71C1C"></div><span>-3%以下</span></div>
        <div class="legend-item"><div class="legend-color" style="background:#F44336"></div><span>-3~-1%</span></div>
        <div class="legend-item"><div class="legend-color" style="background:#FFCDD2"></div><span>-1~0%</span></div>
        <div class="legend-item"><div class="legend-color" style="background:#C8E6C9"></div><span>0~+1%</span></div>
        <div class="legend-item"><div class="legend-color" style="background:#4CAF50"></div><span>+1~+3%</span></div>
        <div class="legend-item"><div class="legend-color" style="background:#00873E"></div><span>+3%以上</span></div>
    </div>

    <div class="controls">
        <button class="active" onclick="sortBy('sector')">業種順</button>
        <button onclick="sortBy('change_desc')">上昇率順</button>
        <button onclick="sortBy('change_asc')">下落率順</button>
        <button onclick="sortBy('code')">コード順</button>
    </div>

    <div id="content">
        {sector_blocks}
    </div>

    <script>
    const stockData = {json_data};

    function getColor(pct) {{
        if (pct === null) return '#9E9E9E';
        if (pct >= 3) return '#00873E';
        if (pct >= 1) return '#4CAF50';
        if (pct >= 0) return '#C8E6C9';
        if (pct >= -1) return '#FFCDD2';
        if (pct >= -3) return '#F44336';
        return '#B71C1C';
    }}

    function getTextColor(pct) {{
        if (pct === null) return '#FFFFFF';
        if (pct >= 3 || pct <= -3) return '#FFFFFF';
        if (pct >= 1 || pct <= -1) return '#FFFFFF';
        return '#333333';
    }}

    function makeTile(s) {{
        const bg = getColor(s.change_pct);
        const fg = getTextColor(s.change_pct);
        const change = s.change_pct !== null ? (s.change_pct >= 0 ? '+' : '') + s.change_pct.toFixed(2) + '%' : 'N/A';
        const price = s.price !== null ? '¥' + s.price.toLocaleString('ja-JP', {{maximumFractionDigits: 0}}) : '';
        return '<div class="tile" style="background-color:' + bg + ';color:' + fg + '">'
            + '<div class="tile-name">' + s.name + '</div>'
            + '<div class="tile-code">' + s.code + '</div>'
            + '<div class="tile-change">' + change + '</div>'
            + '<div class="tile-price">' + price + '</div>'
            + '</div>';
    }}

    function sortBy(mode) {{
        const content = document.getElementById('content');
        const buttons = document.querySelectorAll('.controls button');
        buttons.forEach(b => b.classList.remove('active'));
        event.target.classList.add('active');

        let sorted;
        if (mode === 'sector') {{
            // Group by sector
            const groups = {{}};
            stockData.forEach(s => {{
                if (!groups[s.sector]) groups[s.sector] = [];
                groups[s.sector].push(s);
            }});
            const sectorOrder = Object.keys(groups).sort((a, b) => {{
                const minA = Math.min(...groups[a].map(s => parseInt(s.code)));
                const minB = Math.min(...groups[b].map(s => parseInt(s.code)));
                return minA - minB;
            }});
            let html = '';
            sectorOrder.forEach(sector => {{
                const items = groups[sector].sort((a, b) => a.code.localeCompare(b.code));
                html += '<div class="sector-group"><h2 class="sector-title">' + sector + '</h2><div class="grid">';
                items.forEach(s => {{ html += makeTile(s); }});
                html += '</div></div>';
            }});
            content.innerHTML = html;
            return;
        }}

        if (mode === 'change_desc') {{
            sorted = [...stockData].sort((a, b) => (b.change_pct || 0) - (a.change_pct || 0));
        }} else if (mode === 'change_asc') {{
            sorted = [...stockData].sort((a, b) => (a.change_pct || 0) - (b.change_pct || 0));
        }} else {{
            sorted = [...stockData].sort((a, b) => a.code.localeCompare(b.code));
        }}

        let html = '<div class="flat-grid">';
        sorted.forEach(s => {{ html += makeTile(s); }});
        html += '</div>';
        content.innerHTML = html;
    }}
    </script>
</body>
</html>"""
    return html


def main():
    print("銘柄リストを読み込み中...")
    stocks = load_stock_list()
    print(f"{len(stocks)}銘柄を読み込みました")

    print("株価データを取得中...")
    results = fetch_price_data(stocks)

    success = sum(1 for r in results if r["change_pct"] is not None)
    print(f"データ取得完了: {success}/{len(results)}銘柄")

    updated_at = datetime.now().strftime("%Y年%m月%d日 %H:%M JST")
    html = generate_html(results, updated_at)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"HTMLを生成しました: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
