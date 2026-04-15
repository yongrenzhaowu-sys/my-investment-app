"""
セクターモメンタム戦略

33業種分類に基づく短期モメンタムスコア計算
上位セクター → 上位銘柄 → ポジションサイジング
"""
import numpy as np
import pandas as pd
from typing import Tuple
from ..utils.sector33 import get_sector_name


class SectorMomentumStrategy:
    """
    セクター別モメンタム戦略

    ロジック:
    1. 銘柄ごとに短期モメンタム特徴量を計算
    2. セクターごとにスコアを集計
    3. 上位セクター内の上位銘柄を選択
    """

    def __init__(
        self,
        lookback_5: int = 5,
        lookback_10: int = 10,
        lookback_20: int = 20,
        atr_period: int = 14,
    ):
        """
        Args:
            lookback_5: 短期リターン（5日）
            lookback_10: 中期リターン（10日）
            lookback_20: 長期リターン（20日）、SMA/Vol/ATR基準
            atr_period: ATR計算期間
        """
        self.lookback_5 = lookback_5
        self.lookback_10 = lookback_10
        self.lookback_20 = lookback_20
        self.atr_period = atr_period

    def calculate_features(
        self,
        master: pd.DataFrame,
        daily_bars: pd.DataFrame,
        asof_date: str,
    ) -> pd.DataFrame:
        """
        銘柄ごとの特徴量を計算

        Args:
            master: 銘柄マスター（Code, CompanyName, Sector33Code）
            daily_bars: 日次バー（Date, Code, AdjO, AdjH, AdjL, AdjC, AdjVo）
            asof_date: 基準日（この日の引け時点でスコア計算）

        Returns:
            pd.DataFrame: 特徴量付き銘柄データ
        """
        print("[CALC] 特徴量計算中...")

        # asof_date時点のデータのみ
        df = daily_bars.copy()
        df = df[df["Date"] <= asof_date].copy()

        if df.empty:
            raise ValueError(f"asof_date={asof_date}以前のデータが存在しません")

        # 銘柄ごとにグループ化
        features_list = []

        for code, group in df.groupby("Code"):
            group = group.sort_values("Date").copy()

            # 最新の価格
            latest = group.iloc[-1]
            latest_date = latest["Date"]
            latest_close = latest["AdjC"]

            # データ数チェック
            if len(group) < max(self.lookback_20, self.atr_period):
                continue  # データ不足

            # リターン計算
            ret_5 = self._calculate_return(group, self.lookback_5)
            ret_10 = self._calculate_return(group, self.lookback_10)
            ret_20 = self._calculate_return(group, self.lookback_20)

            # SMA20
            sma_20 = group["AdjC"].tail(self.lookback_20).mean()

            # 出来高比率（VolRatio）
            avg_vol_20 = group["AdjVo"].tail(self.lookback_20).mean()
            vol_ratio = latest["AdjVo"] / avg_vol_20 if avg_vol_20 > 0 else 0

            # 売買代金（概算: AdjC × AdjVo / 1e6 = 百万円）
            group["Value"] = group["AdjC"] * group["AdjVo"] / 1e6
            avg_value_20_mjpy = group["Value"].tail(self.lookback_20).mean()

            # ボラティリティ（20日の日次リターン標準偏差）
            group["DailyRet"] = group["AdjC"].pct_change()
            volatility_20 = group["DailyRet"].tail(self.lookback_20).std()

            # High20 / Low20
            high_20 = group["AdjH"].tail(self.lookback_20).max()
            low_20 = group["AdjL"].tail(self.lookback_20).min()

            # ATR14
            atr_14 = self._calculate_atr(group, self.atr_period)

            features_list.append(
                {
                    "Code": code,
                    "Date": latest_date,
                    "AdjC": latest_close,
                    "Ret_5": ret_5,
                    "Ret_10": ret_10,
                    "Ret_20": ret_20,
                    "SMA20": sma_20,
                    "VolRatio": vol_ratio,
                    "AvgValue20_MJPY": avg_value_20_mjpy,
                    "Volatility20": volatility_20,
                    "High20": high_20,
                    "Low20": low_20,
                    "ATR14": atr_14,
                }
            )

        features_df = pd.DataFrame(features_list)

        if features_df.empty:
            raise ValueError(
                f"特徴量の計算結果が空です。\n"
                f"as関連データ期間: {df['Date'].min()} 〜 {df['Date'].max()}\n"
                f"データ行数: {len(df)}\n"
                f"ユニーク銘柄数: {df['Code'].nunique()}"
            )

        print(f"  [DEBUG] features_df shape: {features_df.shape}, columns: {list(features_df.columns)[:5]}")
        print(f"  [DEBUG] master shape: {master.shape}, columns: {list(master.columns)}")

        # マスター情報をマージ
        features_df = features_df.merge(
            master[["Code", "CompanyName", "Sector33Code"]],
            on="Code",
            how="left",
        )

        # Sector33Nameを追加
        features_df["Sector33Name"] = features_df["Sector33Code"].apply(get_sector_name)

        print(f"  OK 特徴量計算完了: {len(features_df)}銘柄")
        return features_df

    def _calculate_return(self, group: pd.DataFrame, periods: int) -> float:
        """N日リターン計算（%）"""
        if len(group) < periods + 1:
            return 0.0
        price_now = group["AdjC"].iloc[-1]
        price_past = group["AdjC"].iloc[-(periods + 1)]
        if price_past == 0:
            return 0.0
        return ((price_now / price_past) - 1.0) * 100.0

    def _calculate_atr(self, group: pd.DataFrame, periods: int) -> float:
        """ATR（Average True Range）計算"""
        if len(group) < periods:
            return 0.0

        group = group.tail(periods + 1).copy()
        group["H-L"] = group["AdjH"] - group["AdjL"]
        group["H-PC"] = abs(group["AdjH"] - group["AdjC"].shift(1))
        group["L-PC"] = abs(group["AdjL"] - group["AdjC"].shift(1))
        group["TR"] = group[["H-L", "H-PC", "L-PC"]].max(axis=1)

        atr = group["TR"].tail(periods).mean()
        return atr

    def filter_stocks(
        self,
        features_df: pd.DataFrame,
        min_price: float = 200.0,
        min_liquidity_mjpy: float = 30.0,
        min_vol_ratio: float = 1.1,
    ) -> pd.DataFrame:
        """
        銘柄フィルタリング

        Args:
            features_df: 特徴量付き銘柄データ
            min_price: 最低価格（デフォルト200円）
            min_liquidity_mjpy: 最低流動性（百万円、デフォルト30）
            min_vol_ratio: 最低出来高比率（デフォルト1.1）

        Returns:
            pd.DataFrame: フィルタ後の銘柄データ
        """
        df = features_df.copy()

        # フィルタ条件
        mask = (
            (df["AdjC"] >= min_price)
            & (df["AdjC"] >= df["SMA20"])  # 上昇トレンド
            & (df["AvgValue20_MJPY"] >= min_liquidity_mjpy)
            & (df["VolRatio"] >= min_vol_ratio)
            & (df["Volatility20"] > 0)  # ボラティリティ計算可能
        )

        filtered = df[mask].copy()
        print(f"  OK フィルタ後: {len(filtered)}銘柄（元: {len(df)}銘柄）")
        return filtered

    def calculate_stock_score(self, filtered_df: pd.DataFrame) -> pd.DataFrame:
        """
        銘柄スコア計算（robust z-score）

        Args:
            filtered_df: フィルタ後の銘柄データ

        Returns:
            pd.DataFrame: スコア付き銘柄データ
        """
        df = filtered_df.copy()

        # robust z-score（中央値とIQRで頑健化）
        def robust_zscore(series: pd.Series) -> pd.Series:
            median = series.median()
            q25 = series.quantile(0.25)
            q75 = series.quantile(0.75)
            iqr = q75 - q25
            if iqr == 0:
                return pd.Series(0, index=series.index)
            return (series - median) / iqr

        # 各特徴量のスコア化
        df["Score_Ret5"] = robust_zscore(df["Ret_5"])
        df["Score_Ret10"] = robust_zscore(df["Ret_10"])
        df["Score_Ret20"] = robust_zscore(df["Ret_20"])
        df["Score_VolRatio"] = robust_zscore(df["VolRatio"])

        # 合成スコア（重み: 40% / 35% / 15% / 10%）
        df["Score"] = (
            0.40 * df["Score_Ret5"]
            + 0.35 * df["Score_Ret10"]
            + 0.15 * df["Score_Ret20"]
            + 0.10 * df["Score_VolRatio"]
        )

        print(f"  OK スコア計算完了")
        return df

    def rank_sectors(
        self,
        scored_df: pd.DataFrame,
        top_n: int = 30,
    ) -> pd.DataFrame:
        """
        セクターランキング

        Args:
            scored_df: スコア付き銘柄データ
            top_n: セクター内上位N銘柄の平均スコアで評価

        Returns:
            pd.DataFrame: セクター別スコア（降順）
        """
        print(f"[RANK] セクターランキング計算中...")

        sector_stats = []

        for sector_code, group in scored_df.groupby("Sector33Code"):
            # 上位N銘柄の平均スコア
            top_stocks = group.nlargest(min(top_n, len(group)), "Score")
            avg_score = top_stocks["Score"].mean()

            # breadth（AdjC > SMA20の比率）
            breadth = (group["AdjC"] >= group["SMA20"]).sum() / len(group)

            # 平均Ret_20
            avg_ret_20 = group["Ret_20"].mean()

            sector_stats.append(
                {
                    "Sector33Code": sector_code,
                    "Sector33Name": get_sector_name(sector_code),
                    "AvgScore": avg_score,
                    "Breadth": breadth,
                    "AvgRet20": avg_ret_20,
                    "StockCount": len(group),
                }
            )

        sector_df = pd.DataFrame(sector_stats)
        sector_df = sector_df.sort_values("AvgScore", ascending=False)

        print(f"  OK セクターランキング完了: {len(sector_df)}セクター")
        return sector_df

    def select_top_stocks(
        self,
        scored_df: pd.DataFrame,
        top_sectors_df: pd.DataFrame,
        top_k_sectors: int = 5,
        top_n_stocks: int = 20,
    ) -> pd.DataFrame:
        """
        推奨銘柄選択

        Args:
            scored_df: スコア付き銘柄データ
            top_sectors_df: セクターランキング
            top_k_sectors: 選択するセクター数
            top_n_stocks: 選択する銘柄数

        Returns:
            pd.DataFrame: 推奨銘柄（スコア降順）
        """
        print(f"[SELECT] 推奨銘柄選択中（上位{top_k_sectors}セクターから{top_n_stocks}銘柄）...")

        # 上位セクター
        top_sectors = top_sectors_df.head(top_k_sectors)["Sector33Code"].tolist()

        # 推奨セクター内の銘柄のみ
        candidates = scored_df[scored_df["Sector33Code"].isin(top_sectors)].copy()

        # スコア降順で選択
        top_stocks = candidates.nlargest(top_n_stocks, "Score")

        print(f"  OK 推奨銘柄選択完了: {len(top_stocks)}銘柄")
        return top_stocks

    def run(
        self,
        master: pd.DataFrame,
        daily_bars: pd.DataFrame,
        asof_date: str,
        top_k_sectors: int = 5,
        top_n_stocks: int = 20,
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        戦略実行（エンドツーエンド）

        Args:
            master: 銘柄マスター
            daily_bars: 日次バー
            asof_date: 基準日
            top_k_sectors: 推奨セクター数
            top_n_stocks: 推奨銘柄数

        Returns:
            tuple: (top_sectors, top_stocks)
        """
        # 1. 特徴量計算
        features = self.calculate_features(master, daily_bars, asof_date)

        # 2. フィルタリング
        filtered = self.filter_stocks(features)

        # 3. スコア計算
        scored = self.calculate_stock_score(filtered)

        # 4. セクターランキング
        top_sectors = self.rank_sectors(scored)

        # 5. 推奨銘柄選択
        top_stocks = self.select_top_stocks(
            scored, top_sectors, top_k_sectors, top_n_stocks
        )

        return top_sectors, top_stocks
