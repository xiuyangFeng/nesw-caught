from app.db.initializer import initialize_database
from app.main import build_market_quote_producer, register_market_watchlist_handlers
from app.services.event_bus import build_event_bus, set_event_bus


def main() -> None:
    initialize_database()
    event_bus = build_event_bus()
    set_event_bus(event_bus)
    register_market_watchlist_handlers(event_bus)
    producer = build_market_quote_producer(event_bus)
    producer.run_forever()


if __name__ == "__main__":
    main()
