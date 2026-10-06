import numpy as np
import pandas as pd


def calculate_features(prices):
    """
    Calculate historical quantitative features for each asset.

    Expected columns:
        date
        asset_id
        adjusted_close
        volume

    Returns
    -------
    pandas.DataFrame
        Original data with return, momentum, volatility,
        drawdown, liquidity and data-quality features.
    """

    data = (
        prices
        .sort_values(
            ["asset_id", "date"]
        )
        .copy()
    )

    data["date"] = pd.to_datetime(data["date"], errors="raise")
    if data["date"].isna().any() or data.duplicated(["asset_id", "date"]).any():
        raise ValueError("Prices need valid, unique dates for each asset.")

    price_columns = ["adjusted_close"]
    if "close" in data.columns:
        price_columns.append("close")
    for column in price_columns + ["volume"]:
        data[column] = pd.to_numeric(data[column], errors="coerce")
    valid_prices = (np.isfinite(data[price_columns]) & data[price_columns].gt(0)).all(axis=1)
    valid_volume = np.isfinite(data["volume"]) & data["volume"].ge(0)
    data["invalid_observation"] = ~(valid_prices & valid_volume)
    data.loc[data["invalid_observation"], "adjusted_close"] = np.nan

    # A bad observation keeps this asset out until it leaves the 252-row window.
    data["invalid_history_252d"] = (
        data.groupby("asset_id")["invalid_observation"]
        .transform(lambda x: x.rolling(252, min_periods=1).sum())
    )

    # -----------------------------------------------------
    # Daily returns
    # -----------------------------------------------------

    data["return_1d"] = (
        data
        .groupby("asset_id")["adjusted_close"]
        .pct_change(
            fill_method=None
        )
    )

    # -----------------------------------------------------
    # Momentum
    # -----------------------------------------------------

    for window in [5, 20, 60]:

        data[f"momentum_{window}d"] = (
            data
            .groupby("asset_id")["adjusted_close"]
            .pct_change(
                periods=window,
                fill_method=None
            )
        )

    # -----------------------------------------------------
    # Annualized rolling volatility
    # -----------------------------------------------------

    data["volatility_20d_ann"] = (
        data
        .groupby("asset_id")["return_1d"]
        .transform(
            lambda x: x.rolling(
                window=20,
                min_periods=20
            ).std()
        )
        * np.sqrt(252)
    )

    # -----------------------------------------------------
    # 252-observation current drawdown
    # -----------------------------------------------------

    data["rolling_max_252d"] = (
        data
        .groupby("asset_id")["adjusted_close"]
        .transform(
            lambda x: x.rolling(
                window=252,
                min_periods=252
            ).max()
        )
    )

    data["current_drawdown"] = (
        data["adjusted_close"]
        / data["rolling_max_252d"]
        - 1
    )

    # -----------------------------------------------------
    # Liquidity
    # -----------------------------------------------------

    data["zero_volume"] = (
        data["volume"] == 0
    ).astype(int)

    data["zero_volume_rate_20d"] = (
        data
        .groupby("asset_id")["zero_volume"]
        .transform(
            lambda x: x.rolling(
                window=20,
                min_periods=20
            ).mean()
        )
    )

    # -----------------------------------------------------
    # Recent extreme-return events
    # -----------------------------------------------------

    data["extreme_return"] = (
        data["return_1d"]
        .abs()
        .gt(1)
        .fillna(False)
        .astype(int)
    )

    data["extreme_return_60d"] = (
        data
        .groupby("asset_id")["extreme_return"]
        .transform(
            lambda x: x.rolling(
                window=60,
                min_periods=60
            ).sum()
        )
    )

    return data