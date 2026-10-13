import importlib
import pkgutil

from fastapi import FastAPI

from app import config, routers

app = FastAPI(title="shopline", version=config.APP_VERSION)

for module in pkgutil.iter_modules(routers.__path__):
    app.include_router(importlib.import_module(f"app.routers.{module.name}").router)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok", "version": config.APP_VERSION}
