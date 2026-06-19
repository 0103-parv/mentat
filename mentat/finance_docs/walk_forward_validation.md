# Walk-forward and out-of-sample validation

Out-of-sample (OOS) testing evaluates a strategy on data it was never tuned on, which is
the only honest estimate of future performance. Walk-forward analysis formalizes this:
fit or select on an in-sample window, test on the next out-of-sample window, then roll
both windows forward and repeat. This mimics how a strategy would actually be deployed
and re-fit over time.

Plain k-fold cross-validation is unsafe for time series because shuffling leaks the
future into the past. Lopez de Prado's purged and embargoed cross-validation removes
training samples that overlap with the test labels (purging) and adds a gap (embargo) to
prevent leakage from serial correlation. Across multiple regimes, taking the worst OOS
window is a conservative, honest estimate. The rule throughout: judge a strategy by what
it does out-of-sample, after costs, corrected for the number of trials, never in-sample.
