"""Durable publication worker. Safe with multiple processes; browser may be closed."""
import logging
import os
import signal
import threading
from website_app.db import get_sessionmaker
from website_app.news.service import publish_due, dispatch, now
from website_app.consultations import purge_expired

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
            # A separate transaction keeps retention failures from undoing news.
            try:
                with factory() as db:
                    removed = purge_expired(db)
                    db.commit()
                    if removed: log.info('Expired consultation records removed: %s', removed)
            except Exception as cleanup_error:
                log.error('Consultation expiry cleanup failed (%s)', type(cleanup_error).__name__)
            stop.wait(0.1 if count>=50 else 10)
        except Exception as exc:
            # Transaction rollback on failure. Next iteration retries the same durable rows.
            log.error("Publication failed (%s); transaction rolled back and will retry", type(exc).__name__)
            try:
                with factory() as db:
                    gate = dispatch(db)
                    gate.last_error = '自动发布执行失败，事务已撤销，系统将重试。'
                    gate.heartbeat_at = now()
                    db.commit()
            except Exception:
                log.error('Publication failure status could not be persisted')
            stop.wait(20)

if __name__ == "__main__": run()
