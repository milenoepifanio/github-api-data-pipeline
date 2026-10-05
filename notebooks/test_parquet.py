from pathlib import Path

import pandas as pd


parquet_directory = Path("data/raw/commits")

parquet_files = list(
    parquet_directory.rglob("*.parquet")
)

if not parquet_files:
    raise FileNotFoundError(
        "No Parquet files found in data/raw/commits."
    )

parquet_path = max(
    parquet_files,
    key=lambda file: file.stat().st_mtime
)


print("=== PARQUET FILE ===")
print(parquet_path)


df = pd.read_parquet(
    parquet_path
)


print("\n=== PARQUET VALIDATION ===")

print("\nSchema:")
df.info()

print("\nColumns:")
print(df.columns.tolist())

print("\nRecords:")
print(len(df))

print("\nSample:")
print(df.head())