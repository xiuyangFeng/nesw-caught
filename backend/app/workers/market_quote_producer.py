from app.db.initializer import initialize_database
from app.main import build_market_quote_producer, register_market_watchlist_handlers
from app.services.event_bus import build_event_bus, set_event_bus

# 独立进程入口:默认(单机单进程)场景下 producer 已随 app.main 的 lifespan 一起
# 启停,不需要跑这个模块。仅在多进程部署场景下使用——启动前先把
# MARKET_QUOTE_PRODUCER_ENABLED=false 关掉进程内 producer,避免双跑重复轮询。


def main() -> None:
    initialize_database()
    event_bus = build_event_bus()
    set_event_bus(event_bus)
    register_market_watchlist_handlers(event_bus)
    producer = build_market_quote_producer(event_bus)
    producer.run_forever()


if __name__ == "__main__":
    main()
