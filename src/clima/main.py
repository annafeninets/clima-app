"""Application entry point."""

import logging

from clima.boundaries.http_gateway import ClimaHTTPServer, create_handler
from clima.config import Config
from clima.container import Application

logger = logging.getLogger("clima")


def main() -> None:
    config = Config.from_env()
    logging.basicConfig(
        level=config.logLevel,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    application = Application(databasePath=config.dbPath, photoRoot=config.photoRoot)
    server = ClimaHTTPServer(
        (config.host, config.port), create_handler(application, config.corsOrigins)
    )
    scheduleHandler = application.api.scheduleHandler
    scheduleHandler.startBackground()
    logger.info("Clima API listening at http://%s:%s", config.host, config.port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Stopping Clima API")
    finally:
        scheduleHandler.stopBackground()
        server.server_close()
        application.close()


if __name__ == "__main__":
    main()
