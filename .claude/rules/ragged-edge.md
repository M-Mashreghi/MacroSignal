
# Ragged-Edge Rules

A daily macro feature panel is asynchronous.

Every feature row exposes:
- value,
- available_at,
- reference period,
- age since availability,
- reference age,
- stale flag.

Do not blindly forward-fill and forget age.

Feature staleness thresholds must be configurable by series/family.

Models must not treat stale and freshly released information as equivalent unless
the specification explicitly says so.
