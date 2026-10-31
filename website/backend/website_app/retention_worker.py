"""Dedicated retention loop, independent of the news publication switch."""
import logging
import signal
import threading
from website_app.db import get_sessionmaker
from website_app.consultations import enabled, cipher, purge_expired

def run():
    if not enabled(): raise SystemExit('咨询登记未启用，未清理资料')
    cipher()
    stop = threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT): signal.signal(sig, lambda *_: stop.set())
    logging.basicConfig(level=logging.INFO)
    while not stop.is_set():
        try:
            with get_sessionmaker()() as db:
                count = purge_expired(db)
                db.commit()
                if count: logging.info('Expired consultation records removed: %s', count)
            stop.wait(0.1 if count >= 100 else 60)
        except Exception as exc:
            logging.error('Consultation cleanup failed (%s); transaction rolled back', type(exc).__name__)
            stop.wait(20)

if __name__ == '__main__': run()
