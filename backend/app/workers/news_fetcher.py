from app.db.initializer import initialize_database
from app.db.session import SessionLocal
from app.services.news_ingestion import NewsIngestionService


def main() -> None:
    initialize_database()
    with SessionLocal() as session:
        summary = NewsIngestionService(session).refresh_all()

    print(
        f"news refresh finished: fetched={summary.fetched_count} inserted={summary.inserted_count} "
        f"sources={len(summary.results)}"
    )
    for item in summary.results:
        print(
            f"- {item.source_name}: status={item.status} fetched={item.fetched_count} "
            f"inserted={item.inserted_count} latency_ms={item.latency_ms}"
            + (f" error={item.error}" if item.error else "")
        )


if __name__ == "__main__":
    main()
