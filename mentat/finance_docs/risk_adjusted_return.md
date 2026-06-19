# Risk-adjusted return: Sharpe and deflated Sharpe

The Sharpe ratio measures risk-adjusted return: the mean excess return of a strategy
divided by the standard deviation of its returns, usually annualized by multiplying the
per-period Sharpe by the square root of the number of periods per year (about 252 for
daily data). A higher Sharpe means more return per unit of risk.

A backtested Sharpe ratio is biased upward when many strategies are tried, because the
best of N random strategies looks good by luck alone. The Deflated Sharpe Ratio (Bailey
and Lopez de Prado, 2014) corrects for this: it discounts the observed Sharpe by the
Sharpe a lucky null strategy would be expected to reach over N independent trials, given
the number of observations. An edge is only credible if its Sharpe survives this
deflation. This is the core anti-overfit discipline used in mentat's trading gate.
