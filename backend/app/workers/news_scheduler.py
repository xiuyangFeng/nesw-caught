from app.core.config import get_settings
from app.db.initializer import initialize_database
from app.db.session import SessionLocal
from app.services.event_bus import build_event_bus, set_event_bus
from app.services.news_ingest_scheduler import NewsIngestScheduler


def main() -> None:
    initialize_database()
    set_event_bus(build_event_bus())
    settings = get_settings()
    scheduler = NewsIngestScheduler(
        session_factory=SessionLocal,
        tick_seconds=settings.news_scheduler_tick_seconds,
        max_backoff_multiplier=settings.news_backoff_max_multiplier,
    )
    scheduler.run_forever()


if __name__ == "__main__":
    main()
