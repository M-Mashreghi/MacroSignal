
# Examples

These files are small synthetic / schema fixtures.

They are not historical research data.

Their purpose is to:
- define import formats,
- support tests,
- let Claude Code implement adapters without needing proprietary datasets.

## Loaders (Task 1.11)

`macrosignal.fixtures` turns each file into canonical domain objects so tests
run without external APIs:

| File | Loader | Returns |
|---|---|---|
| `vintage_fixture.csv` | `load_vintage_fixture` | `MacroObservation` initial print + revision |
| `release_stage_fixture.csv` | `load_release_stage_fixture` | GDP advance/second/third `MacroObservation`s |
| `release_calendar_fixture.csv` | `load_release_calendar_fixture` | `ReleaseEvent`s |
| `ragged_edge_fixture.csv` | `load_ragged_edge_fixture` | `FixtureFeatureRow`s with ages |
| `market_price_fixture.csv` | `load_market_price_fixture` | open/close/adjusted-close `MarketObservation`s (`fixture_asset()` gives matching metadata) |
| `consensus_template.csv` | `load_consensus_fixture` | `ConsensusExpectation`s |
| `state_alignment_fixture.csv` | `load_state_alignment_fixture` | `StateDescriptorRow`s (raw ids permuted between fits) |

Provenance the CSVs do not carry is filled with fixed `FIXTURE_*` values
(source `synthetic_fixture`, retrieval `2026-11-01T00:00Z`, adapter
`fixture-1`). `known_at(observations, t)` is a minimal latest-known-value helper
for tests; the production as-of engine is Task 2.12.
