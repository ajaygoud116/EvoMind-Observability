from __future__ import annotations

import uvicorn

from evomind.app import create_app
from evomind.config.settings import Settings


def main() -> None:
    settings = Settings()
    app = create_app(settings)
    uvicorn.run(
        app,
        host=settings.api_host,
        port=settings.api_port,
        log_level="debug" if settings.debug else "info",
    )


if __name__ == "__main__":
    main()
