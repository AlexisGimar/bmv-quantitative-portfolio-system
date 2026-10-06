"""Execute monthly targets one trading day at a time, without inventing quotes."""
import numpy as np


def simulate_period(quotes, target_weights, holdings, cash, last_quotes, cost_rate=0.0):
    """Return updated holdings, cash, valuations and the actual trades for one period.

    quotes includes entry and exit dates. Trade from entry through the day before
    exit; the exit close values this period and belongs to the next rebalance.
    Missing quotes may value existing holdings at their last observed price,
    but may never execute an order. Units are fractional adjusted-price units.
    """
    if not np.isfinite(cost_rate) or not 0 <= cost_rate < 1:
        raise ValueError("Cost rate must be between 0 and 1.")
    if len(quotes) < 2:
        raise ValueError("A period needs separate entry and exit dates.")
    holdings = dict(holdings)
    last_quotes = dict(last_quotes)
    pending = set(holdings) | set(target_weights)
    desired_units = {}
    trades = []
    start_value = None
    waiting_days = 0

    for day, row in quotes.iterrows():
        today = {asset: float(price) for asset, price in row.items()
                 if np.isfinite(price) and price > 0}
        for asset, price in today.items():
            last_quotes[asset] = (price, day)
        value = cash + sum(units * last_quotes[asset][0] for asset, units in holdings.items())
        if start_value is None:
            start_value = value
        if day == quotes.index[-1]:
            break  # Value the exit close without executing next month's orders.

        # Fix the desired units at this order's first executable price.
        # Monthly budgets remain fixed; a new signal replaces unfinished orders.
        for asset in sorted(pending):
            if asset in today and asset not in desired_units:
                budget = start_value * target_weights.get(asset, 0.0)
                desired_units[asset] = budget / today[asset]

        # Sell first. An asset without a quote stays held until it can be sold.
        for asset in sorted(pending):
            if asset not in today:
                continue
            difference = desired_units[asset] - holdings.get(asset, 0.0)
            if difference < -1e-12:
                units = -difference
                notional = units * today[asset]
                cash += notional * (1 - cost_rate)
                holdings[asset] = desired_units[asset]
                trades.append(dict(date=day, asset_id=asset, side="sell",
                                   units=units, price=today[asset], notional=notional,
                                   fee=notional * cost_rate))

        # Share available cash across executable buys; never borrow against a
        # sale that has not happened. Partially filled orders remain pending.
        buys = {asset: max(desired_units[asset] - holdings.get(asset, 0.0), 0.0)
                for asset in sorted(pending) if asset in today}
        required_cash = sum(units * today[asset] * (1 + cost_rate)
                            for asset, units in buys.items())
        fraction = min(1.0, max(cash, 0.0) / required_cash) if required_cash > 0 else 0.0
        for asset, requested in buys.items():
            units = requested * fraction
            if units <= 1e-12:
                continue
            notional = units * today[asset]
            cash -= notional * (1 + cost_rate)
            holdings[asset] = holdings.get(asset, 0.0) + units
            trades.append(dict(date=day, asset_id=asset, side="buy",
                               units=units, price=today[asset], notional=notional,
                               fee=notional * cost_rate))

        pending = {asset for asset in pending if asset not in desired_units
                   or abs(desired_units[asset] - holdings.get(asset, 0.0)) > 1e-12}
        holdings = {asset: units for asset, units in holdings.items() if units > 1e-12}
        if pending:
            waiting_days += 1
        if cash < -1e-10:
            raise ValueError("Execution used more cash than available.")
        cash = max(cash, 0.0)

    end_value = cash + sum(units * last_quotes[asset][0] for asset, units in holdings.items())
    oldest_age = max(((quotes.index[-1] - last_quotes[a][1]).days for a in holdings), default=0)
    return dict(holdings=holdings, cash=cash, last_quotes=last_quotes, trades=trades,
                start_value=start_value, end_value=end_value,
                period_return=end_value / start_value - 1,
                pending_orders=len(pending), waiting_days=waiting_days,
                oldest_quote_days=oldest_age)
