"""損益計算のテスト"""
import sys
from pathlib import Path

# srcディレクトリをパスに追加
sys.path.insert(0, str(Path(__file__).parent))

from src.profit_calculator import calculate_available_capital
from src.trading_history import load_trading_history
import json

print("=== 損益計算テスト ===\n")

# 1. 売買履歴を読み込み
history = load_trading_history()
print(f"売買履歴件数: {len(history)}")
print(f"売買履歴の中身:\n{json.dumps(history, ensure_ascii=False, indent=2)}\n")

# 2. 仮説データを読み込み
hypotheses_file = Path(__file__).parent / "data" / "hypotheses.json"
with open(hypotheses_file, "r", encoding="utf-8") as f:
    hypotheses = json.load(f)

print(f"保有銘柄数: {len(hypotheses)}\n")

# 3. 余力を計算
initial_capital = 6_711_800
result = calculate_available_capital(hypotheses, initial_capital)

print("=== 計算結果 ===")
print(f"初期資金: ¥{result['initial_capital']:,.0f}")
print(f"現在保有額: ¥{result['current_investment']:,.0f}")
print(f"累計売却額: ¥{result['cumulative_sales']:,.0f}")
print(f"余力: ¥{result['available_capital']:,.0f}")

# 4. 累計売却額の内訳
if history:
    print("\n=== 累計売却額の内訳 ===")
    for i, record in enumerate(history, 1):
        purchase_amount = record["purchase_price"] * record["shares"]
        cash = purchase_amount + record["after_tax_profit"]
        print(f"\n{i}. {record['name']} ({record['code']})")
        print(f"   購入額: ¥{purchase_amount:,.0f}")
        print(f"   税引き後利益: ¥{record['after_tax_profit']:,.0f}")
        print(f"   現金合計: ¥{cash:,.0f}")
else:
    print("\n売買履歴が空のため、累計売却額は0円になるはずです。")
