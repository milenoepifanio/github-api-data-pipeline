from src.pipeline.commits import CommitsPipeline


pipeline = CommitsPipeline(
    owner="milenoepifanio",
    repository="github-api-data-pipeline"
)

pipeline.run()