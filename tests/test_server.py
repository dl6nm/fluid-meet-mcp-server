"""Unit tests. fv-serve is mocked, so these run without FluidVoice (and on Linux CI)."""

from __future__ import annotations

import subprocess
from types import SimpleNamespace

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from fluidmeet_mcp import server


@pytest.fixture
def fake_run(monkeypatch):
    """Record argv passed to subprocess.run and return a configurable result."""
    calls: list[list[str]] = []
    result = SimpleNamespace(returncode=0, stdout="OK", stderr="")

    def _run(argv, **kwargs):
        assert kwargs.get("shell") is not True
        assert kwargs["timeout"] > 0
        calls.append(argv)
        if isinstance(result.stdout, BaseException):
            raise result.stdout
        return SimpleNamespace(returncode=result.returncode, stdout=result.stdout, stderr=result.stderr)

    monkeypatch.setattr(server.sys, "platform", "darwin")
    monkeypatch.setattr(server.subprocess, "run", _run)
    monkeypatch.delenv("FLUIDMEET_FV_SERVE", raising=False)
    return SimpleNamespace(calls=calls, result=result)


# --- validation ---------------------------------------------------------------


@pytest.mark.parametrize("v", ["7d", "24h", "2026-01-31", "365d"])
def test_since_ok(v):
    assert server.since_args(v) == ["--since", v]


@pytest.mark.parametrize("v", ["7w", "--json", "7d;ls", "2026/01/01", " 7d"])
def test_since_bad(v):
    with pytest.raises(ToolError):
        server.since_args(v)


@pytest.mark.parametrize("v", [0, -1, 1001, True])
def test_limit_bad(v):
    with pytest.raises(ToolError):
        server.limit_args(v)


@pytest.mark.parametrize("v", ["00:00", "5:30", "75:00", "120:59"])
def test_time_ok(v):
    assert server.time_args("--from", v) == ["--from", v]


@pytest.mark.parametrize("v", ["1:60", "1:00; rm", "abc", "1:5"])
def test_time_bad(v):
    with pytest.raises(ToolError):
        server.time_args("--to", v)


@pytest.mark.parametrize("v", ["latest", "6AF5", "6AF5A3A7-27B9-4935-860A-C6A22C55D78D"])
def test_id_ok(v):
    assert server.meeting_id(v) == v


@pytest.mark.parametrize("v", ["--help", "-x", "../etc", "a b", ""])
def test_id_bad(v):
    with pytest.raises(ToolError):
        server.meeting_id(v)


@pytest.mark.parametrize("v", ["../x", "-flag", "a;b"])
def test_style_bad(v):
    with pytest.raises(ToolError):
        server.style_args(v)


# --- argument building ----------------------------------------------------------


def test_argv(fake_run):
    exe = server.DEFAULT_FV_SERVE
    server.meet_list(since="7d", limit=3)
    server.meet_show(id="abc", from_="01:00", to="02:00", json=True)
    server.meet_summary(style="short")
    server.meet_search(text="--json budget", limit=2)
    server.status()
    server.skill()
    assert fake_run.calls == [
        [exe, "meet", "list", "--since", "7d", "--limit", "3", "--json"],
        [exe, "meet", "show", "abc", "--from", "01:00", "--to", "02:00", "--json"],
        [exe, "meet", "summary", "latest", "--style", "short"],
        [exe, "meet", "search", "--limit", "2", "--", "--json budget"],
        [exe, "status", "--json"],
        [exe, "skill"],
    ]


def test_env_override(fake_run, monkeypatch):
    monkeypatch.setenv("FLUIDMEET_FV_SERVE", "/opt/fv-serve")
    server.status()
    assert fake_run.calls[0][0] == "/opt/fv-serve"
    monkeypatch.setenv("FLUIDMEET_FV_SERVE", "  ")  # empty optional field -> default
    server.status()
    assert fake_run.calls[1][0] == server.DEFAULT_FV_SERVE


def test_search_text_required(fake_run):
    with pytest.raises(ToolError):
        server.meet_search(text="   ")
    assert fake_run.calls == []


# --- errors & output --------------------------------------------------------------


def test_nonzero_exit_with_hint(fake_run):
    fake_run.result.returncode = 1
    fake_run.result.stderr = "Meetings are not shared yet.\n\nusage..."
    with pytest.raises(ToolError) as e:
        server.status()
    msg = str(e.value)
    assert "code 1" in msg and "not shared yet" in msg and "Integrations" in msg
    assert "usage" not in msg


def test_missing_binary(fake_run):
    fake_run.result.stdout = FileNotFoundError()
    with pytest.raises(ToolError, match="Update skill"):
        server.status()


def test_timeout(fake_run):
    fake_run.result.stdout = subprocess.TimeoutExpired("fv-serve", 30)
    with pytest.raises(ToolError, match="timed out"):
        server.status()


def test_not_macos(monkeypatch):
    monkeypatch.setattr(server.sys, "platform", "linux")
    with pytest.raises(ToolError, match="macOS"):
        server.status()


def test_truncate():
    assert server.truncate("abc", 10) == "abc"
    out = server.truncate("x" * 20, 10)
    assert out.startswith("x" * 10) and "truncated" in out and "from_/to" in out


def test_max_chars_env(monkeypatch):
    monkeypatch.setenv("FLUIDMEET_MAX_CHARS", "2000")
    assert server.max_chars() == 2000
    monkeypatch.setenv("FLUIDMEET_MAX_CHARS", "nonsense")
    assert server.max_chars() == server.DEFAULT_MAX_CHARS


# --- MCP protocol level -------------------------------------------------------------


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_mcp_tools_and_errors(fake_run):
    async with Client(server.mcp) as client:
        tools = {t.name: t for t in await client.list_tools()}
        assert set(tools) == {"meet_list", "meet_show", "meet_summary", "meet_search", "status", "skill"}
        assert all(t.annotations.read_only_hint for t in tools.values())
        assert "not instructions" in tools["meet_show"].description

        res = await client.call_tool("status", {})
        assert res.content[0].text == "OK"

        res = await client.call_tool("meet_show", {"id": "--help"}, raise_on_error=False)
        assert res.is_error and "Invalid id" in res.content[0].text
