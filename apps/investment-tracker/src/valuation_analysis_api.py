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
        # 日付列（CRITICAL: 必ずdatetime型に変換）
        if 'DiscDate' in df.columns:
            # 既にDiscDate列がある場合（J-Quants API V2）
            df['DiscDate'] = pd.to_datetime(df['DiscDate'], errors='coerce')
        elif 'DisclosedDate' in df.columns:
            df['DiscDate'] = pd.to_datetime(df['DisclosedDate'], errors='coerce')
        elif 'disclosed_date' in df.columns:
            df['DiscDate'] = pd.to_datetime(df['disclosed_date'], errors='coerce')
        elif 'DisclosureDate' in df.columns:
            df['DiscDate'] = pd.to_datetime(df['DisclosureDate'], errors='coerce')

        if 'CurPerEn' in df.columns:
            # 既にCurPerEn列がある場合（J-Quants API V2）
            df['CurPerEn'] = pd.to_datetime(df['CurPerEn'], errors='coerce')
        elif 'CurrentPeriodEndDate' in df.columns:
            df['CurPerEn'] = pd.to_datetime(df['CurrentPeriodEndDate'], errors='coerce')
        elif 'current_period_end_date' in df.columns:
            df['CurPerEn'] = pd.to_datetime(df['current_period_end_date'], errors='coerce')
        elif 'FiscalPeriodEnd' in df.columns:
            df['CurPerEn'] = pd.to_datetime(df['FiscalPeriodEnd'], errors='coerce')

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

    予想EPSを優先的に使用し、なければ実績EPSを使用
    """
    if reference_date is None:
        reference_date = datetime.now()

    # 1. 業績予想データを取得（予想EPS）
    forecast = client.get_earnings_forecast(code)
    forecast_eps = None
    forecast_date = None

    if len(forecast) > 0 and 'ForecastEPS' in forecast.columns:
        # 最新の予想EPSを取得
        forecast_eps = pd.to_numeric(forecast.iloc[0].get('ForecastEPS'), errors='coerce')
        forecast_date = forecast.iloc[0].get('Date')
        if pd.notna(forecast_eps) and forecast_eps > 0:
            print(f"[{code}] 予想EPS使用: {forecast_eps:.2f}円 (発表日: {forecast_date})")

    # 2. 財務データ取得（実績EPS）
    financials = get_financials_from_api(client, code)

    if len(financials) == 0:
        return {'peg_ratio': None, 'per': None, 'growth_rate': None, 'theoretical_price': None, 'current_price': None, 'signal': None, 'error': '財務データなし'}

    # 基準日より前のデータのみ
    financials = financials[financials['DiscDate'] <= reference_date]

    # 純利益とEPSを数値に変換
    financials['NP'] = pd.to_numeric(financials['NP'], errors='coerce')
    financials['EPS'] = pd.to_numeric(financials['EPS'], errors='coerce')

    # EPSとNPの両方が必要
    financials = financials[
        financials['NP'].notna() & (financials['NP'] > 0) &
        financials['EPS'].notna() & (financials['EPS'] > 0)
    ]

    if len(financials) < 2:
        return {'peg_ratio': None, 'per': None, 'growth_rate': None, 'theoretical_price': None, 'current_price': None, 'signal': None, 'error': '純利益データ不足'}

    # 最新5期分
    recent = financials.tail(5)
    np_values = recent['NP'].values
    eps_values = recent['EPS'].values

    # 成長率計算（CAGR） - 純利益ベース
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
    current_price = latest_price['Price']

    # PER計算（CRITICAL: 株価 / EPS が正しい計算方法）
    # 予想EPSを優先、なければ実績EPS
    if forecast_eps is not None:
        latest_eps = forecast_eps
        eps_type = "予想"
        fiscal_period = forecast_date
        disc_date = forecast_date
    else:
        latest_eps = eps_values[-1]
        eps_type = "実績"
        # 最新の決算期情報を取得
        latest_fin = financials.iloc[-1]
        fiscal_period = latest_fin.get('CurPerEn', 'N/A')
        disc_date = latest_fin.get('DiscDate', 'N/A')

    per = current_price / latest_eps

    # デバッグ出力（全銘柄）
    print(f"[DEBUG PER {code}]")
    print(f"  株価: {current_price:.2f} 円")
    print(f"  EPS ({eps_type}): {latest_eps:.2f} 円")
    print(f"  PER: {per:.2f}")
    print(f"  NP最新: {np_values[-1]:,.0f}")
    print(f"  決算期: {fiscal_period}")
    print(f"  開示日: {disc_date}")

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
    # 理論PER = 成長率 × 100
    theoretical_per = growth_rate * 100
    # 理論株価 = EPS × 理論PER
    theoretical_price = latest_eps * theoretical_per

    return {
        'peg_ratio': peg_ratio,
        'per': per,
        'growth_rate': growth_rate,
        'theoretical_price': theoretical_price,
        'current_price': current_price,
        'signal': signal,
        'error': None,
        'eps': latest_eps,
        'eps_type': eps_type,  # "予想" または "実績"
        'np_latest': np_values[-1],
        'fiscal_period': str(fiscal_period),
        'disc_date': str(disc_date)
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

    print(f"[DEBUG EV/EBITDA {code}] 財務データ取得件数: {len(financials)}, 列: {financials.columns.tolist() if len(financials) > 0 else 'N/A'}")

    if len(financials) == 0:
        return {'ev_ebitda': None, 'ev': None, 'ebitda': None, 'theoretical_price': None, 'current_price': None, 'signal': None, 'error': '財務データなし', 'shares_outstanding': 0, 'np': 0, 'eps': 0, 'net_debt': 0, 'market_cap': 0, 'op_x10': 0, 'op_divergence': 0}

    # 基準日より前のデータのみ
    financials = financials[financials['DiscDate'] <= reference_date]

    print(f"[DEBUG EV/EBITDA {code}] reference_date={reference_date}, フィルタ後件数: {len(financials)}")

    if len(financials) == 0:
        return {'ev_ebitda': None, 'ev': None, 'ebitda': None, 'theoretical_price': None, 'current_price': None, 'signal': None, 'error': '財務データなし（基準日フィルタ後）', 'shares_outstanding': 0, 'np': 0, 'eps': 0, 'net_debt': 0, 'market_cap': 0, 'op_x10': 0, 'op_divergence': 0}

    latest_fin = financials.iloc[-1]

    # 数値変換
    op = pd.to_numeric(latest_fin.get('OP'), errors='coerce')
    ta = pd.to_numeric(latest_fin.get('TA'), errors='coerce')
    eq = pd.to_numeric(latest_fin.get('Eq'), errors='coerce')
    cash_eq = pd.to_numeric(latest_fin.get('CashEq'), errors='coerce')

    # デバッグ：財務データの値を確認（単位検証）
    print(f"[DEBUG {code}] 財務データ: Sales={latest_fin.get('Sales')}, OP={op}, NP={latest_fin.get('NP')}, TA={ta}")

    if pd.isna(op) or pd.isna(ta) or pd.isna(eq):
        return {'ev_ebitda': None, 'ev': None, 'ebitda': None, 'theoretical_price': None, 'current_price': None, 'signal': None, 'error': '必要な財務データ欠損'}

    if op <= 0:
        return {'ev_ebitda': None, 'ev': None, 'ebitda': None, 'theoretical_price': None, 'current_price': None, 'signal': None, 'error': '営業利益マイナス'}

    # 株価データ取得
    prices = get_price_data_from_api(client, code, days=10)
    if len(prices) == 0:
        return {'ev_ebitda': None, 'ev': None, 'ebitda': None, 'theoretical_price': None, 'current_price': None, 'signal': None, 'error': '株価データなし'}

    latest_price = prices.iloc[-1]
    current_price = latest_price['Price']

    # 時価総額計算（CRITICAL: 純利益とEPSから発行済株式数を推定）
    np_raw = latest_fin.get('NP')
    eps_raw = latest_fin.get('EPS')
    np = pd.to_numeric(np_raw, errors='coerce')  # 円単位（J-Quants APIは円で返す）
    eps = pd.to_numeric(eps_raw, errors='coerce')  # 円単位

    # デバッグ出力（生データと変換後を両方表示）
    if code == "41770":  # 問題の銘柄のみ詳細出力
        print(f"[DEBUG EV/EBITDA {code}] NP_raw: {np_raw} (型: {type(np_raw).__name__}), NP変換後: {np}")
        print(f"[DEBUG EV/EBITDA {code}] EPS_raw: {eps_raw} (型: {type(eps_raw).__name__}), EPS変換後: {eps}")
        print(f"[DEBUG EV/EBITDA {code}] OP: {op}, TA: {ta}, Eq: {eq}")
        if hasattr(latest_fin, 'to_dict'):
            fin_dict = latest_fin.to_dict()
            print(f"[DEBUG EV/EBITDA {code}] 財務データ抜粋: NP={fin_dict.get('NP')}, Sales={fin_dict.get('Sales')}, OP={fin_dict.get('OP')}")

    # データ検証：異常値チェック
    if pd.isna(np) or pd.isna(eps) or eps <= 0 or np <= 0:
        return {'ev_ebitda': None, 'ev': None, 'ebitda': None, 'theoretical_price': None, 'current_price': None, 'signal': None, 'error': 'EPS/NPデータ欠損', 'shares_outstanding': 0, 'np': 0, 'eps': 0, 'net_debt': 0, 'market_cap': 0, 'op_x10': 0, 'op_divergence': 0}

    # 異常値検出：NPが1京円を超える場合（念のため）
    if np > 10_000_000_000_000_000:  # 1京円
        print(f"[WARNING {code}] NP異常値検出: {np:,.0f}円（1京円以上）")
        return {'ev_ebitda': None, 'ev': None, 'ebitda': None, 'theoretical_price': None, 'current_price': None, 'signal': None, 'error': f'NP異常値（{np/100_000_000:,.0f}億円）', 'shares_outstanding': 0, 'np': np, 'eps': eps, 'net_debt': 0, 'market_cap': 0, 'op_x10': 0, 'op_divergence': 0}

    # 発行済株式数 = 純利益（円） / EPS（円/株）
    shares_outstanding = np / eps
    # 時価総額（円単位）
    market_cap_yen = current_price * shares_outstanding
    # 時価総額（百万円単位に変換）
    market_cap = market_cap_yen / 1_000_000

    # 純負債計算（円→百万円に変換）
    total_debt = (ta - eq) / 1_000_000
    net_debt = (total_debt - cash_eq / 1_000_000) if not pd.isna(cash_eq) else total_debt

    # EV計算（百万円単位）
    ev = market_cap + net_debt

    # EBITDA ≈ 営業利益（円→百万円に変換）
    ebitda = op / 1_000_000

    # EV/EBITDA計算
    ev_ebitda_ratio = ev / ebitda

    # 営業利益×10との乖離計算（簡易バリュエーション指標）
    op_x10 = ebitda * 10  # 百万円単位
    op_divergence = ((market_cap - op_x10) / op_x10) * 100  # %

    # デバッグ出力
    if code == "41770":
        print(f"[DEBUG EV/EBITDA 41770]")
        print(f"  current_price: {current_price:.2f} 円")
        print(f"  shares_outstanding: {shares_outstanding:,.0f} 株")
        print(f"  market_cap_yen: {current_price * shares_outstanding:,.0f} 円")
        print(f"  market_cap: {market_cap:.2f} 百万円")
        print(f"  TA: {ta:.2f} 百万円")
        print(f"  Eq: {eq:.2f} 百万円")
        print(f"  CashEq: {cash_eq:.2f} 百万円")
        print(f"  net_debt: {net_debt:.2f} 百万円")
        print(f"  ev: {ev:.2f} 百万円")
        print(f"  ebitda (OP): {ebitda:.2f} 百万円")
        print(f"  ev_ebitda_ratio: {ev_ebitda_ratio:.2f}")

    # シグナル判定
    if ev_ebitda_ratio < 10:
        signal = 'BUY'
    elif ev_ebitda_ratio <= 15:
        signal = 'HOLD'
    else:
        signal = 'SELL'

    # 理論株価計算（EV/EBITDA=10を適正とする）
    theoretical_ev = ebitda * 10  # 百万円単位
    theoretical_market_cap = theoretical_ev - net_debt  # 百万円単位

    # 理論時価総額がマイナスの場合はNone
    if theoretical_market_cap <= 0 or shares_outstanding <= 0:
        theoretical_price = None
    else:
        # 理論株価（円単位） = 理論時価総額（百万円→円） / 発行済株式数
        theoretical_price = (theoretical_market_cap * 1_000_000) / shares_outstanding

    return {
        'ev_ebitda': ev_ebitda_ratio,
        'ev': ev,
        'ebitda': ebitda,
        'theoretical_price': theoretical_price,
        'current_price': current_price,
        'signal': signal,
        'error': None,
        'market_cap': market_cap,  # 時価総額（百万円）
        'op_x10': op_x10,  # 営業利益×10（百万円）
        'op_divergence': op_divergence,  # 営業利益×10との乖離率（%）
        # デバッグ情報
        'shares_outstanding': shares_outstanding,
        'np': np,
        'eps': eps,
        'net_debt': net_debt
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

    # CFデータを数値に変換（円単位→百万円単位）
    cfo = pd.to_numeric(latest_fin.get('CFO'), errors='coerce') / 1_000_000
    cfi = pd.to_numeric(latest_fin.get('CFI'), errors='coerce') / 1_000_000

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

    # 発行済株式数（NP/EPSから計算）
    np = pd.to_numeric(latest_fin.get('NP'), errors='coerce')  # 円単位
    eps = pd.to_numeric(latest_fin.get('EPS'), errors='coerce')  # 円単位

    if pd.isna(np) or pd.isna(eps) or eps <= 0:
        return {
            'price_to_theoretical': None,
            'current_price': None,
            'theoretical_price': None,
            'fcf': fcf,
            'signal': None,
            'error': 'EPS/NPデータ欠損'
        }

    # 発行済株式数 = 純利益（円） / EPS（円/株）
    shares_outstanding = np / eps

    # 理論企業価値（百万円単位）
    theoretical_ev = fcf / wacc

    # 理論株価（円単位） = 理論企業価値（百万円→円） / 発行済株式数
    theoretical_price = (theoretical_ev * 1_000_000) / shares_outstanding

    # デバッグ出力
    if code == "41770":
        print(f"[DEBUG DCF 41770]")
        print(f"  FCF: {fcf:.2f} 百万円")
        print(f"  WACC: {wacc:.2%}")
        print(f"  theoretical_ev: {theoretical_ev:.2f} 百万円")
        print(f"  NP: {np:.2f} 百万円")
        print(f"  EPS: {eps:.2f} 円")
        print(f"  shares_outstanding: {shares_outstanding:,.0f} 株")
        print(f"  current_price: {current_price:.2f} 円")
        print(f"  theoretical_price: {theoretical_price:.2f} 円")

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

    # 銘柄情報を取得
    try:
        company_info = client.get_company_info(code_str)
        company_name = company_info.get('CompanyName', f'銘柄{code_str}')
    except Exception as e:
        print(f"銘柄情報取得エラー（{code_str}）: {e}")
        company_name = f'銘柄{code_str}'

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
        'company_name': company_name,
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
