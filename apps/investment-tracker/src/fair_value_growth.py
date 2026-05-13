"""
グロース株向け適正株価算出エンジン

PEGレシオベースでグロース株の適正株価を算出します。
"""

import numpy as np
from typing import List, Optional, Tuple
from src.fair_value_models import (
    FinancialData,
    GrowthRateAnalysis,
    GrowthQuality,
    PEGRatioAnalysis,
    PERAnalysis,
    GrowthFairValue
)
from src.fair_value_constants import (
    get_growth_band,
    get_peg_range,
    GROWTH_QUALITY_THRESHOLDS,
    PER_HISTORICAL_CAP_PREMIUM,
    PER_PEER_DIVERGENCE_MAX,
    VALUATION_THRESHOLDS,
    MIN_PERIODS_FOR_CAGR,
    OUTLIER_THRESHOLD_YOY
)


# ========================================
# 1. EPS成長率の算出
# ========================================

def calculate_cagr(values: List[float], exclude_indices: List[int] = None) -> float:
    """
    CAGR（年平均成長率）を計算

    Args:
        values: 数値リスト（古い順）
        exclude_indices: 除外するインデックスのリスト

    Returns:
        CAGR（小数、例: 0.15 = 15%）
    """
    if exclude_indices is None:
        exclude_indices = []

    # 除外後のデータ
    filtered = [v for i, v in enumerate(values) if i not in exclude_indices and v > 0]

    if len(filtered) < MIN_PERIODS_FOR_CAGR:
        return 0.0

    first_val = filtered[0]
    last_val = filtered[-1]
    periods = len(filtered) - 1

    if first_val <= 0 or last_val <= 0:
        return 0.0

    try:
        cagr = (last_val / first_val) ** (1 / periods) - 1
        return cagr
    except (ZeroDivisionError, ValueError):
        return 0.0


def detect_outliers(values: List[float]) -> List[int]:
    """
    異常値を検出

    前年比が異常に大きい/小さい年を検出します。

    Args:
        values: 数値リスト（古い順）

    Returns:
        異常値のインデックスリスト
    """
    outliers = []

    for i in range(1, len(values)):
        if values[i - 1] <= 0 or values[i] <= 0:
            continue

        yoy_ratio = values[i] / values[i - 1]

        # 前年比が3倍以上、または1/3以下
        if yoy_ratio > OUTLIER_THRESHOLD_YOY or yoy_ratio < (1 / OUTLIER_THRESHOLD_YOY):
            outliers.append(i)

    return outliers


def analyze_growth_rate(data: FinancialData) -> GrowthRateAnalysis:
    """
    EPS成長率を分析

    Args:
        data: 財務データ

    Returns:
        成長率分析結果
    """
    eps_list = data.eps_list
    reasons = []

    # 異常値検出
    outliers = detect_outliers(eps_list)
    if outliers:
        reasons.append(f"異常値年を検出: {outliers}")

    # 過去CAGR（異常値除外版）
    historical_cagr = calculate_cagr(eps_list, exclude_indices=outliers)
    reasons.append(f"過去CAGR: {historical_cagr*100:.1f}%（{len(eps_list)}期、異常値{len(outliers)}年除外）")

    # 予想成長率（予想EPSがある場合）
    forecast_growth = None
    if data.forecast_eps and len(eps_list) > 0:
        latest_eps = eps_list[-1]
        if latest_eps > 0:
            forecast_growth = (data.forecast_eps / latest_eps) - 1
            reasons.append(f"予想成長率: {forecast_growth*100:.1f}%（予想EPS: {data.forecast_eps:.2f}）")

    # 採用成長率の決定
    # ルール: 予想成長率を優先、なければ過去CAGR
    if forecast_growth is not None and forecast_growth > 0:
        adopted_growth = forecast_growth
        reasons.append(f"✅ 採用: 予想成長率 {adopted_growth*100:.1f}%")
    elif historical_cagr > 0:
        adopted_growth = historical_cagr
        reasons.append(f"✅ 採用: 過去CAGR {adopted_growth*100:.1f}%（予想データなし）")
    else:
        # マイナス成長またはデータ不足
        adopted_growth = 0.05  # デフォルト5%
        reasons.append(f"⚠️ 成長率がマイナスまたは計算不可。デフォルト{adopted_growth*100:.0f}%を採用")

    # 成長率帯の判定
    growth_band = get_growth_band(adopted_growth * 100)

    return GrowthRateAnalysis(
        historical_cagr=historical_cagr,
        forecast_growth=forecast_growth,
        adopted_growth=adopted_growth,
        growth_band=growth_band,
        reasons=reasons,
        excluded_years=outliers
    )


# ========================================
# 2. 成長の質評価
# ========================================

def evaluate_growth_quality(data: FinancialData, growth_analysis: GrowthRateAnalysis) -> GrowthQuality:
    """
    成長の質を評価

    Args:
        data: 財務データ
        growth_analysis: 成長率分析結果

    Returns:
        成長品質評価
    """
    reasons = []
    score = 0  # スコアリング（0～4点）

    # (1) 売上も成長しているか
    sales_growing = False
    if len(data.sales) >= 2:
        sales_cagr = calculate_cagr(data.sales)
        if sales_cagr >= GROWTH_QUALITY_THRESHOLDS['sales_growth_min']:
            sales_growing = True
            score += 1
            reasons.append(f"✅ 売上成長率: {sales_cagr*100:.1f}%（基準{GROWTH_QUALITY_THRESHOLDS['sales_growth_min']*100:.0f}%以上）")
        else:
            reasons.append(f"⚠️ 売上成長率: {sales_cagr*100:.1f}%（基準未達）")
    else:
        reasons.append("⚠️ 売上データ不足")

    # (2) 利益率が改善しているか
    margin_improving = False
    if len(data.operating_profit) >= 2 and len(data.sales) >= 2:
        # 最新と2期前の営業利益率を比較
        if data.sales[-1] > 0 and data.sales[0] > 0:
            margin_latest = data.operating_profit[-1] / data.sales[-1]
            margin_first = data.operating_profit[0] / data.sales[0]
            margin_change = margin_latest - margin_first

            if margin_change >= GROWTH_QUALITY_THRESHOLDS['margin_improvement_min']:
                margin_improving = True
                score += 1
                reasons.append(f"✅ 営業利益率改善: {margin_change*100:.1f}%ポイント")
            else:
                reasons.append(f"⚠️ 営業利益率変化: {margin_change*100:.1f}%ポイント（改善不十分）")
    else:
        reasons.append("⚠️ 利益率計算データ不足")

    # (3) 一時要因依存ではないか（異常値年が少ない）
    one_time_dependent = len(growth_analysis.excluded_years) > len(data.eps_list) // 2
    if not one_time_dependent:
        score += 1
        reasons.append("✅ 一時要因依存なし（異常値年が少ない）")
    else:
        reasons.append("⚠️ 一時要因に依存する可能性（異常値年が多い）")

    # (4) ビジネスモデルの継続性（簡易判定: EPSの標準偏差/平均が小さい）
    sustainable = False
    if len(data.eps_list) >= 3:
        eps_mean = np.mean(data.eps_list)
        eps_std = np.std(data.eps_list)
        if eps_mean > 0:
            cv = eps_std / eps_mean  # 変動係数
            if cv < 0.5:  # 変動係数50%未満で安定
                sustainable = True
                score += 1
                reasons.append(f"✅ EPS安定性高い（変動係数{cv:.2f}）")
            else:
                reasons.append(f"⚠️ EPSのブレが大きい（変動係数{cv:.2f}）")
    else:
        reasons.append("⚠️ 継続性判定データ不足")

    # 総合評価（4点満点）
    if score >= 3:
        rank = 'high'
    elif score >= 2:
        rank = 'medium'
    else:
        rank = 'low'

    reasons.append(f"📊 成長品質スコア: {score}/4 → ランク: {rank.upper()}")

    return GrowthQuality(
        rank=rank,
        sales_growing=sales_growing,
        margin_improving=margin_improving,
        one_time_dependent=one_time_dependent,
        sustainable=sustainable,
        reasons=reasons
    )


# ========================================
# 3. PEGレシオ決定
# ========================================

def determine_peg_ratio(growth_analysis: GrowthRateAnalysis, quality: GrowthQuality) -> PEGRatioAnalysis:
    """
    PEGレシオを決定

    Args:
        growth_analysis: 成長率分析
        quality: 成長品質評価

    Returns:
        PEGレシオ分析
    """
    growth_band = growth_analysis.growth_band
    quality_rank = quality.rank

    # PEGレンジ取得
    peg_min, peg_max = get_peg_range(growth_band, quality_rank)

    # 採用PEG（デフォルトはレンジ中央値）
    adopted_peg = (peg_min + peg_max) / 2

    reasons = [
        f"成長率帯: {growth_band.upper()}（{growth_analysis.adopted_growth*100:.1f}%）",
        f"成長品質: {quality_rank.upper()}",
        f"PEGレンジ: {peg_min:.2f} ～ {peg_max:.2f}",
        f"✅ 採用PEG: {adopted_peg:.2f}（レンジ中央値）"
    ]

    return PEGRatioAnalysis(
        theoretical_peg=adopted_peg,
        peg_range_min=peg_min,
        peg_range_max=peg_max,
        adopted_peg=adopted_peg,
        reasons=reasons
    )


# ========================================
# 4. 適正PER算出
# ========================================

def calculate_theoretical_per(
    growth_rate: float,
    peg: float,
    data: FinancialData
) -> PERAnalysis:
    """
    適正PERを算出

    Args:
        growth_rate: 採用成長率（小数）
        peg: 採用PEG
        data: 財務データ

    Returns:
        PER分析
    """
    # 理論PER = PEG × 成長率（%値）
    theoretical_per = peg * (growth_rate * 100)

    adjustment_reasons = []

    # 調整前の理論PERを記録
    adjustment_reasons.append(f"理論PER = PEG {peg:.2f} × 成長率 {growth_rate*100:.1f}% = {theoretical_per:.1f}")

    # 調整後PER（初期値は理論PER）
    adjusted_per = theoretical_per

    # (1) 過去PERレンジ上限チェック
    if data.historical_per_max:
        historical_cap = data.historical_per_max * (1 + PER_HISTORICAL_CAP_PREMIUM)
        if adjusted_per > historical_cap:
            old_per = adjusted_per
            adjusted_per = historical_cap
            adjustment_reasons.append(
                f"⚠️ 過去PER上限調整: {old_per:.1f} → {adjusted_per:.1f}"
                f"（過去上限{data.historical_per_max:.1f} + {PER_HISTORICAL_CAP_PREMIUM*100:.0f}%）"
            )

    # (2) 同業PER平均との乖離チェック（TODO: 同業データ取得後に実装）
    # 現時点では省略

    # 最終PER
    if adjusted_per == theoretical_per:
        adjustment_reasons.append("✅ 調整なし（理論PERをそのまま採用）")
    else:
        adjustment_reasons.append(f"✅ 最終採用PER: {adjusted_per:.1f}")

    return PERAnalysis(
        theoretical_per=theoretical_per,
        adjusted_per=adjusted_per,
        adjustment_reasons=adjustment_reasons,
        historical_per_cap=data.historical_per_max,
        peer_per_avg=None  # TODO: 同業データ
    )


# ========================================
# 5. 株価レンジ算出
# ========================================

def calculate_price_range(
    per: float,
    data: FinancialData,
    growth_rate: float
) -> Tuple[float, float, float]:
    """
    適正株価レンジを算出（保守・中央・強気）

    Args:
        per: 採用PER
        data: 財務データ
        growth_rate: 採用成長率

    Returns:
        (保守ケース, 中央ケース, 強気ケース)
    """
    # 今期EPS
    current_eps = data.eps_list[-1] if data.eps_list else 0

    # 来期EPS
    if data.forecast_eps:
        next_eps = data.forecast_eps
    else:
        next_eps = current_eps * (1 + growth_rate)

    # 再来期EPS（強気ケース用）
    future_eps = next_eps * (1 + growth_rate)

    # 株価計算
    conservative_price = current_eps * per  # 保守: 今期EPS × PER
    base_price = next_eps * per  # 中央: 来期EPS × PER
    optimistic_price = future_eps * per  # 強気: 再来期EPS × PER

    return conservative_price, base_price, optimistic_price


# ========================================
# 6. 最終評価
# ========================================

def evaluate_valuation(current_price: float, base_price: float) -> Tuple[str, float]:
    """
    バリュエーション判定

    Args:
        current_price: 現在株価
        base_price: 中央ケース適正株価

    Returns:
        (評価, 乖離率%)
    """
    divergence_pct = ((current_price - base_price) / base_price) * 100

    if divergence_pct <= VALUATION_THRESHOLDS['undervalued'] * 100:
        valuation = 'undervalued'
    elif divergence_pct >= VALUATION_THRESHOLDS['overvalued'] * 100:
        valuation = 'overvalued'
    else:
        valuation = 'fair'

    return valuation, divergence_pct


def generate_investment_comment(
    valuation: str,
    divergence_pct: float,
    growth_rate: float,
    quality_rank: str
) -> str:
    """
    投資判断コメントを生成

    Args:
        valuation: 評価（undervalued/fair/overvalued）
        divergence_pct: 乖離率（%）
        growth_rate: 成長率
        quality_rank: 成長品質ランク

    Returns:
        コメント文字列
    """
    if valuation == 'undervalued':
        comment = f"[割安] 現在株価は適正価格から{abs(divergence_pct):.1f}%下回る。"
        comment += f"成長率{growth_rate*100:.1f}%、品質{quality_rank.upper()}を考慮すると、投資妙味あり。"
    elif valuation == 'overvalued':
        comment = f"[割高] 現在株価は適正価格を{divergence_pct:.1f}%上回る。"
        comment += f"成長率{growth_rate*100:.1f}%に対してプレミアムが過大。慎重な判断を推奨。"
    else:
        comment = f"[適正] 現在株価との乖離は{divergence_pct:+.1f}%。"
        comment += f"成長率{growth_rate*100:.1f}%、品質{quality_rank.upper()}を勘案すると妥当な水準。"

    return comment


# ========================================
# メイン関数
# ========================================

def calculate_growth_fair_value(data: FinancialData) -> GrowthFairValue:
    """
    グロース株の適正株価を算出（メイン関数）

    Args:
        data: 財務データ

    Returns:
        グロース株適正株価評価結果
    """
    # 1. 成長率分析
    growth_analysis = analyze_growth_rate(data)

    # 2. 成長品質評価
    quality = evaluate_growth_quality(data, growth_analysis)

    # 3. PEGレシオ決定
    peg_analysis = determine_peg_ratio(growth_analysis, quality)

    # 4. 適正PER算出
    per_analysis = calculate_theoretical_per(
        growth_rate=growth_analysis.adopted_growth,
        peg=peg_analysis.adopted_peg,
        data=data
    )

    # 5. 株価レンジ算出
    conservative, base, optimistic = calculate_price_range(
        per=per_analysis.adjusted_per,
        data=data,
        growth_rate=growth_analysis.adopted_growth
    )

    # 6. 最終評価
    valuation, divergence_pct = evaluate_valuation(data.current_price, base)

    # 投資判断コメント
    investment_comment = generate_investment_comment(
        valuation=valuation,
        divergence_pct=divergence_pct,
        growth_rate=growth_analysis.adopted_growth,
        quality_rank=quality.rank
    )

    # 評価根拠サマリー
    rationale = (
        f"成長率{growth_analysis.adopted_growth*100:.1f}%（{growth_analysis.growth_band.upper()}）、"
        f"品質{quality.rank.upper()}により、PEG {peg_analysis.adopted_peg:.2f}、"
        f"適正PER {per_analysis.adjusted_per:.1f}を採用。"
    )

    # 使用EPS
    current_eps = data.eps_list[-1] if data.eps_list else 0
    next_eps = data.forecast_eps if data.forecast_eps else current_eps * (1 + growth_analysis.adopted_growth)

    return GrowthFairValue(
        code=data.code,
        company_name=data.company_name,
        current_price=data.current_price,
        growth_analysis=growth_analysis,
        growth_quality=quality,
        peg_analysis=peg_analysis,
        per_analysis=per_analysis,
        conservative_price=conservative,
        base_price=base,
        optimistic_price=optimistic,
        current_vs_fair=valuation,
        divergence_pct=divergence_pct,
        rationale=rationale,
        investment_comment=investment_comment,
        current_eps=current_eps,
        next_eps=next_eps
    )
