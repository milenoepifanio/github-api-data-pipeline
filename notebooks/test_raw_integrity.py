
import json
from pathlib import Path

import pandas as pd


RAW_PATH = Path("data/raw")

ENTITY_CONFIG = {
    "commits": {
        "key": "sha",
        "required_columns": [
            "sha",
            "message",
            "commit_date",
            "ingestion_timestamp",
        ],
    },
    "repositories": {
        "key": "id",
        "required_columns": [
            "id",
            "name",
            "full_name",
            "owner_login",
            "ingestion_timestamp",
        ],
    },
    "issues": {
        "key": "id",
        "required_columns": [
            "id",
            "number",
            "title",
            "state",
            "ingestion_timestamp",
        ],
    },
    "pull_requests": {
        "key": "id",
        "required_columns": [
            "id",
            "number",
            "title",
            "state",
            "ingestion_timestamp",
        ],
    },
}


def load_json(path):
    with path.open(
        mode="r",
        encoding="utf-8",
    ) as file:
        data = json.load(file)

    assert isinstance(data, list), (
        f"Expected a list of records: {path}"
    )

    return data


def get_identifiers(records, key):
    identifiers = []

    for record in records:
        assert isinstance(record, dict), (
            "Each record must be a dictionary."
        )

        identifier = record.get(key)

        assert identifier is not None, (
            f"Missing identifier: {key}"
        )

        identifiers.append(str(identifier))

    assert len(identifiers) == len(set(identifiers)), (
        f"Duplicate identifiers found: {key}"
    )

    return set(identifiers)


def find_matching_files(entity, key):
    entity_path = RAW_PATH / entity

    json_files = sorted(
        entity_path.glob("ingestion_date=*/*.json"),
        key=lambda path: path.stat().st_mtime_ns,
        reverse=True,
    )

    parquet_files = sorted(
        entity_path.glob("ingestion_date=*/*.parquet"),
        key=lambda path: path.stat().st_mtime_ns,
        reverse=True,
    )

    assert json_files, (
        f"No JSON files found for {entity}"
    )

    assert parquet_files, (
        f"No Parquet files found for {entity}"
    )

    # Match files by record identifiers, rather than
    # relying on identical ingestion timestamps.
    #
    # Restrict matching to the same ingestion partition
    # and file prefix to avoid unrelated datasets.

    for json_path in json_files:
        json_records = load_json(json_path)

        if not json_records:
            continue

        json_ids = get_identifiers(json_records, key)

        json_prefix = json_path.stem.rsplit("_", 1)[0]

        for parquet_path in parquet_files:
            if parquet_path.parent != json_path.parent:
                continue

            parquet_prefix = (
                parquet_path.stem.rsplit("_", 1)[0]
            )

            if parquet_prefix != json_prefix:
                continue

            dataframe = pd.read_parquet(parquet_path)

            if key not in dataframe.columns:
                continue

            parquet_ids = get_identifiers(
                dataframe[[key]].to_dict("records"),
                key,
            )

            if (
                len(json_records) == len(dataframe)
                and json_ids == parquet_ids
            ):
                return (
                    json_path,
                    parquet_path,
                    json_records,
                    dataframe,
                )

    raise AssertionError(
        f"No matching JSON/Parquet pair found for {entity}"
    )


def validate_entity(entity, config):
    print(f"\n=== {entity.upper()} ===")

    key = config["key"]

    (
        json_path,
        parquet_path,
        json_records,
        dataframe,
    ) = find_matching_files(entity, key)

    assert not dataframe.empty, (
        f"Parquet is empty: {entity}"
    )

    missing_columns = [
        column
        for column in config["required_columns"]
        if column not in dataframe.columns
    ]

    assert not missing_columns, (
        f"Missing columns for {entity}: {missing_columns}"
    )

    assert dataframe[key].notna().all(), (
        f"Null identifiers found for {entity}"
    )

    assert not dataframe[key].duplicated().any(), (
        f"Duplicate identifiers found for {entity}"
    )

    assert dataframe["ingestion_timestamp"].notna().all(), (
        f"Null ingestion timestamps found for {entity}"
    )

    print("JSON reading: OK")
    print("Parquet reading: OK")
    print("Required columns: OK")
    print("Identifier uniqueness: OK")
    print("JSON/Parquet consistency: OK")
    print("Ingestion timestamps: OK")

    print(f"Records: {len(dataframe)}")
    print(f"Columns: {len(dataframe.columns)}")
    print(f"JSON: {json_path}")
    print(f"Parquet: {parquet_path}")

    return {
        "entity": entity,
        "records": len(dataframe),
        "columns": len(dataframe.columns),
        "status": "PASS",
    }


def main():
    print("\n=== RAW DATA INTEGRITY TEST ===")

    assert RAW_PATH.exists(), (
        f"Raw directory not found: {RAW_PATH}"
    )

    results = []

    for entity, config in ENTITY_CONFIG.items():
        result = validate_entity(
            entity=entity,
            config=config,
        )

        results.append(result)

    print("\n=== VALIDATION SUMMARY ===")

    summary = pd.DataFrame(results)

    print(
        summary.to_string(index=False)
    )

    print("\nAll Raw integrity checks passed.")


if __name__ == "__main__":
    main()
