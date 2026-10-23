
# Deployment / Research Environment

## Local

Python 3.11+.

Use a virtual environment.

## Dashboard

Local Streamlit is sufficient for v1.

## Secrets

API keys must live in environment variables or `.env`.

Never commit them.

## CI

Run:
- lint,
- unit tests,
- PIT tests,
- backtest integrity fixtures,
- project validation.

## Reproducible Demo

The repository must include enough synthetic/permitted fixture data for CI and
clean-clone tests even when external APIs are unavailable.
