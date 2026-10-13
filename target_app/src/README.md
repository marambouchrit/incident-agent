# shopline

Small shop backend: `api` (FastAPI), `worker` (background jobs), PostgreSQL, and a local stand-in for the payment provider.

## Run locally
```
docker compose up -d db
./deploy.sh --migrate api worker payments
curl localhost:18000/healthz
```

## Deploy notes
- `./deploy.sh <service>` builds the current commit and restarts the given services. Each service logs `service started` with the commit it runs.
- Schema changes are **not** applied on startup. Pass `--migrate` to run `alembic upgrade head` before the restart.
- Settings live in `config/`. A settings change needs a deploy of the affected service to take effect.

## Load test
```
docker compose --profile load up -d loadgen
```
