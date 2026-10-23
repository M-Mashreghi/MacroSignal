
# Return & Execution Rules

Every asset has:
- tradable lifecycle,
- provider,
- price field semantics,
- adjustment policy,
- currency,
- timezone.

Every backtest has:
- signal time,
- decision time,
- execution time,
- execution price,
- marking price,
- cash return assumption.

Do not use an ETF before inception.

Do not mix adjusted-close returns with unadjusted execution prices without an
explicit reconciliation policy.

Daily event studies and daily strategy backtests are different research objects.
