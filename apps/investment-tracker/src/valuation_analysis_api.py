"""
持ち株バリュエーション分析モジュール（API版）

J-Quants API V2から直接データを取得
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple


def get_price_data_from_api(client, code: str, days: int = 100) -> pd.DataFrame:
    """
    J-Quants API V2から株価データを取得

    Args:
        client: JQuantsClient
        code: 銘柄コード（5桁文字列）
        days: 取得日数

    Returns:
        株価データ（DataFrame）
    """
    # 終了日：今日
    end_date = datetime.now()
    # 開始日：今日から指定日数前
    start_date = end_date - timedelta(days=days + 30)  # バッファ含む

    try:
        # J-Quants API V2: /equities/bars/daily
        df = client.get_daily_quotes(
            code=code,
            from_date=start_date.strftime('%Y-%m-%d'),
            to_date=end_date.strftime('%Y-%m-%d')
        )

        if df is None or len(df) == 0:
            return pd.DataFrame()

        # 日付列は既に変換済み
        if 'Date' not in df.columns and 'date' in df.columns:
            df['Date'] = pd.to_datetime(df['date'])

        # 調整済み株価の正しい計算（CRITICAL）
        if 'AdjustmentFactor' in df.columns:
            df['AdjFactor'] = df['AdjustmentFactor']
        elif 'AdjustmentClose' in df.columns and 'Close' in df.columns:
            # AdjustmentClose / Close = AdjFactor
            df['AdjFactor'] = df['AdjustmentClose'] / df['Close']
        elif 'AdjFactor' in df.columns:
            pass  # 既にある
        else:
            df['AdjFactor'] = 1.0

        # 終値
        if 'Close' in df.columns:
            df['C'] = df['Close']
        elif 'close' in df.columns:
            df['C'] = df['close']

        # 始値
        if 'Open' in df.columns:
            df['O'] = df['Open']
        elif 'open' in df.columns:
            df['O'] = df['open']

        # 出来高
        if 'Volume' in df.columns:
            df['Vo'] = df['Volume']
        elif 'volume' in df.columns:
            df['Vo'] = df['volume']

        df['Price'] = df['C'] * df['AdjFactor']

        return df.sort_values('Date')

    except Exception as e:
        print(f"株価データ取得エラー（{code}）: {e}")
        return pd.DataFrame()


def get_financials_from_api(client, code: str, debug: bool = False) -> pd.DataFrame:
    """
    J-Quants API V2から財務データを取得

    Args:
        client: JQuantsClient
        code: 銘柄コード（5桁文字列）
        debug: デバッグモード

    Returns:
        財務データ（DataFrame）
    """
    try:
        # J-Quants API V2: /fins/summary（直近5件のみ）
        # 成長率計算には最低5期必要なので、limitを増やす
        df = client.get_financial_statements(code=code, limit=10)

        if df is None or len(df) == 0:
            if debug:
                print(f"[{code}] 財務データなし")
            return pd.DataFrame()

        if debug:
            print(f"[{code}] 取得列: {df.columns.tolist()}")
            print(f"[{code}] 取得件数: {len(df)}")

        # 列名の標準化（J-Quants API V2の実際の列名に対応）
        # 日付列
        if 'DisclosedDate' in df.columns:
            df['DiscDate'] = pd.to_datetime(df['DisclosedDate'])
        elif 'disclosed_date' in df.columns:
            df['DiscDate'] = pd.to_datetime(df['disclosed_date'])
        elif 'DisclosureDate' in df.columns:
            df['DiscDate'] = pd.to_datetime(df['DisclosureDate'])

        if 'CurrentPeriodEndDate' in df.columns:
            df['CurPerEn'] = pd.to_datetime(df['CurrentPeriodEndDate'])
        elif 'current_period_end_date' in df.columns:
            df['CurPerEn'] = pd.to_datetime(df['current_period_end_date'])
        elif 'FiscalPeriodEnd' in df.columns:
            df['CurPerEn'] = pd.to_datetime(df['FiscalPeriodEnd'])

        # 財務データの列名を標準化（複数のパターンに対応）
        column_mapping = {
            # 純利益
            'NetProfit': 'NP',
            'net_profit': 'NP',
            'Profit': 'NP',
            # 営業利益
            'OperatingProfit': 'OP',
            'operating_profit': 'OP',
            # 総資産
            'TotalAssets': 'TA',
            'total_assets': 'TA',
            'Assets': 'TA',
            # 自己資本
            'Equity': 'Eq',
            'equity': 'Eq',
            'NetAssets': 'Eq',
            # 現金
            'CashAndEquivalents': 'CashEq',
            'cash_and_equivalents': 'CashEq',
            'CashAndDeposits': 'CashEq',
            # 営業CF
            'OperatingCashFlow': 'CFO',
            'operating_cash_flow': 'CFO',
            'CashFlowsFromOperatingActivities': 'CFO',
            # 投資CF
            'InvestingCashFlow': 'CFI',
            'investing_cash_flow': 'CFI',
            'CashFlowsFromInvestingActivities': 'CFI',
        }

        for old_col, new_col in column_mapping.items():
            if old_col in df.columns and new_col not in df.columns:
                df[new_col] = df[old_col]

        if debug:
            print(f"[{code}] マッピング後の列: {df.columns.tolist()}")
            if 'NP' in df.columns:
                print(f"[{code}] NP値: {df['NP'].tolist()}")

        # ソート（決算期順）
        if 'CurPerEn' in df.columns:
            return df.sort_values('CurPerEn')
        else:
            return df

    except Exception as e:
        print(f"財務データ取得エラー（{code}）: {e}")
        return pd.DataFrame()


def calculate_peg_ratio(client, code: str, reference_date: Optional[datetime] = None) -> Dict:
    """
    PEG Ratio計算（API版）
    """
    if reference_date is None:
        reference_date = datetime.now()

    # 財務データ取得
    financials = get_financials_from_api(client, code)

    if len(financials) == 0:
        return {'peg_ratio': None, 'per': None, 'growth_rate': None, 'theoretical_price': None, 'current_price': None, 'signal': None, 'error': '財務データなし'}

    # 基準日より前のデータのみ
    financials = financials[financials['DiscDate'] <= reference_date]

    # 純利益を数値に変換
    financials['NP'] = pd.to_numeric(financials['NP'], errors='coerce')
    financials = financials[financials['NP'].notna() & (financials['NP'] > 0)]

    if len(financials) < 2:
        return {'peg_ratio': None, 'per': None, 'growth_rate': None, 'theoretical_price': None, 'current_price': None, 'signal': None, 'error': '純利益データ不足'}

    # 最新5期分
    recent = financials.tail(5)
    np_values = recent['NP'].values

    # 成長率計算（CAGR）
    if len(np_values) >= 2:
        years = len(np_values) - 1
        try:
            growth_rate = (np_values[-1] / np_values[0]) ** (1 / years) - 1
        except:
            return {'peg_ratio': None, 'per': None, 'growth_rate': None, 'theoretical_price': None, 'current_price': None, 'signal': None, 'error': '成長率計算エラー'}
    else:
        return {'peg_ratio': None, 'per': None, 'growth_rate': None, 'theoretical_price': None, 'current_price': None, 'signal': None, 'error': '成長率計算に必要なデータ不足'}

    # 株価データ取得
    prices = get_price_data_from_api(client, code, days=10)
    if len(prices) == 0:
        return {'peg_ratio': None, 'per': None, 'growth_rate': None, 'theoretical_price': None, 'current_price': None, 'signal': None, 'error': '株価データなし'}

    latest_price = prices.iloc[-1]
    market_cap = latest_price['Price'] * latest_price['Vo'] * 100

    # PER計算
    latest_np = np_values[-1]
    per = market_cap / latest_np

    # PEG計算
    if growth_rate <= 0:
        return {'peg_ratio': None, 'per': per, 'growth_rate': growth_rate, 'theoretical_price': None, 'current_price': latest_price['Price'], 'signal': 'SELL', 'error': '成長率マイナス'}

    peg_ratio = per / (growth_rate * 100)

    # シグナル判定
    if peg_ratio < 1.0:
        signal = 'BUY'
    elif peg_ratio <= 2.0:
        signal = 'HOLD'
    else:
        signal = 'SELL'

    # 理論株価計算（PEG=1.0を適正とする）
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


def calculate_ma_divergence(client, code: str) -> Dict:
    """
    移動平均乖離率計算（API版）
    """
    # 100日分の株価取得
    prices = get_price_data_from_api(client, code, days=100)

    if len(prices) < 75:
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
    prices['MA_25'] = prices['Price'].rolling(window=25).mean()
    prices['MA_75'] = prices['Price'].rolling(window=75).mean()

    # 最新データ
    latest = prices.iloc[-1]
    current_price = latest['Price']
    ma_25 = latest['MA_25']
    ma_75 = latest['MA_75']

    # 乖離率計算
    divergence_25 = ((current_price - ma_25) / ma_25) * 100
    divergence_75 = ((current_price - ma_75) / ma_75) * 100

    # ゴールデンクロス/デッドクロス判定
    if len(prices) >= 2:
        prev = prices.iloc[-2]
        prev_ma_25 = prev['MA_25']
        prev_ma_75 = prev['MA_75']

        # ゴールデンクロス
        if prev_ma_25 < prev_ma_75 and ma_25 > ma_75:
            signal = 'BUY'
        # デッドクロス
        elif prev_ma_25 > prev_ma_75 and ma_25 < ma_75:
            signal = 'SELL'
        # 現在価格が両方のMAより上
        elif current_price > ma_25 and current_price > ma_75:
            signal = 'HOLD'
        # 現在価格が両方のMAより下
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


def calculate_ev_ebitda(client, code: str, reference_date: Optional[datetime] = None) -> Dict:
    """
    EV/EBITDA計算（API版、簡易版）
    """
    if reference_date is None:
        reference_date = datetime.now()

    # 財務データ取得
    financials = get_financials_from_api(client, code)

    if len(financials) == 0:
        return {'ev_ebitda': None, 'ev': None, 'ebitda': None, 'theoretical_price': None, 'current_price': None, 'signal': None, 'error': '財務データなし'}

    # 基準日より前のデータのみ
    financials = financials[financials['DiscDate'] <= reference_date]

    if len(financials) == 0:
        return {'ev_ebitda': None, 'ev': None, 'ebitda': None, 'theoretical_price': None, 'current_price': None, 'signal': None, 'error': '財務データなし'}

    latest_fin = financials.iloc[-1]

    # 数値変換
    op = pd.to_numeric(latest_fin.get('OP'), errors='coerce')
    ta = pd.to_numeric(latest_fin.get('TA'), errors='coerce')
    eq = pd.to_numeric(latest_fin.get('Eq'), errors='coerce')
    cash_eq = pd.to_numeric(latest_fin.get('CashEq'), errors='coerce')

    if pd.isna(op) or pd.isna(ta) or pd.isna(eq):
        return {'ev_ebitda': None, 'ev': None, 'ebitda': None, 'theoretical_price': None, 'current_price': None, 'signal': None, 'error': '必要な財務データ欠損'}

    if op <= 0:
        return {'ev_ebitda': None, 'ev': None, 'ebitda': None, 'theoretical_price': None, 'current_price': None, 'signal': None, 'error': '営業利益マイナス'}

    # 株価データ取得
    prices = get_price_data_from_api(client, code, days=10)
    if len(prices) == 0:
        return {'ev_ebitda': None, 'ev': None, 'ebitda': None, 'theoretical_price': None, 'current_price': None, 'signal': None, 'error': '株価データなし'}

    latest_price = prices.iloc[-1]
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


def calculate_dcf_proxy(client, code: str, reference_date: Optional[datetime] = None, wacc: float = 0.10) -> Dict:
    """
    DCF Proxy計算（API版、簡易版）
    """
    if reference_date is None:
        reference_date = datetime.now()

    # 財務データ取得
    financials = get_financials_from_api(client, code)

    if len(financials) == 0:
        return {
            'price_to_theoretical': None,
            'current_price': None,
            'theoretical_price': None,
            'fcf': None,
            'signal': None,
            'error': '財務データなし'
        }

    # 基準日より前のデータのみ
    financials = financials[financials['DiscDate'] <= reference_date]

    if len(financials) == 0:
        return {
            'price_to_theoretical': None,
            'current_price': None,
            'theoretical_price': None,
            'fcf': None,
            'signal': None,
            'error': '財務データなし'
        }

    latest_fin = financials.iloc[-1]

    # CFデータを数値に変換
    cfo = pd.to_numeric(latest_fin.get('CFO'), errors='coerce')
    cfi = pd.to_numeric(latest_fin.get('CFI'), errors='coerce')

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

    # 株価データ取得
    prices = get_price_data_from_api(client, code, days=10)
    if len(prices) == 0:
        return {
            'price_to_theoretical': None,
            'current_price': None,
            'theoretical_price': None,
            'fcf': fcf,
            'signal': None,
            'error': '株価データなし'
        }

    latest_price = prices.iloc[-1]
    current_price = latest_price['Price']

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


def analyze_stock(client, code: str, reference_date: Optional[datetime] = None) -> Dict:
    """
    全バリュエーション分析を統合実行（API版）

    Args:
        client: JQuantsClient
        code: 銘柄コード（5桁文字列）
        reference_date: 基準日（Noneの場合は現在日時）

    Returns:
        分析結果の辞書
    """
    # 銘柄コードを5桁文字列に変換
    code_str = str(code).zfill(5)

    # 各分析実行
    peg = calculate_peg_ratio(client, code_str, reference_date)
    ma_div = calculate_ma_divergence(client, code_str)
    ev_ebit = calculate_ev_ebitda(client, code_str, reference_date)
    dcf = calculate_dcf_proxy(client, code_str, reference_date)

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
