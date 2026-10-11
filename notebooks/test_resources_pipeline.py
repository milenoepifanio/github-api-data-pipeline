from src.pipeline.resources import ResourcesPipeline


def main() -> None:

    pipeline = ResourcesPipeline(
        owner="milenoepifanio",
        repository="github-api-data-pipeline"
    )

    pipeline.run()


if __name__ == "__main__":
    main()