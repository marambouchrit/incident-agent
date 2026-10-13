import logging

import uvicorn

from app import config
from app.logging_setup import configure


def main() -> None:
    configure("api")
    logging.getLogger("app").info("service started", extra={"version": config.APP_VERSION})
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, log_config=None, access_log=False)


if __name__ == "__main__":
    main()
