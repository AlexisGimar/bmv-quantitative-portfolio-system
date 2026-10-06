import numpy as np
import pandas as pd


DEFAULT_FRESHNESS_LIMITS = {
    "STOCK": 4,
    "ETF": 4,
    "FUND": 7
}


FACTOR_COLUMNS = [
    "momentum_5d",
    "momentum_20d",
    "momentum_60d",
    "volatility_20d_ann",
    "current_drawdown"
]

RESTRICTED_SYMBOLS = {
    "SOXL",
    "SOXS",
    "SPXL",
    "TECL",
    "QLD",
    "TQQQ",
    "ANGELD",
    "SQQQ",
    "FAZ",
    "FAS",
    "SPXS",
    "TECS",
    "TNA",
    "TZA"
}

def safe_zscore(series):
    """
    Cross-sectional z-score robust to zero variance.
    """

    std = series.std()

    if (
        pd.isna(std)
        or np.isclose(std, 0)
    ):
        return pd.Series(
            0.0,
            index=series.index
        )

    return (
        series - series.mean()
    ) / std


def build_universe(
    prices,
    evaluation_date,
    momentum_weight=1/3,
    volatility_weight=1/3,
    drawdown_weight=1/3,
    freshness_limits=None,
    max_zero_volume_rate=0.50,
    rejections=None
):
    """
    Build the eligible and scored cross-sectional universe
    at a specific historical evaluation date.

    Features are sliced through evaluation_date. Provider history may be revised.
    """

    if not all(np.isfinite(w) and w >= 0 for w in
               [momentum_weight, volatility_weight, drawdown_weight]):
        raise ValueError("Score weights must be finite and nonnegative.")

    weight_sum = (
        momentum_weight
        + volatility_weight
        + drawdown_weight
    )

    if not np.isclose(
        weight_sum,
        1.0
    ):
        raise ValueError(
            "Score weights must sum to 1."
        )

    if freshness_limits is None:
        freshness_limits = (
            DEFAULT_FRESHNESS_LIMITS
        )

    evaluation_date = pd.Timestamp(
        evaluation_date
    )

    # -----------------------------------------------------
    # Use only information available at evaluation date
    # -----------------------------------------------------

    historical = prices[
        prices["date"]
        <= evaluation_date
    ]

    latest = (
        historical
        .sort_values(
            ["asset_id", "date"]
        )
        .groupby("asset_id")
        .tail(1)
        .copy()
    )

    # -----------------------------------------------------
    # Freshness
    # -----------------------------------------------------

    latest["stale_days"] = (
        evaluation_date
        - latest["date"]
    ).dt.days

    latest["freshness_limit"] = (
        latest["asset_type"]
        .map(freshness_limits)
    )

    latest["fresh_data"] = (
        latest["stale_days"]
        <= latest["freshness_limit"]
    )

    # -----------------------------------------------------
    # Factor availability
    # -----------------------------------------------------

    latest["factors_complete"] = (
        latest[FACTOR_COLUMNS]
        .notna()
        .all(axis=1)
    )

    latest["factors_finite"] = (
        np.isfinite(
            latest[FACTOR_COLUMNS]
        ).all(axis=1)
    )

    # -----------------------------------------------------
    # Data quality
    # -----------------------------------------------------

    latest["data_quality_ok"] = (
        latest["extreme_return_60d"]
        == 0
    )

    if "invalid_history_252d" in latest.columns:
        latest["data_quality_ok"] &= latest["invalid_history_252d"].eq(0)
    if "pending_rejections" in latest.columns:
        # Current screener only: this count describes today's unresolved issues.
        latest["data_quality_ok"] &= latest["pending_rejections"].eq(0)
    if rejections is not None:
        # Historical screening: never apply a rejection from a future market date.
        dated = rejections[rejections["date"] <= evaluation_date]
        latest["data_quality_ok"] &= ~latest["asset_id"].isin(dated["asset_id"])

    # -----------------------------------------------------
    # Liquidity
    # -----------------------------------------------------

    latest["liquidity_ok"] = (
        (
            latest["zero_volume_rate_20d"]
            <= max_zero_volume_rate
        )
        |
        (
            latest["asset_type"]
            == "FUND"
        )
    )

    # -----------------------------------------------------
    # Valid Assets
    # -----------------------------------------------------

    latest["competition_eligible"] = (
        ~latest["actinver_symbol"]
        .isin(RESTRICTED_SYMBOLS)
    )

    # -----------------------------------------------------
    # Eligibility
    # -----------------------------------------------------

    latest["eligible"] = (
        latest["fresh_data"]
        & latest["factors_complete"]
        & latest["factors_finite"]
        & latest["data_quality_ok"]
        & latest["liquidity_ok"]
        & latest["competition_eligible"]
    )

    universe = latest[
        latest["eligible"]
    ].copy()

    # -----------------------------------------------------
    # Cross-sectional standardization
    # -----------------------------------------------------

    for column in FACTOR_COLUMNS:

        universe[f"z_{column}"] = (
            universe
            .groupby("asset_type")[column]
            .transform(safe_zscore)
            .clip(-3, 3)
        )

    # -----------------------------------------------------
    # Momentum block
    # -----------------------------------------------------

    universe["momentum_factor"] = (
        universe[
            [
                "z_momentum_5d",
                "z_momentum_20d",
                "z_momentum_60d"
            ]
        ]
        .mean(
            axis=1,
            skipna=False
        )
    )

    # -----------------------------------------------------
    # Multifactor score
    # -----------------------------------------------------

    universe["score"] = (
          momentum_weight
          * universe["momentum_factor"]

        - volatility_weight
          * universe["z_volatility_20d_ann"]

        + drawdown_weight
          * universe["z_current_drawdown"]
    )

    # -----------------------------------------------------
    # Ranking within asset category
    # -----------------------------------------------------

    universe["category_rank"] = (
        universe
        .groupby("asset_type")["score"]
        .rank(
            ascending=False,
            method="min"
        )
    )

    universe["category_percentile"] = (
        universe
        .groupby("asset_type")["score"]
        .rank(
            ascending=True,
            pct=True
        )
    )

    return universe


def select_candidates(
    universe,
    cutoff=0.90
):
    """
    Select assets above the required percentile within
    their respective asset category.
    """

    return (
        universe[
            universe["category_percentile"]
            >= cutoff
        ]
        .sort_values(
            [
                "asset_type",
                "category_rank"
            ]
        )
        .copy()
    )

def select_candidates_with_buffer(
    universe,
    previous_assets=None,
    entry_cutoff=0.90,
    exit_cutoff=0.80
):
    """
    Select candidates using a hysteresis buffer.

    New assets enter when their percentile is at or above
    entry_cutoff.

    Existing holdings remain in the portfolio while their
    percentile stays at or above exit_cutoff.
    """

    previous_assets = set(
        previous_assets or []
    )

    data = universe.copy()

    new_entries = (
        data["category_percentile"]
        >= entry_cutoff
    )

    existing_holdings = (
        data["asset_id"]
        .isin(previous_assets)
        &
        (
            data["category_percentile"]
            >= exit_cutoff
        )
    )

    selected = (
        new_entries
        | existing_holdings
    )

    return (
        data[selected]
        .sort_values(
            [
                "asset_type",
                "category_rank"
            ]
        )
        .copy()
    )