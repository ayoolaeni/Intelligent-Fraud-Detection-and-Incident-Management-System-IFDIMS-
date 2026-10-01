# simulator

Plays the role of the bank's channels for demonstration purposes (Section
17). Needs `data/synthetic/demo/` to exist (`make data` or run the
generator directly with a `demo` output directory).

```bash
pip install -r requirements.txt

# Load the first 45 days of the demo world as history, shifting all
# timestamps so day 46 starts "now":
python -m seed_history --world ../data/synthetic/demo --anchor-now --database-url <postgres-url>

# Stream the rest of the demo world to the live scoring API in time order:
python -m stream --world ../data/synthetic/demo --api-url http://localhost:8000 \
    --api-key <one of SERVICE_API_KEYS> --rate 5
```

`stream.py` writes `reports/demo_stream_results.csv` and prints a confusion
matrix comparing the model's risk band against the (hidden, ground-truth)
`is_fraud` label from the generator.
