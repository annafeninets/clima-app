"""Application entry point."""

import logging
import os
import signal
from threading import Thread

from clima.boundaries.http_gateway import ClimaHTTPServer, create_handler
from clima.config import Config
from clima.container import Application

logger = logging.getLogger("clima")


def _warn_about_configuration() -> None:
    if not os.environ.get("CLIMA_VAPID_PRIVATE_KEY"):
        logger.warning("CLIMA_VAPID_PRIVATE_KEY не задан: push-уведомления отключены")
    if not os.environ.get("CLIMA_SCHEDULER_TOKEN"):
        logger.warning(
            "CLIMA_SCHEDULER_TOKEN не задан: ручной запуск /internal/scheduler/morning недоступен"
        )


def main() -> None:
    config = Config.from_env()
    logging.basicConfig(
        level=config.logLevel,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    _warn_about_configuration()
    application = Application(databasePath=config.dbPath, photoRoot=config.photoRoot)
    server = ClimaHTTPServer(
        (config.host, config.port), create_handler(application, config.corsOrigins)
    )
    scheduleHandler = application.api.scheduleHandler
    scheduleHandler.startBackground()

    def request_shutdown(signum, _frame) -> None:
        logger.info("Получен сигнал %s, останавливаем Clima API", signal.Signals(signum).name)
        # shutdown() блокирует до выхода serve_forever(), поэтому вызываем его из другого потока.
        Thread(target=server.shutdown, name="clima-shutdown", daemon=True).start()

    signal.signal(signal.SIGTERM, request_shutdown)
    signal.signal(signal.SIGINT, request_shutdown)
    logger.info("Clima API listening at http://%s:%s", config.host, config.port)
    try:
        server.serve_forever()
    finally:
        scheduleHandler.stopBackground()
        server.server_close()
        application.close()
        logger.info("Clima API остановлен")


if __name__ == "__main__":
    main()
