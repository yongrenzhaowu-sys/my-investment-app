"""
適正株価算出機能のデータモデル定義

このモジュールは、グロース株・バリュー株の適正株価算出に必要な
データ構造を定義します。
"""

from dataclasses import dataclass, field
from typing import Optional, Literal, Dict, List
from datetime import datetime


# ========================================
# 共通モデル
# ========================================

@dataclass
class FinancialData:
    """財務データ（複数期）"""
    # 基本情報
    code: str
    company_name: str
    current_price: float
    shares_outstanding: float  # 発行済株式数
    market_cap: float  # 時価総額（百万円）

    # 損益データ（リスト: 古い順）
    sales: List[float] = field(default_factory=list)  # 売上高
    operating_profit: List[float] = field(default_factory=list)  # 営業利益
    ordinary_profit: List[float] = field(default_factory=list)  # 経常利益
    net_profit: List[float] = field(default_factory=list)  # 純利益
    eps_list: List[float] = field(default_factory=list)  # EPS

    # BS・CFデータ（最新値）
    bps: Optional[float] = None  # 1株当たり純資産
    equity: Optional[float] = None  # 自己資本（百万円）
    total_assets: Optional[float] = None  # 総資産（百万円）
    cash: Optional[float] = None  # 現預金（百万円）
    debt: Optional[float] = None  # 有利子負債（百万円）
    operating_cf: Optional[float] = None  # 営業CF（百万円）
    investing_cf: Optional[float] = None  # 投資CF（百万円）

    # その他
    dividend: Optional[float] = None  # 年間配当金
    roe: Optional[float] = None  # ROE（%）

    # 予想データ
    forecast_eps: Optional[float] = None  # 予想EPS
    forecast_net_profit: Optional[float] = None  # 予想純利益

    # 過去マルチプルレンジ
    historical_per_min: Optional[float] = None
    historical_per_max: Optional[float] = None
    historical_pbr_min: Optional[float] = None
    historical_pbr_max: Optional[float] = None

    # メタデータ
    fiscal_periods: List[str] = field(default_factory=list)  # 決算期リスト


@dataclass
class GrowthQuality:
    """成長の質評価"""
    rank: Literal['high', 'medium', 'low']
    sales_growing: bool  # 売上も成長しているか
    margin_improving: bool  # 利益率が改善しているか
    one_time_dependent: bool  # 一時要因依存か
    sustainable: bool  # ビジネスモデルの継続性
    reasons: List[str] = field(default_factory=list)  # 判定理由


@dataclass
class AssetQuality:
    """資産品質評価"""
    rank: Literal['high', 'medium', 'low']
    cash_ratio: float  # 現預金比率
    has_goodwill_risk: bool  # のれんリスク
    has_inventory_risk: bool  # 棚卸資産リスク
    reasons: List[str] = field(default_factory=list)


@dataclass
class FinancialSafety:
    """財務安全性評価"""
    rank: Literal['high', 'medium', 'low']
    equity_ratio: float  # 自己資本比率（%）
    net_cash: float  # ネットキャッシュ（百万円、マイナス=ネットデット）
    cf_stable: bool  # 営業CF安定性
    reasons: List[str] = field(default_factory=list)


# ========================================
# グロース株評価モデル
# ========================================

@dataclass
class GrowthRateAnalysis:
    """EPS成長率分析"""
    historical_cagr: float  # 過去CAGR（%）
    forecast_growth: Optional[float]  # 予想成長率（%）
    adopted_growth: float  # 採用成長率（%）
    growth_band: Literal['low', 'mid', 'high', 'ultra']  # 成長率帯
    reasons: List[str] = field(default_factory=list)  # 採用理由
    excluded_years: List[int] = field(default_factory=list)  # 除外年インデックス


@dataclass
class PEGRatioAnalysis:
    """PEGレシオ分析"""
    theoretical_peg: float  # 理論PEG
    peg_range_min: float  # PEGレンジ下限
    peg_range_max: float  # PEGレンジ上限
    adopted_peg: float  # 採用PEG
    reasons: List[str] = field(default_factory=list)


@dataclass
class PERAnalysis:
    """PER分析（グロース株）"""
    theoretical_per: float  # 理論PER（PEG × 成長率）
    adjusted_per: float  # 調整後PER
    adjustment_reasons: List[str] = field(default_factory=list)
    historical_per_cap: Optional[float] = None  # 過去レンジ上限
    peer_per_avg: Optional[float] = None  # 同業PER平均


@dataclass
class GrowthFairValue:
    """グロース株適正株価評価結果"""
    code: str
    company_name: str
    current_price: float

    # 成長率分析
    growth_analysis: GrowthRateAnalysis
    growth_quality: GrowthQuality

    # PEG・PER分析
    peg_analysis: PEGRatioAnalysis
    per_analysis: PERAnalysis

    # 適正株価レンジ
    conservative_price: float  # 保守ケース
    base_price: float  # 中央ケース
    optimistic_price: float  # 強気ケース

    # 評価
    current_vs_fair: Literal['undervalued', 'fair', 'overvalued']  # 割安/適正/割高
    divergence_pct: float  # 乖離率（%）= (現在株価 - 中央ケース) / 中央ケース × 100

    # 総合コメント
    rationale: str  # 評価根拠
    investment_comment: str  # 投資判断コメント

    # 計算に使用したEPS
    current_eps: float
    next_eps: Optional[float] = None


# ========================================
# バリュー株評価モデル
# ========================================

@dataclass
class NormalizedEPS:
    """正規化EPS"""
    historical_avg_eps: float  # 過去平均EPS
    current_eps: float  # 今期EPS
    next_eps: Optional[float]  # 来期想定EPS
    adopted_eps: float  # 採用正規化EPS
    reasons: List[str] = field(default_factory=list)


@dataclass
class ValueQuality:
    """バリュー株総合品質評価"""
    asset_quality: AssetQuality
    financial_safety: FinancialSafety
    roe_level: Literal['high', 'mid', 'low']  # ROE水準
    dividend_policy: Literal['aggressive', 'normal', 'weak']  # 還元姿勢
    overall_rank: Literal['high', 'medium', 'low']  # 総合ランク
    reasons: List[str] = field(default_factory=list)


@dataclass
class ValueMethod:
    """バリュー株評価軸"""
    method: Literal['pbr', 'per', 'ev_ebitda', 'dividend']
    reasons: List[str] = field(default_factory=list)  # 選定理由


@dataclass
class MultipleAnalysis:
    """マルチプル分析"""
    method: Literal['pbr', 'per', 'ev_ebitda']
    theoretical_multiple: float  # 理論マルチプル
    adjusted_multiple: float  # 調整後マルチプル
    range_min: float  # レンジ下限
    range_max: float  # レンジ上限
    adjustment_reasons: List[str] = field(default_factory=list)


@dataclass
class ValueFairValue:
    """バリュー株適正株価評価結果"""
    code: str
    company_name: str
    current_price: float

    # 正規化EPS
    normalized_eps: NormalizedEPS

    # 品質評価
    value_quality: ValueQuality

    # 評価軸
    primary_method: ValueMethod

    # マルチプル分析
    multiple_analysis: MultipleAnalysis

    # 適正株価レンジ
    conservative_price: float  # 保守ケース
    base_price: float  # 中央ケース
    optimistic_price: float  # 強気ケース

    # 評価
    current_vs_fair: Literal['undervalued', 'fair', 'overvalued']
    divergence_pct: float  # 乖離率（%）
    margin_of_safety: float  # 安全域（%）= (中央ケース - 現在株価) / 中央ケース × 100

    # 総合コメント
    rationale: str  # 評価根拠
    investment_comment: str  # 投資判断コメント
    catalyst: str  # カタリスト
    risks: str  # リスク

    # 計算に使用した基礎データ
    bps: Optional[float] = None
    roe: Optional[float] = None
    ebitda: Optional[float] = None


# ========================================
# 統合評価モデル
# ========================================

@dataclass
class ComprehensiveFairValue:
    """包括的適正株価評価（グロース・バリュー両方）"""
    code: str
    company_name: str
    current_price: float

    # 推奨評価タイプ
    recommended_type: Literal['growth', 'value', 'hybrid']

    # 総合推奨価格
    recommended_price: float
    recommended_method: str  # 採用した評価方法

    # 各評価結果
    growth_result: Optional[GrowthFairValue] = None
    value_result: Optional[ValueFairValue] = None

    # メタデータ
    calculated_at: datetime = field(default_factory=datetime.now)
    data_quality: Literal['high', 'medium', 'low'] = 'medium'  # データ品質
    missing_data: List[str] = field(default_factory=list)  # 不足データ
    warnings: List[str] = field(default_factory=list)  # 警告
