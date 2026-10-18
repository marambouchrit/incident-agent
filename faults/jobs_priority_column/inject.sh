#!/usr/bin/env bash
# Adds jobs.priority (model, migration, claim query, checkout), then deploys only the worker, without --migrate.
set -euo pipefail
source "$FAULTS_DIR/lib.sh"

python - <<'PY'
from pathlib import Path


def edit(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    assert text.count(old) == 1, f"expected exactly one match in {path}"
    file.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


edit(
    "app/models.py",
    "    attempts: Mapped[int] = mapped_column(Integer, default=0)\n",
    "    attempts: Mapped[int] = mapped_column(Integer, default=0)\n"
    '    priority: Mapped[int] = mapped_column(Integer, default=0, server_default="0")\n',
)
edit(
    "app/routers/checkout.py",
    '    session.add(Job(kind="order_confirmation", payload={"order_id": order.id}))\n',
    '    session.add(Job(kind="order_confirmation", payload={"order_id": order.id}, priority=10))\n',
)
edit(
    "worker/main.py",
    "        ORDER BY id LIMIT :batch\n",
    "        ORDER BY priority DESC, id LIMIT :batch\n",
)

Path("migrations/versions/0002_job_priority.py").write_text(
    '''"""job priority

Revision ID: 0002
Revises: 0001
"""
import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"


def upgrade() -> None:
    op.add_column("jobs", sa.Column("priority", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("jobs", "priority")
''',
    encoding="utf-8",
    newline="\n",
)
PY

commit_as "$PRIYA" "Add priority to job queue"
mark_culprit
deploy worker
