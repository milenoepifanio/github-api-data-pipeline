
import time

from src.pipeline.commits import CommitsPipeline
from src.pipeline.resources import ResourcesPipeline
from src.utils.logger import get_logger


logger = get_logger(__name__)


def main() -> None:
    """
    Main entry point for the GitHub API Data Pipeline.

    Executes:
        1. Commits Pipeline
        2. Resources Pipeline

    Tracks:
        - Pipeline execution status
        - Execution duration
        - Pipeline failures
    """

    owner = "milenoepifanio"
    repository = "github-api-data-pipeline"

    start_time = time.perf_counter()

    logger.info(
        "GitHub API Data Pipeline started | "
        "Owner=%s | Repository=%s",
        owner,
        repository
    )

    try:

        # ==========================================
        # STEP 1 - COMMITS
        # ==========================================

        logger.info(
            "[1/2] Starting Commits Pipeline"
        )

        commits_pipeline = CommitsPipeline(
            owner=owner,
            repository=repository
        )

        commits_pipeline.run()

        logger.info(
            "[1/2] Commits Pipeline completed"
        )

        # ==========================================
        # STEP 2 - RESOURCES
        # ==========================================

        logger.info(
            "[2/2] Starting Resources Pipeline"
        )

        resources_pipeline = ResourcesPipeline(
            owner=owner,
            repository=repository
        )

        resources_pipeline.run()

        logger.info(
            "[2/2] Resources Pipeline completed"
        )

        # ==========================================
        # EXECUTION SUMMARY
        # ==========================================

        duration = (
            time.perf_counter() - start_time
        )

        logger.info(
            "GitHub API Data Pipeline completed | "
            "Status=SUCCESS | Duration=%.2fs",
            duration
        )

    except Exception:

        duration = (
            time.perf_counter() - start_time
        )

        logger.exception(
            "GitHub API Data Pipeline failed | "
            "Status=FAILED | Duration=%.2fs",
            duration
        )

        raise


if __name__ == "__main__":
    main()
