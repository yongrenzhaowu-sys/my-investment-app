"""
バリュー株向け適正株価算出エンジン

PBR/PER/EV-EBITDAベースでバリュー株の適正株価を算出します。
"""

import numpy as np
from typing import List, Optional, Tuple
from src.fair_value_models import (
    FinancialData,
    NormalizedEPS,
    AssetQuality,
    FinancialSafety,
    ValueQuality,
    ValueMethod,
    MultipleAnalysis,
    ValueFairValue
)
from src.fair_value_constants import (
    get_roe_level,
    get_pbr_range,
    get_per_range_value,
    get_ev_ebitda_range,
    ROE_LEVEL_THRESHOLDS,
    FINANCIAL_SAFETY_THRESHOLDS,
    ASSET_QUALITY_THRESHOLDS,
    VALUATION_THRESHOLDS,
    MULTIPLE_ADJUSTMENT_LIMITS
)


# ========================================
# 1. 正規化EPS算出
# ========================================

def calculate_normalized_eps(data: FinancialData) -> NormalizedEPS:
    """
    正規化EPSを算出

    Args:
        data: 財務データ

    Returns:
        正規化EPS分析
    """
    reasons = []

    # 過去平均EPS
    if data.eps_list:
        historical_avg_eps = np.mean(data.eps_list)
        reasons.append(f"過去平均EPS: {historical_avg_eps:.2f}円（{len(data.eps_list)}期）")
    else:
        historical_avg_eps = 0
        reasons.append("⚠️ 過去EPSデータなし")

    # 今期EPS
    current_eps = data.eps_list[-1] if data.eps_list else 0
    reasons.append(f"今期EPS: {current_eps:.2f}円")

    # 来期想定EPS
    if data.forecast_eps:
        next_eps = data.forecast_eps
        reasons.append(f"来期予想EPS: {next_eps:.2f}円")
    else:
        next_eps = None
        reasons.append("⚠️ 来期予想EPSなし")

    # 採用正規化EPS決定
    # ルール: 来期予想 > 今期実績 > 過去平均（データ品質による優先順位）
    if next_eps and next_eps > 0:
        adopted_eps = next_eps
        reasons.append(f"✅ 採用: 来期予想EPS {adopted_eps:.2f}円")
    elif current_eps > 0:
        adopted_eps = current_eps
        reasons.append(f"✅ 採用: 今期EPS {adopted_eps:.2f}円（予想なし）")
    elif historical_avg_eps > 0:
        adopted_eps = historical_avg_eps
        reasons.append(f"✅ 採用: 過去平均EPS {adopted_eps:.2f}円（今期データなし）")
    else:
        adopted_eps = 0
        reasons.append("❌ 採用EPSなし（データ不足）")

    return NormalizedEPS(
        historical_avg_eps=historical_avg_eps,
        current_eps=current_eps,
        next_eps=next_eps,
        adopted_eps=adopted_eps,
        reasons=reasons
    )


# ========================================
# 2. 資産品質評価
# ========================================

def evaluate_asset_quality(data: FinancialData) -> AssetQuality:
    """
    資産品質を評価

    Args:
        data: 財務データ

    Returns:
        資産品質評価
    """
    reasons = []
    score = 0  # スコアリング（0～3点）

    # 現預金比率
    cash_ratio = 0
    if data.total_assets and data.cash:
        cash_ratio = data.cash / data.total_assets
        if cash_ratio >= ASSET_QUALITY_THRESHOLDS['cash_ratio_high']:
            score += 1
            reasons.append(f"✅ 現預金比率: {cash_ratio*100:.1f}%（高水準）")
        elif cash_ratio >= ASSET_QUALITY_THRESHOLDS['cash_ratio_low']:
            reasons.append(f"📊 現預金比率: {cash_ratio*100:.1f}%（普通）")
        else:
            reasons.append(f"⚠️ 現預金比率: {cash_ratio*100:.1f}%（低水準）")
    else:
        reasons.append("⚠️ 現預金データなし")

    # のれんリスク（TODO: のれんデータ取得後に実装）
    has_goodwill_risk = False
    score += 1  # 仮スコア
    reasons.append("✅ のれんリスク: 低（データ未実装）")

    # 棚卸資産リスク（TODO: 棚卸資産データ取得後に実装）
    has_inventory_risk = False
    score += 1  # 仮スコア
    reasons.append("✅ 棚卸資産リスク: 低（データ未実装）")

    # 総合評価
    if score >= 3:
        rank = 'high'
    elif score >= 2:
        rank = 'medium'
    else:
        rank = 'low'

    reasons.append(f"📊 資産品質スコア: {score}/3 → ランク: {rank.upper()}")

    return AssetQuality(
        rank=rank,
        cash_ratio=cash_ratio,
        has_goodwill_risk=has_goodwill_risk,
        has_inventory_risk=has_inventory_risk,
        reasons=reasons
    )


# ========================================
# 3. 財務安全性評価
# ========================================

def evaluate_financial_safety(data: FinancialData) -> FinancialSafety:
    """
    財務安全性を評価

    Args:
        data: 財務データ

    Returns:
        財務安全性評価
    """
    reasons = []
    score = 0  # スコアリング（0～3点）

    # 自己資本比率
    equity_ratio = 0
    if data.total_assets and data.equity:
        equity_ratio = (data.equity / data.total_assets) * 100
        if equity_ratio >= FINANCIAL_SAFETY_THRESHOLDS['equity_ratio_high']:
            score += 1
            reasons.append(f"✅ 自己資本比率: {equity_ratio:.1f}%（高水準）")
        elif equity_ratio >= FINANCIAL_SAFETY_THRESHOLDS['equity_ratio_low']:
            reasons.append(f"📊 自己資本比率: {equity_ratio:.1f}%（普通）")
        else:
            reasons.append(f"⚠️ 自己資本比率: {equity_ratio:.1f}%（低水準）")
    else:
        reasons.append("⚠️ 自己資本比率データなし")

    # ネットキャッシュ / ネットデット
    net_cash = 0
    if data.cash is not None and data.debt is not None:
        net_cash = data.cash - data.debt
        if net_cash > 0:
            score += 1
            reasons.append(f"✅ ネットキャッシュ: {net_cash:.0f}百万円（無借金経営）")
        else:
            reasons.append(f"⚠️ ネットデット: {abs(net_cash):.0f}百万円")
    else:
        reasons.append("⚠️ ネットキャッシュデータ不足")

    # 営業CFの安定性（TODO: 複数期CFデータ取得後に実装）
    cf_stable = True  # 仮判定
    score += 1
    reasons.append("✅ 営業CF安定（データ未実装）")

    # 総合評価
    if score >= 3:
        rank = 'high'
    elif score >= 2:
        rank = 'medium'
    else:
        rank = 'low'

    reasons.append(f"📊 財務安全性スコア: {score}/3 → ランク: {rank.upper()}")

    return FinancialSafety(
        rank=rank,
        equity_ratio=equity_ratio,
        net_cash=net_cash,
        cf_stable=cf_stable,
        reasons=reasons
    )


# ========================================
# 4. 総合品質評価
# ========================================

def evaluate_value_quality(
    data: FinancialData,
    asset_quality: AssetQuality,
    financial_safety: FinancialSafety
) -> ValueQuality:
    """
    バリュー株の総合品質を評価

    Args:
        data: 財務データ
        asset_quality: 資産品質評価
        financial_safety: 財務安全性評価

    Returns:
        総合品質評価
    """
    reasons = []

    # ROE水準判定
    roe = data.roe if data.roe else 0
    roe_level = get_roe_level(roe)
    reasons.append(f"ROE: {roe:.1f}% → {roe_level.upper()}水準")

    # 配当方針判定（TODO: 配当性向・DOE・自社株買いデータ取得後に実装）
    dividend_policy = 'normal'  # 仮判定
    if data.dividend and data.current_price:
        dividend_yield = (data.dividend / data.current_price) * 100
        reasons.append(f"配当利回り: {dividend_yield:.2f}%")
        if dividend_yield >= 3.0:
            dividend_policy = 'aggressive'
        elif dividend_yield < 1.0:
            dividend_policy = 'weak'
    else:
        reasons.append("⚠️ 配当データ不足")

    reasons.append(f"還元姿勢: {dividend_policy.upper()}")

    # 総合ランク決定（資産品質・財務安全性・ROE・還元の平均）
    rank_scores = {
        'high': 3,
        'medium': 2,
        'low': 1,
        'aggressive': 3,
        'normal': 2,
        'weak': 1
    }

    total_score = (
        rank_scores.get(asset_quality.rank, 2) +
        rank_scores.get(financial_safety.rank, 2) +
        rank_scores.get(roe_level, 2) +
        rank_scores.get(dividend_policy, 2)
    )
    avg_score = total_score / 4

    if avg_score >= 2.5:
        overall_rank = 'high'
    elif avg_score >= 1.5:
        overall_rank = 'medium'
    else:
        overall_rank = 'low'

    reasons.append(f"📊 総合品質: {overall_rank.upper()}（平均スコア{avg_score:.1f}/3）")

    return ValueQuality(
        asset_quality=asset_quality,
        financial_safety=financial_safety,
        roe_level=roe_level,
        dividend_policy=dividend_policy,
        overall_rank=overall_rank,
        reasons=reasons
    )


# ========================================
# 5. 評価軸選定
# ========================================

def select_valuation_method(data: FinancialData, quality: ValueQuality) -> ValueMethod:
    """
    評価軸を選定

    Args:
        data: 財務データ
        quality: 総合品質評価

    Returns:
        評価軸
    """
    reasons = []

    # デフォルト: PBR方式
    method = 'pbr'

    # ROEが高い場合はPER方式を検討
    if quality.roe_level == 'high' and data.eps_list:
        method = 'per'
        reasons.append("✅ ROE高水準のため、PER方式を採用")
    # 資産株（低ROE・高現預金）の場合はPBR
    elif quality.roe_level == 'low' and quality.asset_quality.cash_ratio > 0.15:
        method = 'pbr'
        reasons.append("✅ 資産株（低ROE・高現預金）のため、PBR方式を採用")
    # 安定収益株の場合はPER
    elif quality.financial_safety.rank == 'high' and data.eps_list:
        method = 'per'
        reasons.append("✅ 財務安全性高・収益安定のため、PER方式を採用")
    else:
        method = 'pbr'
        reasons.append("✅ デフォルトでPBR方式を採用")

    return ValueMethod(
        method=method,
        reasons=reasons
    )


# ========================================
# 6. マルチプル算出
# ========================================

def calculate_multiple(
    method: str,
    data: FinancialData,
    quality: ValueQuality
) -> MultipleAnalysis:
    """
    適正マルチプルを算出

    Args:
        method: 評価方法（'pbr', 'per', 'ev_ebitda'）
        data: 財務データ
        quality: 総合品質評価

    Returns:
        マルチプル分析
    """
    adjustment_reasons = []

    if method == 'pbr':
        # PBR方式
        roe_level = quality.roe_level
        quality_rank = quality.overall_rank

        # 理論PBRレンジ取得
        pbr_min, pbr_max = get_pbr_range(roe_level, quality_rank)
        theoretical_multiple = (pbr_min + pbr_max) / 2  # 中央値

        adjustment_reasons.append(
            f"ROE水準: {roe_level.upper()}, 品質: {quality_rank.upper()} "
            f"→ PBRレンジ {pbr_min:.2f}～{pbr_max:.2f}, 採用{theoretical_multiple:.2f}"
        )

        # 過去PBRレンジとの比較調整
        adjusted_multiple = theoretical_multiple
        if data.historical_pbr_max:
            historical_cap = data.historical_pbr_max * MULTIPLE_ADJUSTMENT_LIMITS['historical_cap_ratio']
            if adjusted_multiple > historical_cap:
                old_multiple = adjusted_multiple
                adjusted_multiple = historical_cap
                adjustment_reasons.append(
                    f"⚠️ 過去PBR上限調整: {old_multiple:.2f} → {adjusted_multiple:.2f}"
                )

        return MultipleAnalysis(
            method='pbr',
            theoretical_multiple=theoretical_multiple,
            adjusted_multiple=adjusted_multiple,
            range_min=pbr_min,
            range_max=pbr_max,
            adjustment_reasons=adjustment_reasons
        )

    elif method == 'per':
        # PER方式
        quality_rank = quality.overall_rank

        # 理論PERレンジ取得
        per_min, per_max = get_per_range_value(quality_rank)
        theoretical_multiple = (per_min + per_max) / 2

        adjustment_reasons.append(
            f"品質: {quality_rank.UPPER()} → PERレンジ {per_min:.1f}～{per_max:.1f}, 採用{theoretical_multiple:.1f}"
        )

        # 過去PERレンジとの比較調整
        adjusted_multiple = theoretical_multiple
        if data.historical_per_max:
            historical_cap = data.historical_per_max * MULTIPLE_ADJUSTMENT_LIMITS['historical_cap_ratio']
            if adjusted_multiple > historical_cap:
                old_multiple = adjusted_multiple
                adjusted_multiple = historical_cap
                adjustment_reasons.append(
                    f"⚠️ 過去PER上限調整: {old_multiple:.1f} → {adjusted_multiple:.1f}"
                )

        return MultipleAnalysis(
            method='per',
            theoretical_multiple=theoretical_multiple,
            adjusted_multiple=adjusted_multiple,
            range_min=per_min,
            range_max=per_max,
            adjustment_reasons=adjustment_reasons
        )

    else:
        # EV/EBITDA方式（TODO: 実装）
        adjustment_reasons.append("⚠️ EV/EBITDA方式は未実装")
        return MultipleAnalysis(
            method='ev_ebitda',
            theoretical_multiple=7.0,
            adjusted_multiple=7.0,
            range_min=6.0,
            range_max=9.0,
            adjustment_reasons=adjustment_reasons
        )


# ========================================
# 7. 株価レンジ算出
# ========================================

def calculate_value_price_range(
    method: str,
    multiple: float,
    data: FinancialData,
    normalized_eps: NormalizedEPS
) -> Tuple[float, float, float]:
    """
    適正株価レンジを算出（保守・中央・強気）

    Args:
        method: 評価方法
        multiple: 採用マルチプル
        data: 財務データ
        normalized_eps: 正規化EPS

    Returns:
        (保守ケース, 中央ケース, 強気ケース)
    """
    if method == 'pbr':
        # PBR方式
        bps = data.bps if data.bps else 0

        # 保守: PBR × 0.9
        conservative_price = bps * multiple * 0.9
        # 中央: PBR × 1.0
        base_price = bps * multiple
        # 強気: PBR × 1.1
        optimistic_price = bps * multiple * 1.1

    elif method == 'per':
        # PER方式
        eps = normalized_eps.adopted_eps

        # 保守: 過去平均EPS × PER
        conservative_eps = normalized_eps.historical_avg_eps if normalized_eps.historical_avg_eps > 0 else eps
        conservative_price = conservative_eps * multiple

        # 中央: 採用EPS × PER
        base_price = eps * multiple

        # 強気: 来期EPS × PER
        optimistic_eps = normalized_eps.next_eps if normalized_eps.next_eps else eps * 1.1
        optimistic_price = optimistic_eps * multiple

    else:
        # EV/EBITDA方式（TODO）
        conservative_price = data.current_price * 0.9
        base_price = data.current_price
        optimistic_price = data.current_price * 1.1

    return conservative_price, base_price, optimistic_price


# ========================================
# 8. 最終評価
# ========================================

def evaluate_value_valuation(current_price: float, base_price: float) -> Tuple[str, float, float]:
    """
    バリュエーション判定

    Args:
        current_price: 現在株価
        base_price: 中央ケース適正株価

    Returns:
        (評価, 乖離率%, 安全域%)
    """
    divergence_pct = ((current_price - base_price) / base_price) * 100
    margin_of_safety = ((base_price - current_price) / base_price) * 100

    if divergence_pct <= VALUATION_THRESHOLDS['undervalued'] * 100:
        valuation = 'undervalued'
    elif divergence_pct >= VALUATION_THRESHOLDS['overvalued'] * 100:
        valuation = 'overvalued'
    else:
        valuation = 'fair'

    return valuation, divergence_pct, margin_of_safety


def generate_value_comment(
    valuation: str,
    margin_of_safety: float,
    method: str,
    quality_rank: str
) -> str:
    """
    投資判断コメントを生成

    Args:
        valuation: 評価
        margin_of_safety: 安全域（%）
        method: 評価方法
        quality_rank: 品質ランク

    Returns:
        コメント文字列
    """
    method_name = {'pbr': 'PBR', 'per': 'PER', 'ev_ebitda': 'EV/EBITDA'}.get(method, method)

    if valuation == 'undervalued':
        comment = f"[割安] 安全域{margin_of_safety:.1f}%。"
        comment += f"{method_name}方式、品質{quality_rank.upper()}を勘案すると、下値余地は限定的。"
    elif valuation == 'overvalued':
        comment = f"[割高] 現在株価が適正価格を{abs(margin_of_safety):.1f}%上回る。"
        comment += f"{method_name}ベースでは説明困難な水準。慎重な判断を推奨。"
    else:
        comment = f"[適正] 安全域{margin_of_safety:+.1f}%。"
        comment += f"{method_name}方式で評価した場合、妥当な水準。"

    return comment


# ========================================
# メイン関数
# ========================================

def calculate_value_fair_value(data: FinancialData) -> ValueFairValue:
    """
    バリュー株の適正株価を算出（メイン関数）

    Args:
        data: 財務データ

    Returns:
        バリュー株適正株価評価結果
    """
    # 1. 正規化EPS算出
    normalized_eps = calculate_normalized_eps(data)

    # 2. 品質評価
    asset_quality = evaluate_asset_quality(data)
    financial_safety = evaluate_financial_safety(data)
    value_quality = evaluate_value_quality(data, asset_quality, financial_safety)

    # 3. 評価軸選定
    primary_method = select_valuation_method(data, value_quality)

    # 4. マルチプル算出
    multiple_analysis = calculate_multiple(
        method=primary_method.method,
        data=data,
        quality=value_quality
    )

    # 5. 株価レンジ算出
    conservative, base, optimistic = calculate_value_price_range(
        method=primary_method.method,
        multiple=multiple_analysis.adjusted_multiple,
        data=data,
        normalized_eps=normalized_eps
    )

    # 6. 最終評価
    valuation, divergence_pct, margin_of_safety = evaluate_value_valuation(
        data.current_price, base
    )

    # 投資判断コメント
    investment_comment = generate_value_comment(
        valuation=valuation,
        margin_of_safety=margin_of_safety,
        method=primary_method.method,
        quality_rank=value_quality.overall_rank
    )

    # 評価根拠サマリー
    method_name = {'pbr': 'PBR', 'per': 'PER', 'ev_ebitda': 'EV/EBITDA'}.get(primary_method.method)
    rationale = (
        f"{method_name}方式を採用。品質{value_quality.overall_rank.upper()}、"
        f"適正{method_name} {multiple_analysis.adjusted_multiple:.2f}により算出。"
    )

    return ValueFairValue(
        code=data.code,
        company_name=data.company_name,
        current_price=data.current_price,
        normalized_eps=normalized_eps,
        value_quality=value_quality,
        primary_method=primary_method,
        multiple_analysis=multiple_analysis,
        conservative_price=conservative,
        base_price=base,
        optimistic_price=optimistic,
        current_vs_fair=valuation,
        divergence_pct=divergence_pct,
        margin_of_safety=margin_of_safety,
        rationale=rationale,
        investment_comment=investment_comment,
        catalyst="カタリスト未実装",  # TODO
        risks="リスク未実装",  # TODO
        bps=data.bps,
        roe=data.roe,
        ebitda=None  # TODO
    )
