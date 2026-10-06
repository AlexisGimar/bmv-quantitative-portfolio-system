import numpy as np


def calculate_portfolio_weights(
    candidates,
    method="equal"
):
    """
    Calculate portfolio weights for the selected candidates.

    Supported methods
    -----------------
    equal
        Equal capital allocation across all selected assets.

    category_inverse_volatility
        Category budget is determined by the number of selected
        assets in each category. Within each category, weights
        are inversely proportional to volatility.

    category_score_volatility
        Category budget is determined by the number of selected
        assets in each category. Within each category, weights
        are proportional to positive score divided by volatility.
    """

    allowed = {"equal", "category_inverse_volatility", "category_score_volatility"}
    if method not in allowed:
        raise ValueError(f"Unknown weighting method: {method}")
    data = candidates.copy()
    data["weight"] = 0.0
    if data["asset_id"].duplicated().any():
        raise ValueError("Each candidate must appear only once.")
    if not data.empty and data["asset_type"].isna().any():
        raise ValueError("Each candidate needs an asset category.")

    if data.empty:
        return data


    if method == "equal":

        data["weight"] = (
            1 / len(data)
        )

        return data


    # -----------------------------------------------------
    # Category budget
    # -----------------------------------------------------

    data["category_budget"] = (
        data
        .groupby("asset_type")["asset_id"]
        .transform("count")
        / len(data)
    )


    # -----------------------------------------------------
    # Weighting signal
    # -----------------------------------------------------

    if method == "category_inverse_volatility":

        data["weight_signal"] = (
            1
            / data["volatility_20d_ann"]
        )


    elif method == "category_score_volatility":

        positive_score = (
            data["score"]
            .clip(lower=0)
        )

        data["weight_signal"] = (
            positive_score
            / data["volatility_20d_ann"]
        )


    else:

        raise ValueError(
            f"Unknown weighting method: {method}"
        )


    data["weight_signal"] = (
        data["weight_signal"]
        .replace(
            [np.inf, -np.inf],
            np.nan
        )
    )


    # If one category has unusable volatility or no positive signal,
    # split its budget equally. Other category budgets stay unchanged.
    data["equal_weight_fallback"] = False
    for category, group in data.groupby("asset_type"):
        valid_volatility = (
            np.isfinite(group["volatility_20d_ann"])
            & group["volatility_20d_ann"].gt(0)
        ).all()
        valid_signal = np.isfinite(group["weight_signal"]).all()
        if not valid_volatility or not valid_signal or group["weight_signal"].sum() <= 0:
            data.loc[group.index, "weight_signal"] = 1.0
            data.loc[group.index, "equal_weight_fallback"] = True

    # -----------------------------------------------------
    # Weight inside each category
    # -----------------------------------------------------

    signal_sum = (
        data
        .groupby("asset_type")["weight_signal"]
        .transform("sum")
    )


    data["within_category_weight"] = (
        data["weight_signal"]
        / signal_sum
    )


    # -----------------------------------------------------
    # Final portfolio weight
    # -----------------------------------------------------

    data["weight"] = (
        data["category_budget"]
        * data["within_category_weight"]
    )


    if not (np.isfinite(data["weight"]).all()
            and data["weight"].ge(0).all()
            and np.isclose(data["weight"].sum(), 1.0)):
        raise ValueError("Portfolio weights must be finite, nonnegative and sum to 1.")

    return data