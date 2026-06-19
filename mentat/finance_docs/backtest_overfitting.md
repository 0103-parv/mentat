# Backtest overfitting and multiple testing

Backtest overfitting happens when a strategy is tuned (knowingly or not) to fit the
noise in a historical sample, so it looks profitable in-sample but fails out-of-sample.
The more configurations you try, the more likely you are to find one that fit the past
by chance. This is the multiple-testing problem applied to trading.

Defenses: evaluate on a held-out out-of-sample window the strategy never saw; test
across multiple market regimes and take the worst; charge realistic transaction costs;
and apply a multiple-testing correction such as the deflated Sharpe ratio. Lopez de
Prado argues most published backtests are false discoveries because they ignore the
number of trials. The honest rule: a strategy is believed only if it survives
out-of-sample, after costs, after deflation for the number of trials.
