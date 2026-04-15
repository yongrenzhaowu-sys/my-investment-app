"""バリュエーション分析のテスト"""

import sys
from pathlib import Path
import pandas as pd

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

sys.path.insert(0, str(Path(__file__).parent))
from src.valuation_analysis import analyze_stock

# データ確認
DATA_DIR = project_root / "data" / "processed" / "jquants_historical_6years"
financials = pd.read_parquet(DATA_DIR / "financials_2021_2026.parquet")
prices = pd.read_parquet(DATA_DIR / "daily_bars_2021_2026.parquet")

# 共通の銘柄コードを探す
common_codes = set(financials['Code'].unique()).intersection(set(prices['Code'].unique()))
print(f"財務データと株価データの両方がある銘柄数: {len(common_codes)}")

# サンプル銘柄でテスト
sample_codes = list(common_codes)[:5]
print(f"\nテスト銘柄: {sample_codes}")

for code in sample_codes:
    print(f"\n{'='*80}")
    print(f"銘柄コード: {code}")
    print(f"{'='*80}")

    result = analyze_stock(code)

    print("\n【PEG Ratio】")
    peg = result['peg_ratio']
    if peg.get('error'):
        print(f"  エラー: {peg['error']}")
    else:
        print(f"  PEG: {peg.get('peg_ratio'):.2f}")
        print(f"  PER: {peg.get('per'):.1f}")
        print(f"  成長率: {peg.get('growth_rate')*100:.1f}%")
        print(f"  シグナル: {peg.get('signal')}")

    print("\n【移動平均乖離】")
    ma = result['ma_divergence']
    if ma.get('error'):
        print(f"  エラー: {ma['error']}")
    else:
        print(f"  現在価格: {ma.get('current_price'):.0f}")
        print(f"  25日MA: {ma.get('ma_25'):.0f}")
        print(f"  75日MA: {ma.get('ma_75'):.0f}")
        print(f"  乖離率（25日）: {ma.get('divergence_25'):.1f}%")
        print(f"  シグナル: {ma.get('signal')}")

    print("\n【EV/EBITDA】")
    ev = result['ev_ebitda']
    if ev.get('error'):
        print(f"  エラー: {ev['error']}")
    else:
        print(f"  EV/EBITDA: {ev.get('ev_ebitda'):.1f}")
        print(f"  シグナル: {ev.get('signal')}")

    print("\n【DCF Proxy】")
    dcf = result['dcf_proxy']
    if dcf.get('error'):
        print(f"  エラー: {dcf['error']}")
    else:
        print(f"  株価/理論株価: {dcf.get('price_to_theoretical'):.2f}")
        print(f"  現在株価: {dcf.get('current_price'):.0f}")
        print(f"  理論株価: {dcf.get('theoretical_price'):.0f}")
        print(f"  シグナル: {dcf.get('signal')}")

    print("\n【総合判定】")
    print(f"  シグナル: {result['overall_signal']}")

    print("\n【理論株価と乖離】")
    print(f"  現在株価: {result.get('current_price'):.0f}" if result.get('current_price') else "  現在株価: なし")
    print(f"  PEG理論株価: {result['theoretical_prices'].get('peg'):.0f}" if result['theoretical_prices'].get('peg') else "  PEG理論株価: なし")
    print(f"  EV/EBITDA理論株価: {result['theoretical_prices'].get('ev_ebitda'):.0f}" if result['theoretical_prices'].get('ev_ebitda') else "  EV/EBITDA理論株価: なし")
    print(f"  DCF理論株価: {result['theoretical_prices'].get('dcf'):.0f}" if result['theoretical_prices'].get('dcf') else "  DCF理論株価: なし")
    print(f"  最小理論株価（{result.get('min_theoretical_method')}）: {result.get('min_theoretical_price'):.0f}" if result.get('min_theoretical_price') else "  最小理論株価: なし")
    print(f"  乖離率: {result.get('divergence_from_min'):+.1f}%" if result.get('divergence_from_min') is not None else "  乖離率: なし")

    # 1銘柄のみテスト
    break
