"""
適正株価算出機能の定数・マトリクス定義

マジックナンバーを避け、閾値・評価基準を一元管理します。
"""

from typing import Dict, Tuple


# ========================================
# グロース株評価定数
# ========================================

# 成長率帯の分類基準（%）
GROWTH_BAND_THRESHOLDS = {
    'low': (0, 10),       # 低成長: 0～10%
    'mid': (10, 20),      # 中成長: 10～20%
    'high': (20, 40),     # 高成長: 20～40%
    'ultra': (40, 999)    # 超高成長: 40%以上
}

# PEGレシオマトリクス（成長率帯 × 成長品質 → PEGレンジ）
# 形式: {(growth_band, quality): (peg_min, peg_max)}
PEG_MATRIX: Dict[Tuple[str, str], Tuple[float, float]] = {
    # 低成長（0～10%）
    ('low', 'low'):    (0.5, 0.7),
    ('low', 'medium'): (0.7, 0.9),
    ('low', 'high'):   (0.9, 1.1),

    # 中成長（10～20%）
    ('mid', 'low'):    (0.7, 1.0),
    ('mid', 'medium'): (0.9, 1.3),
    ('mid', 'high'):   (1.2, 1.6),

    # 高成長（20～40%）
    ('high', 'low'):    (1.0, 1.4),
    ('high', 'medium'): (1.2, 1.8),
    ('high', 'high'):   (1.6, 2.2),

    # 超高成長（40%以上）
    ('ultra', 'low'):    (1.2, 1.8),
    ('ultra', 'medium'): (1.5, 2.5),
    ('ultra', 'high'):   (2.0, 3.5),
}

# 成長品質評価の閾値
GROWTH_QUALITY_THRESHOLDS = {
    'sales_growth_min': 0.05,  # 売上成長率の最低ライン（5%）
    'margin_improvement_min': 0.01,  # 利益率改善の最低ライン（1%ポイント）
}

# PER調整の上限比率（過去レンジ上限からの乖離許容）
PER_HISTORICAL_CAP_PREMIUM = 0.20  # 過去上限 + 20%まで許容

# PER調整の同業比較乖離許容
PER_PEER_DIVERGENCE_MAX = 0.50  # 同業平均から±50%まで許容


# ========================================
# バリュー株評価定数
# ========================================

# PBR目安マトリクス（ROE水準 × 品質ランク → PBRレンジ）
# 形式: {(roe_level, quality_rank): (pbr_min, pbr_max)}
PBR_MATRIX: Dict[Tuple[str, str], Tuple[float, float]] = {
    # 低ROE（< 5%）
    ('low', 'low'):    (0.4, 0.8),
    ('low', 'medium'): (0.6, 1.0),
    ('low', 'high'):   (0.8, 1.2),

    # 中ROE（5% ～ 10%）
    ('mid', 'low'):    (0.6, 1.0),
    ('mid', 'medium'): (0.8, 1.2),
    ('mid', 'high'):   (1.0, 1.5),

    # 高ROE（10%以上）
    ('high', 'low'):    (0.8, 1.2),
    ('high', 'medium'): (1.0, 1.5),
    ('high', 'high'):   (1.2, 2.0),
}

# ROE水準の分類基準（%）
ROE_LEVEL_THRESHOLDS = {
    'low': (0, 5),
    'mid': (5, 10),
    'high': (10, 999),
}

# PER目安マトリクス（利益安定性 × 財務健全性 × 還元姿勢 → PERレンジ）
# 簡易版: 総合品質ランクで判定
PER_MATRIX_VALUE: Dict[str, Tuple[float, float]] = {
    'low':    (6, 9),    # 低品質
    'medium': (10, 14),  # 中品質
    'high':   (14, 18),  # 高品質
}

# EV/EBITDA目安マトリクス
EV_EBITDA_MATRIX: Dict[str, Tuple[float, float]] = {
    'low':    (4, 6),    # 低品質
    'medium': (6, 9),    # 中品質
    'high':   (8, 12),   # 高品質
}

# 財務安全性評価の閾値
FINANCIAL_SAFETY_THRESHOLDS = {
    'equity_ratio_high': 50,    # 自己資本比率50%以上で高評価
    'equity_ratio_low': 30,     # 自己資本比率30%未満で低評価
}

# 資産品質評価の閾値
ASSET_QUALITY_THRESHOLDS = {
    'cash_ratio_high': 0.20,    # 現預金比率20%以上で高評価
    'cash_ratio_low': 0.05,     # 現預金比率5%未満で低評価
}

# 配当利回り期待値（バリュー株）
DIVIDEND_YIELD_EXPECTED = 0.03  # 3%


# ========================================
# 共通定数
# ========================================

# CAGR計算の最小期間
MIN_PERIODS_FOR_CAGR = 2

# 異常値判定の閾値（前年比）
OUTLIER_THRESHOLD_YOY = 3.0  # 前年比3倍以上は異常値候補

# データ品質評価の最小期数
MIN_PERIODS_FOR_HIGH_QUALITY = 5
MIN_PERIODS_FOR_MEDIUM_QUALITY = 3

# 評価判定の閾値（乖離率）
VALUATION_THRESHOLDS = {
    'undervalued': -0.15,   # -15%以下で割安
    'overvalued': 0.15,     # +15%以上で割高
    # -15% ～ +15%は適正
}

# マルチプル調整の上限・下限制約
MULTIPLE_ADJUSTMENT_LIMITS = {
    'historical_cap_ratio': 1.20,  # 過去上限の120%までキャップ
    'historical_floor_ratio': 0.80,  # 過去下限の80%までフロア
}


# ========================================
# ヘルパー関数
# ========================================

def get_growth_band(growth_rate: float) -> str:
    """成長率から成長率帯を判定"""
    for band, (min_val, max_val) in GROWTH_BAND_THRESHOLDS.items():
        if min_val <= growth_rate < max_val:
            return band
    return 'ultra'  # フォールバック


def get_peg_range(growth_band: str, quality: str) -> Tuple[float, float]:
    """成長率帯と品質からPEGレンジを取得"""
    return PEG_MATRIX.get((growth_band, quality), (1.0, 1.5))  # デフォルト


def get_roe_level(roe: float) -> str:
    """ROEから水準を判定"""
    for level, (min_val, max_val) in ROE_LEVEL_THRESHOLDS.items():
        if min_val <= roe < max_val:
            return level
    return 'high'  # フォールバック


def get_pbr_range(roe_level: str, quality: str) -> Tuple[float, float]:
    """ROE水準と品質からPBRレンジを取得"""
    return PBR_MATRIX.get((roe_level, quality), (0.8, 1.2))  # デフォルト


def get_per_range_value(quality: str) -> Tuple[float, float]:
    """品質からPERレンジを取得（バリュー株）"""
    return PER_MATRIX_VALUE.get(quality, (10, 14))  # デフォルト


def get_ev_ebitda_range(quality: str) -> Tuple[float, float]:
    """品質からEV/EBITDAレンジを取得"""
    return EV_EBITDA_MATRIX.get(quality, (6, 9))  # デフォルト
