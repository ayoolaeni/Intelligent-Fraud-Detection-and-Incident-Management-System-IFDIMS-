.PHONY: up down data train seed-demo stream demo test loadtest uat-summary

PYTHON ?= python
API_URL ?= http://localhost:8000
API_KEY ?= sim-key-change-me
DATABASE_URL ?= postgresql+psycopg://ifdims:ifdims@localhost:5432/ifdims

up:
	docker compose up --build -d

down:
	docker compose down

data:
	cd ml && $(PYTHON) -m generator.generate_synthetic --out ../data/synthetic/train --customers 5000 --days 90 --seed 42 --fraud-rate 0.005 --label-noise-rate 0.02
	cd ml && $(PYTHON) -m generator.generate_synthetic --out ../data/synthetic/demo  --customers 1000 --days 60 --seed 7  --fraud-rate 0.02
	cd ml && $(PYTHON) -m pipeline.build_features --in ../data/synthetic/train --out ../data/processed/train_features.parquet

train:
	cd ml && $(PYTHON) -m pipeline.train --features ../data/processed/train_features.parquet --meta ../data/processed/feature_meta.json --out-dir ../models
	cd ml && $(PYTHON) -m pipeline.evaluate --model-dir $$(ls -d ../models/*/ | sort | tail -1) --reports-dir ../reports
	cd ml && $(PYTHON) -m pipeline.benchmark_public --raw-dir ../data/raw --reports-dir ../reports
	cd ml && $(PYTHON) -m pipeline.register_model --path $$(ls -d ../models/*/ | sort | tail -1) --activate --database-url $(DATABASE_URL)

seed-demo:
	$(PYTHON) -m simulator.seed_history --world data/synthetic/demo --anchor-now --database-url $(DATABASE_URL)

stream:
	$(PYTHON) -m simulator.stream --world data/synthetic/demo --api-url $(API_URL) --api-key $(API_KEY) --rate 5

demo: up data train seed-demo
	$(PYTHON) -m simulator.stream --world data/synthetic/demo --api-url $(API_URL) --api-key $(API_KEY) --rate 5 --limit 2000

test:
	cd ml && $(PYTHON) -m pytest --cov=fraud_core --cov-report=term-missing
	cd backend && $(PYTHON) -m pytest --cov=app --cov-report=term-missing
	cd frontend && npm test

loadtest:
	mkdir -p reports
	SIM_API_KEY=$(API_KEY) locust -f loadtest/locustfile.py --host $(API_URL) --headless -u 20 -r 5 -t 5m --csv reports/loadtest
	$(PYTHON) -m loadtest.summarize --stats-csv reports/loadtest_stats.csv --out reports/loadtest_summary.md

uat-summary:
	$(PYTHON) scripts/uat_summary.py --responses reports/uat_responses.csv --out reports/uat_summary.csv
