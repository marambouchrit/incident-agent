"""Local stand-in for the external payment provider."""

import random
import time
import uuid

import uvicorn
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel

app = FastAPI(title="payments-stub")


class Charge(BaseModel):
    order_id: int
    amount_cents: int


@app.post("/charge")
def charge(body: Charge) -> JSONResponse:
    roll = random.random()
    if roll < 0.01:
        return JSONResponse({"error": "provider temporarily unavailable"}, status_code=503)
    time.sleep(random.uniform(0.45, 0.8) if roll < 0.015 else random.uniform(0.02, 0.08))
    return JSONResponse({"ref": f"pay_{uuid.uuid4().hex[:16]}", "status": "captured"})


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080, access_log=False)
