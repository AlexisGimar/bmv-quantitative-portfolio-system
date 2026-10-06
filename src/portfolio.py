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

    data = candidates.copy()

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


    return data