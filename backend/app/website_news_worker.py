"""Durable publication worker. Safe with multiple processes; browser may be closed."""
import logging
import os
import signal
import threading
from app.db.session import get_sessionmaker
from app.services.website_news.service import publish_due

log=logging.getLogger("website-news-worker")

def run():
    stop=threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT): signal.signal(sig, lambda *_: stop.set())
    logging.basicConfig(level=logging.INFO)
    factory=get_sessionmaker()
    # Only explicit deployment configuration can start the publishing loop.
    if os.getenv("WEBSITE_NEWS_WORKER_ENABLED", "false").lower() != "true":
        raise SystemExit("WEBSITE_NEWS_WORKER_ENABLED 未启用；未发布任何文章")
    while not stop.is_set():
        try:
            with factory() as db:
                if db.get_bind().dialect.name != "mysql": raise RuntimeError("MySQL required")
                count=publish_due(db)
                db.commit()
                if count: log.info("Published %s approved news articles", count)
            stop.wait(0.1 if count>=50 else 10)
        except Exception:
            # Transaction rollback on failure. Next iteration retries the same durable rows.
            log.exception("Publication failed; transaction rolled back and will retry")
            stop.wait(20)

if __name__ == "__main__": run()
