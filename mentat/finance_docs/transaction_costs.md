# Transaction costs and turnover

Transaction costs are what a strategy pays to trade: the bid-ask spread, commissions,
and market impact (the price moves against you as you fill a large order). Slippage is
the gap between the expected and the realized execution price.

Turnover is how much a strategy trades per period. High-turnover strategies (e.g.
short-horizon mean reversion) pay costs far more often, so a paper edge can vanish once
realistic costs are charged. The net return is the gross return minus costs times
turnover. A backtest that ignores costs systematically overstates performance; an honest
backtest charges a cost on every position change and reports net, after-cost results.
This is why mentat's trading gate charges a transaction cost on every change in position.
