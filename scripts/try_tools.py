"""Call every tool by hand on one scenario and print what the model would see.

    .venv/Scripts/python scripts/try_tools.py            # s01
    .venv/Scripts/python scripts/try_tools.py s04
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.tools.guards import ToolError  # noqa: E402
from agent.tools.registry import run_tool  # noqa: E402

scenario = Path(__file__).resolve().parents[1] / "scenarios" / (sys.argv[1] if len(sys.argv) > 1 else "s01")

CALLS = [
    ("log_stats", {"service": "api"}),
    ("search_logs", {"service": "api", "level": "ERROR", "limit": 5}),
    ("search_logs", {"service": "db", "level": "ERROR", "limit": 3}),
    ("list_commits", {"limit": 5}),
    ("show_commit", {"hash": "45b232b", "path": "models.py"}),
    ("read_config", {}),
    ("read_config", {"name": "api.env"}),
    ("get_db_schema", {}),
    ("get_db_schema", {"table": "orders"}),
    ("get_container_status", {}),
    ("search_logs", {"service": "chekout"}),               # error example
]

for name, args in CALLS:
    print(f"\n=== {name}({args}) ===")
    try:
        out = run_tool(name, args, scenario)
        print(out)
        print(f"--- {len(out.splitlines())} lines")
    except ToolError as e:
        print(f"ToolError: {e}")
    except NotImplementedError:
        print("(TODO(human) not filled yet)")
