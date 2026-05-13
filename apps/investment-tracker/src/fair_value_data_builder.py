"""
J-Quants APIデータからFinancialDataモデルを構築するヘルパー

既存のvaluation_analysis_api.pyのデータ取得関数を活用します。
"""

import pandas as pd
from typing import Optional
from datetime import datetime
from src.fair_value_models import FinancialData
from src.valuation_analysis_api import (
    get_financials_from_api,
    get_price_data_from_api
)


def build_financial_data_from_api(client, code: str) -> Optional[FinancialData]:
    """
    J-Quants APIから財務データを取得してFinancialDataモデルを構築

    Args:
        client: JQuantsClient
        code: 銘柄コード（5桁）

    Returns:
        FinancialDataモデル、またはNone（データ取得失敗時）
    """
    try:
        # 銘柄情報取得
        company_info = client.get_company_info(code)
        company_name = company_info.get('CompanyName', f'銘柄{code}')

        # 財務データ取得
        financials = get_financials_from_api(client, code, debug=False)
        if financials is None or len(financials) == 0:
            print(f"[{code}] 財務データ取得失敗")
            return None

        # 株価データ取得
        prices = get_price_data_from_api(client, code, days=10)
        if prices is None or len(prices) == 0:
            print(f"[{code}] 株価データ取得失敗")
            return None

        current_price = prices.iloc[-1]['Price']

        # 損益データの抽出（複数期）
        sales = []
        operating_profit = []
        ordinary_profit = []
        net_profit = []
        eps_list = []
        fiscal_periods = []

        for _, row in financials.iterrows():
            # 売上高
            if 'Sales' in row:
                sales_val = pd.to_numeric(row['Sales'], errors='coerce')
                if pd.notna(sales_val):
                    sales.append(sales_val / 1_000_000)  # 百万円単位

            # 営業利益
            if 'OP' in row:
                op_val = pd.to_numeric(row['OP'], errors='coerce')
                if pd.notna(op_val):
                    operating_profit.append(op_val / 1_000_000)

            # 経常利益（TODO: 列名確認）
            ordinary_profit.append(0)  # 暫定

            # 純利益
            if 'NP' in row:
                np_val = pd.to_numeric(row['NP'], errors='coerce')
                if pd.notna(np_val):
                    net_profit.append(np_val / 1_000_000)

            # EPS
            if 'EPS' in row:
                eps_val = pd.to_numeric(row['EPS'], errors='coerce')
                if pd.notna(eps_val):
                    eps_list.append(eps_val)

            # 決算期
            if 'CurPerEn' in row:
                period = row['CurPerEn']
                fiscal_periods.append(str(period))

        # 最新財務データ（BS・CF）
        latest_fin = financials.iloc[-1]

        # BPS（1株当たり純資産）
        bps = pd.to_numeric(latest_fin.get('BPS'), errors='coerce') if 'BPS' in latest_fin else None

        # 自己資本
        equity = pd.to_numeric(latest_fin.get('Eq'), errors='coerce') if 'Eq' in latest_fin else None
        if pd.notna(equity):
            equity = equity / 1_000_000  # 百万円単位

        # 総資産
        total_assets = pd.to_numeric(latest_fin.get('TA'), errors='coerce') if 'TA' in latest_fin else None
        if pd.notna(total_assets):
            total_assets = total_assets / 1_000_000

        # 現預金
        cash = pd.to_numeric(latest_fin.get('CashEq'), errors='coerce') if 'CashEq' in latest_fin else None
        if pd.notna(cash):
            cash = cash / 1_000_000

        # 有利子負債（簡易計算: 総資産 - 自己資本 - 現預金）
        debt = None
        if pd.notna(total_assets) and pd.notna(equity) and pd.notna(cash):
            debt = total_assets - equity - cash

        # 営業CF
        operating_cf = pd.to_numeric(latest_fin.get('CFO'), errors='coerce') if 'CFO' in latest_fin else None
        if pd.notna(operating_cf):
            operating_cf = operating_cf / 1_000_000

        # 投資CF
        investing_cf = pd.to_numeric(latest_fin.get('CFI'), errors='coerce') if 'CFI' in latest_fin else None
        if pd.notna(investing_cf):
            investing_cf = investing_cf / 1_000_000

        # 配当金（TODO: 配当データ取得）
        dividend = None

        # ROE
        roe = pd.to_numeric(latest_fin.get('ROE'), errors='coerce') if 'ROE' in latest_fin else None

        # 発行済株式数
        shares_outstanding = None
        for field in ['NumberOfIssuedAndOutstandingSharesAtTheEndOfFiscalYearIncludingTreasuryStock',
                      'AverageNumberOfShares', 'IssuedShares']:
            if field in latest_fin:
                shares_val = pd.to_numeric(latest_fin.get(field), errors='coerce')
                if pd.notna(shares_val) and shares_val > 0:
                    shares_outstanding = shares_val
                    break

        # フォールバック: NP / EPS で推定
        if shares_outstanding is None or pd.isna(shares_outstanding):
            if len(net_profit) > 0 and len(eps_list) > 0:
                latest_np = net_profit[-1] * 1_000_000  # 円単位に戻す
                latest_eps = eps_list[-1]
                if latest_eps > 0:
                    shares_outstanding = latest_np / latest_eps

        # 時価総額
        market_cap = current_price * shares_outstanding / 1_000_000 if shares_outstanding else 0

        # 予想EPS（業績予想APIから取得）
        forecast_eps = None
        forecast_net_profit = None
        try:
            forecast_df = client.get_earnings_forecast(code)
            if len(forecast_df) > 0 and 'ForecastEPS' in forecast_df.columns:
                forecast_eps = pd.to_numeric(forecast_df.iloc[0].get('ForecastEPS'), errors='coerce')
                if pd.notna(forecast_eps) and forecast_eps > 0:
                    if shares_outstanding:
                        forecast_net_profit = forecast_eps * shares_outstanding / 1_000_000
        except Exception as e:
            print(f"[{code}] 予想データ取得エラー: {e}")

        # 過去マルチプルレンジ（TODO: 過去株価から計算）
        historical_per_min = None
        historical_per_max = None
        historical_pbr_min = None
        historical_pbr_max = None

        # FinancialDataモデル構築
        financial_data = FinancialData(
            code=code,
            company_name=company_name,
            current_price=current_price,
            shares_outstanding=shares_outstanding if shares_outstanding else 0,
            market_cap=market_cap,
            sales=sales,
            operating_profit=operating_profit,
            ordinary_profit=ordinary_profit,
            net_profit=net_profit,
            eps_list=eps_list,
            bps=bps,
            equity=equity,
            total_assets=total_assets,
            cash=cash,
            debt=debt,
            operating_cf=operating_cf,
            investing_cf=investing_cf,
            dividend=dividend,
            roe=roe,
            forecast_eps=forecast_eps,
            forecast_net_profit=forecast_net_profit,
            historical_per_min=historical_per_min,
            historical_per_max=historical_per_max,
            historical_pbr_min=historical_pbr_min,
            historical_pbr_max=historical_pbr_max,
            fiscal_periods=fiscal_periods
        )

        return financial_data

    except Exception as e:
        print(f"[{code}] FinancialData構築エラー: {e}")
        import traceback
        traceback.print_exc()
        return None
