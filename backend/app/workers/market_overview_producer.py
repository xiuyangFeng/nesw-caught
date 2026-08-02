from app.db.initializer import initialize_database
from app.main import build_market_overview_producer

# 独立进程入口:默认(单机单进程)场景下 overview producer 已随 app.main 的
# lifespan 一起启停,不需要跑这个模块。仅在多进程部署场景下使用——启动前先把
# MARKET_OVERVIEW_PRODUCER_ENABLED=false 关掉进程内 producer,避免双跑重复轮询。
# overview producer 不发布 event_bus 事件,因此这里不需要 build/set event bus。


def main() -> None:
    initialize_database()
    producer = build_market_overview_producer()
    producer.run_forever()


if __name__ == "__main__":
    main()
