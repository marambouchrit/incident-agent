import os
import time
from pathlib import Path

import pytest

from agent.tools.guards import (
    ToolError,
    ToolTimeout,
    cap_output,
    run_with_timeout,
    safe_path,
)

REPO = Path(__file__).resolve().parents[1]
S01 = REPO / "scenarios" / "s01"


# --- safe_path ---------------------------------------------------------------

def test_safe_path_allows_file_inside_scenario():
    p = safe_path(S01, "logs/api.jsonl")
    assert p == (S01 / "logs" / "api.jsonl").resolve()
    assert p.exists()


@pytest.mark.parametrize(
    "rel",
    [
        "../../ground_truth/s01.json",   # the one that matters most
        "logs/../../../ground_truth/s01.json",
        "..",
        "/etc/passwd",
        "\\Windows\\win.ini",
        "C:/Windows/win.ini",
        str(REPO / "ground_truth" / "s01.json"),
        "",
        "   ",
    ],
)
def test_safe_path_rejects_escapes(rel):
    with pytest.raises(ToolError):
        safe_path(S01, rel)


def test_ground_truth_is_unreachable_from_any_scenario():
    gt = (REPO / "ground_truth").resolve()
    for scenario in sorted((REPO / "scenarios").iterdir()):
        if not scenario.is_dir():
            continue
        for rel in [f"../../ground_truth/{scenario.name}.json", "../../ground_truth"]:
            with pytest.raises(ToolError):
                safe_path(scenario, rel)
        # and nothing inside a scenario resolves into ground_truth
        for f in scenario.rglob("*"):
            assert not f.resolve().is_relative_to(gt)


def test_safe_path_rejects_symlink_out(tmp_path):
    scenario = tmp_path / "s99"
    scenario.mkdir()
    secret = tmp_path / "secret.json"
    secret.write_text("{}")
    link = scenario / "link.json"
    try:
        os.symlink(secret, link)
    except OSError:
        pytest.skip("symlinks need Developer Mode/admin on Windows")
    with pytest.raises(ToolError):
        safe_path(scenario, "link.json")


# --- cap_output --------------------------------------------------------------

def test_cap_short_text_unchanged():
    text = "\n".join(f"line {i}" for i in range(50))
    assert cap_output(text) == text


def test_cap_exactly_at_limit_unchanged():
    text = "\n".join(f"line {i}" for i in range(100))
    assert cap_output(text) == text


def test_cap_footer_long_text_is_cut():
    text = "\n".join(f"line {i}" for i in range(440))
    out = cap_output(text).splitlines()
    assert len(out) == 101                  # 100 kept lines + 1 footer
    assert out[99] == "line 99"
    assert "line 100" not in out


def test_cap_footer_says_how_much_is_missing():
    text = "\n".join(f"line {i}" for i in range(440))
    footer = cap_output(text).splitlines()[-1]
    assert "340" in footer                  # omitted count is visible to the model


# --- run_with_timeout --------------------------------------------------------

def test_timeout_returns_value():
    assert run_with_timeout(lambda x: x * 2, 21, timeout_s=1) == 42


def test_timeout_raises_on_slow_tool():
    start = time.monotonic()
    with pytest.raises(ToolTimeout):
        run_with_timeout(time.sleep, 2, timeout_s=0.2)
    assert time.monotonic() - start < 1.0   # loop is not blocked by the slow call


def test_timeout_propagates_tool_errors():
    def boom():
        raise ToolError("bad args")
    with pytest.raises(ToolError, match="bad args"):
        run_with_timeout(boom, timeout_s=1)
