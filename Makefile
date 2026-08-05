demo-baseline:
	uv run dbt seed --project-dir demo/sonicledger --profiles-dir demo/sonicledger
	uv run dbt build --project-dir demo/sonicledger --profiles-dir demo/sonicledger

datahub-up:
	scripts/start_datahub.sh

datahub-down:
	scripts/stop_datahub.sh

datahub-seed:
	uv run python scripts/seed_datahub.py
