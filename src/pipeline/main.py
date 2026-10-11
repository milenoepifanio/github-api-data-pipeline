from src.pipeline.commits import CommitsPipeline
from src.pipeline.resources import ResourcesPipeline


def main() -> None:
    owner = "milenoepifanio"
    repository = "github-api-data-pipeline"

    print("\n=== GITHUB API DATA PIPELINE ===")

    print("\n[1/2] Running Commits Pipeline")

    commits_pipeline = CommitsPipeline(
        owner=owner,
        repository=repository
    )

    commits_pipeline.run()

    print("\n[2/2] Running Resources Pipeline")

    resources_pipeline = ResourcesPipeline(
        owner=owner,
        repository=repository
    )

    resources_pipeline.run()

    print("\n=== PIPELINE EXECUTION COMPLETED ===")


if __name__ == "__main__":
    main()