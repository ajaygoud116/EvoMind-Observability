from __future__ import annotations

import logging
import traceback
import sys

import uvicorn

from evomind.app import create_app
from evomind.config.settings import Settings

logger = logging.getLogger("evomind")


def main() -> None:
    try:
        settings = Settings()
        app = create_app(settings)
        uvicorn.run(
            app,
            host=settings.api_host,
            port=settings.api_port,
            log_level="debug" if settings.debug else "info",
        )
    except SystemExit as exc:
        logger.warning("=== MAIN EXIT: SystemExit(code=%s) ===", exc.code)
        raise
    except BaseException:
        logger.critical(
            "=== MAIN EXIT: UNHANDLED EXCEPTION ===\n%s",
            traceback.format_exc(),
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
