"""
持ち株バリュエーション分析モジュール

4つの分析手法を提供：
1. PEG Ratio（株価収益成長率）
2. Moving Average Divergence（移動平均乖離）
3. EV/EBITDA（簡易版）
4. DCF Proxy（簡易版）
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple


# データパス（ワークスペースルートからの相対パス）
BASE_DIR = Path(__file__).parent.parent.parent.parent
DATA_DIR = BASE_DIR / "data" / "processed" / "jquants_historical_6years"

PRICES_PATH = DATA_DIR / "daily_bars_2021_2026.parquet"
FINANCIALS_PATH = DATA_DIR / "financials_2021_2026.parquet"


def load_jquants_data() -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    J-Quantsデータを読み込み

    Returns:
        (prices, financials): 株価データと財務データ
    """
    prices = pd.read_parquet(PRICES_PATH)
    prices['Date'] = pd.to_datetime(prices['Date'])

    # 調整済み株価の正しい計算（CRITICAL）
    if 'AdjFactor' in prices.columns:
        prices['Price'] = prices['C'] * prices['AdjFactor']
    else:
        prices['Price'] = prices['C']

    financials = pd.read_parquet(FINANCIALS_PATH)
    financials['DiscDate'] = pd.to_datetime(financials['DiscDate'])
    financials['CurPerEn'] = pd.to_datetime(financials['CurPerEn'])

    return prices, financials


def get_latest_financials(financials: pd.DataFrame, code: str, reference_date: Optional[datetime] = None) -> Optional[pd.DataFrame]:
    """
    最新の財務データを取得

    Args:
        financials: 財務データ
        code: 銘柄コード（5桁文字列）
        reference_date: 基準日（Noneの場合は現在日時）

    Returns:
        最新の財務データ（1行のDataFrame）、データがない場合はNone
    """
    if reference_date is None:
        reference_date = datetime.now()

    code_data = financials[
        (financials['Code'] == code) &
        (financials['DiscDate'] <= reference_date)
    ].copy()

    if len(code_data) == 0:
        return None

    # 決算期でソート
    code_data = code_data.sort_values('CurPerEn')

    return code_data.iloc[-1:].copy()


def get_price_history(prices: pd.DataFrame, code: str, days: int = 100) -> pd.DataFrame:
    """
    株価履歴を取得（移動平均計算用）

    Args:
        prices: 株価データ
        code: 銘柄コード（5桁文字列）
        days: 取得日数

    Returns:
        株価履歴（Date昇順）
    """
    code_prices = prices[prices['Code'] == code].copy()

    if len(code_prices) == 0:
        return pd.DataFrame()

    code_prices = code_prices.sort_values('Date')

    # 最新N日分を取得
    return code_prices.tail(days).copy()


def calculate_peg_ratio(financials: pd.DataFrame, prices: pd.DataFrame, code: str, reference_date: Optional[datetime] = None) -> Dict:
    """
    PEG Ratio計算

    PEG = PER / (成長率 × 100)
    - PEG < 1.0: 割安
    - PEG 1.0-2.0: 適正
    - PEG > 2.0: 割高

    Args:
        financials: 財務データ
        prices: 株価データ
        code: 銘柄コード
        reference_date: 基準日

    Returns:
        {
            'peg_ratio': float or None,
            'per': float or None,
            'growth_rate': float or None (年率、小数表記),
            'signal': 'BUY'/'HOLD'/'SELL'/None,
            'error': str or None
        }
    """
    if reference_date is None:
        reference_date = datetime.now()

    # 過去5年の純利益データを取得
    code_data = financials[
        (financials['Code'] == code) &
        (financials['DiscDate'] <= reference_date)
    ].copy()

    if len(code_data) == 0:
        return {'peg_ratio': None, 'per': None, 'growth_rate': None, 'signal': None, 'error': '財務データなし'}

    code_data = code_data.sort_values('CurPerEn')

    # 純利益を数値に変換
    code_data['NP'] = pd.to_numeric(code_data['NP'], errors='coerce')
    code_data = code_data[code_data['NP'].notna() & (code_data['NP'] > 0)]

    if len(code_data) < 2:
        return {'peg_ratio': None, 'per': None, 'growth_rate': None, 'signal': None, 'error': '純利益データ不足'}

    # 最新5期分
    recent = code_data.tail(5)
    np_values = recent['NP'].values

    # 成長率計算（CAGR）
    if len(np_values) >= 2:
        years = len(np_values) - 1
        try:
            growth_rate = (np_values[-1] / np_values[0]) ** (1 / years) - 1
        except:
            return {'peg_ratio': None, 'per': None, 'growth_rate': None, 'signal': None, 'error': '成長率計算エラー'}
    else:
        return {'peg_ratio': None, 'per': None, 'growth_rate': None, 'signal': None, 'error': '成長率計算に必要なデータ不足'}

    # 時価総額取得
    latest_prices = get_price_history(prices, code, days=10)
    if len(latest_prices) == 0:
        return {'peg_ratio': None, 'per': None, 'growth_rate': None, 'signal': None, 'error': '株価データなし'}

    latest_price = latest_prices.iloc[-1]
    market_cap = latest_price['Price'] * latest_price['Vo'] * 100

    # PER計算
    latest_np = np_values[-1]
    per = market_cap / latest_np

    # PEG計算
    if growth_rate <= 0:
        # 成長率がマイナスまたはゼロの場合はPEG計算不可
        return {'peg_ratio': None, 'per': per, 'growth_rate': growth_rate, 'signal': 'SELL', 'error': '成長率マイナス'}

    peg_ratio = per / (growth_rate * 100)

    # シグナル判定
    if peg_ratio < 1.0:
        signal = 'BUY'
    elif peg_ratio <= 2.0:
        signal = 'HOLD'
    else:
        signal = 'SELL'

    # 理論株価計算（PEG=1.0を適正とする）
    # 理論PER = 成長率 × 100
    # 理論株価 = (NP / 発行済株式数) × 理論PER
    shares_outstanding = latest_price['Vo'] * 100
    eps = latest_np / shares_outstanding
    theoretical_per = growth_rate * 100
    theoretical_price = eps * theoretical_per
    current_price = latest_price['Price']

    return {
        'peg_ratio': peg_ratio,
        'per': per,
        'growth_rate': growth_rate,
        'theoretical_price': theoretical_price,
        'current_price': current_price,
        'signal': signal,
        'error': None
    }


def calculate_ma_divergence(prices: pd.DataFrame, code: str) -> Dict:
    """
    移動平均乖離率計算

    - 25日移動平均線（短期）
    - 75日移動平均線（中期）

    シグナル:
    - ゴールデンクロス（25日MAが75日MAを上抜け）: BUY
    - デッドクロス（25日MAが75日MAを下抜け）: SELL
    - その他: HOLD

    Args:
        prices: 株価データ
        code: 銘柄コード

    Returns:
        {
            'current_price': float or None,
            'ma_25': float or None,
            'ma_75': float or None,
            'divergence_25': float or None (乖離率、%表記),
            'divergence_75': float or None,
            'signal': 'BUY'/'HOLD'/'SELL'/None,
            'error': str or None
        }
    """
    # 100日分の株価取得（75日MA計算 + バッファ）
    price_history = get_price_history(prices, code, days=100)

    if len(price_history) < 75:
        return {
            'current_price': None,
            'ma_25': None,
            'ma_75': None,
            'divergence_25': None,
            'divergence_75': None,
            'signal': None,
            'error': '株価データ不足（75日以上必要）'
        }

    # 移動平均計算
    price_history['MA_25'] = price_history['Price'].rolling(window=25).mean()
    price_history['MA_75'] = price_history['Price'].rolling(window=75).mean()

    # 最新データ
    latest = price_history.iloc[-1]
    current_price = latest['Price']
    ma_25 = latest['MA_25']
    ma_75 = latest['MA_75']

    # 乖離率計算
    divergence_25 = ((current_price - ma_25) / ma_25) * 100
    divergence_75 = ((current_price - ma_75) / ma_75) * 100

    # ゴールデンクロス/デッドクロス判定
    # 直近2日分でクロスを判定
    if len(price_history) >= 2:
        prev = price_history.iloc[-2]
        prev_ma_25 = prev['MA_25']
        prev_ma_75 = prev['MA_75']

        # ゴールデンクロス: 前日は25MA < 75MA、今日は25MA > 75MA
        if prev_ma_25 < prev_ma_75 and ma_25 > ma_75:
            signal = 'BUY'
        # デッドクロス: 前日は25MA > 75MA、今日は25MA < 75MA
        elif prev_ma_25 > prev_ma_75 and ma_25 < ma_75:
            signal = 'SELL'
        # 現在価格が両方のMAより上: 強気
        elif current_price > ma_25 and current_price > ma_75:
            signal = 'HOLD'
        # 現在価格が両方のMAより下: 弱気
        elif current_price < ma_25 and current_price < ma_75:
            signal = 'SELL'
        else:
            signal = 'HOLD'
    else:
        signal = 'HOLD'

    return {
        'current_price': current_price,
        'ma_25': ma_25,
        'ma_75': ma_75,
        'divergence_25': divergence_25,
        'divergence_75': divergence_75,
        'signal': signal,
        'error': None
    }


def calculate_ev_ebitda(financials: pd.DataFrame, prices: pd.DataFrame, code: str, reference_date: Optional[datetime] = None) -> Dict:
    """
    EV/EBITDA計算（簡易版）

    EV = 時価総額 + 純負債
    純負債 = 総負債 - 現金 = (総資産 - 自己資本) - 現金
    EBITDA ≈ 営業利益（OP）

    判定基準:
    - EV/EBITDA < 10: 割安 (BUY)
    - EV/EBITDA 10-15: 適正 (HOLD)
    - EV/EBITDA > 15: 割高 (SELL)

    Args:
        financials: 財務データ
        prices: 株価データ
        code: 銘柄コード
        reference_date: 基準日

    Returns:
        {
            'ev_ebitda': float or None,
            'ev': float or None,
            'ebitda': float or None,
            'signal': 'BUY'/'HOLD'/'SELL'/None,
            'error': str or None
        }
    """
    if reference_date is None:
        reference_date = datetime.now()

    # 最新の財務データ取得
    latest_fin = get_latest_financials(financials, code, reference_date)

    if latest_fin is None or len(latest_fin) == 0:
        return {'ev_ebitda': None, 'ev': None, 'ebitda': None, 'signal': None, 'error': '財務データなし'}

    latest_fin = latest_fin.iloc[0]

    # 数値変換
    op = pd.to_numeric(latest_fin['OP'], errors='coerce')
    ta = pd.to_numeric(latest_fin['TA'], errors='coerce')
    eq = pd.to_numeric(latest_fin['Eq'], errors='coerce')
    cash_eq = pd.to_numeric(latest_fin['CashEq'], errors='coerce')

    if pd.isna(op) or pd.isna(ta) or pd.isna(eq):
        return {'ev_ebitda': None, 'ev': None, 'ebitda': None, 'signal': None, 'error': '必要な財務データ欠損'}

    if op <= 0:
        return {'ev_ebitda': None, 'ev': None, 'ebitda': None, 'signal': None, 'error': '営業利益マイナス'}

    # 時価総額取得
    latest_prices = get_price_history(prices, code, days=10)
    if len(latest_prices) == 0:
        return {'ev_ebitda': None, 'ev': None, 'ebitda': None, 'signal': None, 'error': '株価データなし'}

    latest_price = latest_prices.iloc[-1]
    market_cap = latest_price['Price'] * latest_price['Vo'] * 100

    # 純負債計算
    total_debt = ta - eq
    net_debt = total_debt - cash_eq if not pd.isna(cash_eq) else total_debt

    # EV計算
    ev = market_cap + net_debt

    # EBITDA ≈ 営業利益
    ebitda = op

    # EV/EBITDA計算
    ev_ebitda_ratio = ev / ebitda

    # シグナル判定
    if ev_ebitda_ratio < 10:
        signal = 'BUY'
    elif ev_ebitda_ratio <= 15:
        signal = 'HOLD'
    else:
        signal = 'SELL'

    # 理論株価計算（EV/EBITDA=10を適正とする）
    theoretical_ev = ebitda * 10
    theoretical_market_cap = theoretical_ev - net_debt
    shares_outstanding = latest_price['Vo'] * 100

    # 理論時価総額がマイナスの場合はNone
    if theoretical_market_cap <= 0 or shares_outstanding <= 0:
        theoretical_price = None
    else:
        theoretical_price = theoretical_market_cap / shares_outstanding

    current_price = latest_price['Price']

    return {
        'ev_ebitda': ev_ebitda_ratio,
        'ev': ev,
        'ebitda': ebitda,
        'theoretical_price': theoretical_price,
        'current_price': current_price,
        'signal': signal,
        'error': None
    }


def calculate_dcf_proxy(financials: pd.DataFrame, prices: pd.DataFrame, code: str, reference_date: Optional[datetime] = None, wacc: float = 0.10) -> Dict:
    """
    DCF Proxy計算（簡易版）

    理論企業価値 = FCF / WACC
    理論株価 = 理論企業価値 / 発行済株式数

    判定基準:
    - 現在株価 / 理論株価 < 0.8: 割安 (BUY)
    - 0.8-1.2: 適正 (HOLD)
    - > 1.2: 割高 (SELL)

    Args:
        financials: 財務データ
        prices: 株価データ
        code: 銘柄コード
        reference_date: 基準日
        wacc: 加重平均資本コスト（デフォルト10%）

    Returns:
        {
            'price_to_theoretical': float or None (現在株価/理論株価),
            'current_price': float or None,
            'theoretical_price': float or None,
            'fcf': float or None,
            'signal': 'BUY'/'HOLD'/'SELL'/None,
            'error': str or None
        }
    """
    if reference_date is None:
        reference_date = datetime.now()

    # 最新の財務データ取得
    latest_fin = get_latest_financials(financials, code, reference_date)

    if latest_fin is None or len(latest_fin) == 0:
        return {
            'price_to_theoretical': None,
            'current_price': None,
            'theoretical_price': None,
            'fcf': None,
            'signal': None,
            'error': '財務データなし'
        }

    latest_fin = latest_fin.iloc[0]

    # CFデータを数値に変換
    cfo = pd.to_numeric(latest_fin['CFO'], errors='coerce')
    cfi = pd.to_numeric(latest_fin['CFI'], errors='coerce')

    if pd.isna(cfo) or pd.isna(cfi):
        return {
            'price_to_theoretical': None,
            'current_price': None,
            'theoretical_price': None,
            'fcf': None,
            'signal': None,
            'error': 'キャッシュフローデータ欠損'
        }

    # FCF計算
    fcf = cfo - cfi

    if fcf <= 0:
        return {
            'price_to_theoretical': None,
            'current_price': None,
            'theoretical_price': None,
            'fcf': fcf,
            'signal': None,
            'error': 'FCFマイナス'
        }

    # 時価総額と株価取得
    latest_prices = get_price_history(prices, code, days=10)
    if len(latest_prices) == 0:
        return {
            'price_to_theoretical': None,
            'current_price': None,
            'theoretical_price': None,
            'fcf': fcf,
            'signal': None,
            'error': '株価データなし'
        }

    latest_price = latest_prices.iloc[-1]
    current_price = latest_price['Price']
    market_cap = current_price * latest_price['Vo'] * 100

    # 発行済株式数（簡易推定）
    shares_outstanding = latest_price['Vo'] * 100

    # 理論企業価値
    theoretical_ev = fcf / wacc

    # 理論株価
    theoretical_price = theoretical_ev / shares_outstanding

    # 現在株価 / 理論株価
    price_to_theoretical = current_price / theoretical_price

    # シグナル判定
    if price_to_theoretical < 0.8:
        signal = 'BUY'
    elif price_to_theoretical <= 1.2:
        signal = 'HOLD'
    else:
        signal = 'SELL'

    return {
        'price_to_theoretical': price_to_theoretical,
        'current_price': current_price,
        'theoretical_price': theoretical_price,
        'fcf': fcf,
        'signal': signal,
        'error': None
    }


def analyze_stock(code: str, reference_date: Optional[datetime] = None) -> Dict:
    """
    全バリュエーション分析を統合実行

    Args:
        code: 銘柄コード（5桁文字列）
        reference_date: 基準日（Noneの場合は現在日時）

    Returns:
        {
            'code': str,
            'peg_ratio': {...},
            'ma_divergence': {...},
            'ev_ebitda': {...},
            'dcf_proxy': {...},
            'overall_signal': 'BUY'/'HOLD'/'SELL'/None
        }
    """
    # データ読み込み
    try:
        prices, financials = load_jquants_data()
    except Exception as e:
        return {
            'code': code,
            'peg_ratio': {'error': f'データ読み込みエラー: {str(e)}'},
            'ma_divergence': {'error': f'データ読み込みエラー: {str(e)}'},
            'ev_ebitda': {'error': f'データ読み込みエラー: {str(e)}'},
            'dcf_proxy': {'error': f'データ読み込みエラー: {str(e)}'},
            'overall_signal': None
        }

    # 銘柄コードを5桁文字列に変換
    code_str = str(code).zfill(5)

    # 各分析実行
    peg = calculate_peg_ratio(financials, prices, code_str, reference_date)
    ma_div = calculate_ma_divergence(prices, code_str)
    ev_ebit = calculate_ev_ebitda(financials, prices, code_str, reference_date)
    dcf = calculate_dcf_proxy(financials, prices, code_str, reference_date)

    # 総合シグナル判定（多数決）
    signals = [
        peg.get('signal'),
        ma_div.get('signal'),
        ev_ebit.get('signal'),
        dcf.get('signal')
    ]

    # Noneを除外
    valid_signals = [s for s in signals if s is not None]

    if len(valid_signals) == 0:
        overall_signal = None
    else:
        # BUY/HOLD/SELLの数を集計
        buy_count = valid_signals.count('BUY')
        sell_count = valid_signals.count('SELL')
        hold_count = valid_signals.count('HOLD')

        # 多数決
        if buy_count > sell_count and buy_count >= hold_count:
            overall_signal = 'BUY'
        elif sell_count > buy_count and sell_count >= hold_count:
            overall_signal = 'SELL'
        else:
            overall_signal = 'HOLD'

    # 最小理論株価の特定と乖離率計算
    theoretical_prices = []
    current_price = None

    # PEGから理論株価
    if peg.get('theoretical_price') is not None and not peg.get('error'):
        theoretical_prices.append(('PEG', peg['theoretical_price']))
        if current_price is None:
            current_price = peg.get('current_price')

    # EV/EBITDAから理論株価
    if ev_ebit.get('theoretical_price') is not None and not ev_ebit.get('error'):
        theoretical_prices.append(('EV/EBITDA', ev_ebit['theoretical_price']))
        if current_price is None:
            current_price = ev_ebit.get('current_price')

    # DCFから理論株価
    if dcf.get('theoretical_price') is not None and not dcf.get('error'):
        theoretical_prices.append(('DCF', dcf['theoretical_price']))
        if current_price is None:
            current_price = dcf.get('current_price')

    # 最小理論株価（最も保守的）
    min_theoretical = None
    min_method = None
    divergence_from_min = None

    if len(theoretical_prices) > 0 and current_price is not None:
        # 正の理論株価のみ
        valid_theoretical = [(m, p) for m, p in theoretical_prices if p > 0]

        if len(valid_theoretical) > 0:
            min_method, min_theoretical = min(valid_theoretical, key=lambda x: x[1])
            # 乖離率（%）= (現在株価 - 最小理論株価) / 最小理論株価 × 100
            divergence_from_min = ((current_price - min_theoretical) / min_theoretical) * 100

    return {
        'code': code_str,
        'current_price': current_price,
        'theoretical_prices': {
            'peg': peg.get('theoretical_price'),
            'ev_ebitda': ev_ebit.get('theoretical_price'),
            'dcf': dcf.get('theoretical_price')
        },
        'min_theoretical_price': min_theoretical,
        'min_theoretical_method': min_method,
        'divergence_from_min': divergence_from_min,
        'peg_ratio': peg,
        'ma_divergence': ma_div,
        'ev_ebitda': ev_ebit,
        'dcf_proxy': dcf,
        'overall_signal': overall_signal
    }


if __name__ == "__main__":
    # テスト実行
    test_code = "7203"  # トヨタ自動車
    result = analyze_stock(test_code)

    print("=" * 80)
    print(f"銘柄コード: {result['code']}")
    print("=" * 80)

    print("\n【PEG Ratio】")
    print(f"  PEG: {result['peg_ratio'].get('peg_ratio')}")
    print(f"  PER: {result['peg_ratio'].get('per')}")
    print(f"  成長率: {result['peg_ratio'].get('growth_rate')}")
    print(f"  シグナル: {result['peg_ratio'].get('signal')}")
    print(f"  エラー: {result['peg_ratio'].get('error')}")

    print("\n【移動平均乖離】")
    print(f"  現在価格: {result['ma_divergence'].get('current_price')}")
    print(f"  25日MA: {result['ma_divergence'].get('ma_25')}")
    print(f"  75日MA: {result['ma_divergence'].get('ma_75')}")
    print(f"  乖離率（25日）: {result['ma_divergence'].get('divergence_25')}%")
    print(f"  シグナル: {result['ma_divergence'].get('signal')}")

    print("\n【EV/EBITDA】")
    print(f"  EV/EBITDA: {result['ev_ebitda'].get('ev_ebitda')}")
    print(f"  シグナル: {result['ev_ebitda'].get('signal')}")

    print("\n【DCF Proxy】")
    print(f"  株価/理論株価: {result['dcf_proxy'].get('price_to_theoretical')}")
    print(f"  現在株価: {result['dcf_proxy'].get('current_price')}")
    print(f"  理論株価: {result['dcf_proxy'].get('theoretical_price')}")
    print(f"  シグナル: {result['dcf_proxy'].get('signal')}")

    print("\n【総合判定】")
    print(f"  シグナル: {result['overall_signal']}")
