import logging

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.initializer import initialize_database
from app.db.session import SessionLocal
from app.services.news_ingestion import NewsIngestionService

logger = logging.getLogger(__name__)


def main() -> None:
    # 独立脚本入口（`make ingest-news`），不经过 app.main 的 lifespan，因此需要
    # 自行接上项目统一的日志配置，否则下面的 logger 调用在默认 root logger
    # （无 handler）下会被静默吞掉，脚本变成没有任何输出。
    settings = get_settings()
    configure_logging(
        settings.log_level,
        file_enabled=settings.log_file_enabled,
        file_path=settings.log_file_path,
        file_max_bytes=settings.log_file_max_bytes,
        file_backup_count=settings.log_file_backup_count,
        log_format=settings.log_format,
    )
    initialize_database()
    with SessionLocal() as session:
        summary = NewsIngestionService(session).refresh_all()

    logger.info(
        "news refresh finished: fetched=%s inserted=%s sources=%s",
        summary.fetched_count,
        summary.inserted_count,
        len(summary.results),
    )
    for item in summary.results:
        logger.info(
            "- %s: status=%s fetched=%s inserted=%s latency_ms=%s%s",
            item.source_name,
            item.status,
            item.fetched_count,
            item.inserted_count,
            item.latency_ms,
            f" error={item.error}" if item.error else "",
        )


if __name__ == "__main__":
    main()
