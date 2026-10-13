import importlib
import pkgutil

from fastapi import FastAPI

from app import config, routers
from app.middleware import request_logging

app = FastAPI(title="shopline", version=config.APP_VERSION)
app.middleware("http")(request_logging)

for module in pkgutil.iter_modules(routers.__path__):
    app.include_router(importlib.import_module(f"app.routers.{module.name}").router)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok", "version": config.APP_VERSION}
