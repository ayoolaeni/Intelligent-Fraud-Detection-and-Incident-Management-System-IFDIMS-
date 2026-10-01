"""Insert a model_version row for a trained model bundle (Section 6.1 step 11).

Usage:
    python -m pipeline.register_model --path models/<version> [--activate]

Talks directly to the database via DATABASE_URL (same env var the backend
uses) so it can run standalone, outside the backend container.
"""
from __future__ import annotations

import argparse
import json
import os
import uuid
from pathlib import Path

from sqlalchemy import create_engine, text


def register(model_path: Path, activate: bool, database_url: str) -> str:
    metadata = json.loads((model_path / "metadata.json").read_text())
    algorithm = metadata["algorithm"]
    version = metadata["version"]
    # Stored as just the version folder name, resolved by the backend as
    # ``<MODELS_DIR>/<path>``, so it is portable between the environment
    # this script runs in and the backend container's mounted models volume.
    relative_path = model_path.name

    engine = create_engine(database_url)
    with engine.begin() as conn:
        existing = conn.execute(
            text("SELECT model_id FROM model_version WHERE version = :version"),
            {"version": version},
        ).fetchone()
        if existing:
            model_id = str(existing[0])
            print(f"model_version {version} already registered as {model_id}")
        else:
            model_id = str(uuid.uuid4())
            conn.execute(
                text(
                    "INSERT INTO model_version (model_id, algorithm, version, path, metrics, is_active) "
                    "VALUES (:model_id, :algorithm, :version, :path, :metrics, false)"
                ),
                {
                    "model_id": model_id,
                    "algorithm": algorithm,
                    "version": version,
                    "path": relative_path,
                    "metrics": json.dumps(metadata),
                },
            )
            print(f"Registered model_version {version} as {model_id}")

        if activate:
            conn.execute(text("UPDATE model_version SET is_active = false WHERE is_active = true"))
            conn.execute(
                text(
                    "UPDATE model_version SET is_active = true, deployed_on = now() WHERE model_id = :model_id"
                ),
                {"model_id": model_id},
            )
            print(f"Activated model_version {version}")

    return model_id


def main() -> None:
    parser = argparse.ArgumentParser(description="Register a trained model bundle in the database")
    parser.add_argument("--path", required=True, type=Path)
    parser.add_argument("--activate", action="store_true")
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL"))
    args = parser.parse_args()
    if not args.database_url:
        raise SystemExit("DATABASE_URL must be set (env var or --database-url)")
    register(args.path, args.activate, args.database_url)


if __name__ == "__main__":
    main()
