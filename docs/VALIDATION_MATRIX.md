
# Validation Matrix

| Risk | Guard | Blocking |
|---|---|---:|
| Revised macro leakage | PIT vintage/as-of tests | Yes |
| Date-only treated as exact time | availability precision resolver | Yes |
| Release timestamp leakage | available_at gate | Yes |
| Stale macro value treated as fresh | ragged-edge age/stale fields | Yes |
| Future scaler/PCA leakage | fit-cutoff tests | Yes |
| HMM smoothing leakage | filtered-only signal interface | Yes |
| HMM/GMM state permutation | state alignment layer | Yes |
| ETF used before inception | asset lifecycle gate | Yes |
| Return convention mismatch | return contract validator | Yes |
| Same-bar impossible fill | execution-policy test | Yes |
| Cash return omitted | explicit cash policy | Yes |
| Missing consensus fabricated | expectation validator | Yes |
| Intraday claim from daily prices | granularity guard | Yes |
| Overlapping macro releases | event cluster flag | Warning/Policy |
| Invalid portfolio weights | weight validator | Yes |
| Costs omitted | net-performance requirement | Yes |
| Test-period tuning | search/split audit | Yes |
| Snapshot drift | snapshot hash regression | Yes |
| Hidden local dependency | clean-clone test | Yes |
