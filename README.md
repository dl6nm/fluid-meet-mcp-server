# FluidMeet MCP server

Ask Claude about the meetings you recorded with [FluidVoice](https://github.com/altic-dev/FluidVoice)
(FluidMeet), for example: *"What did we decide in yesterday's call?"* or
*"Summarize the action items from my last meeting."*

This is a small, local, **read-only** [MCP](https://modelcontextprotocol.io) server. It wraps the helper
`fv-serve` that ships inside FluidVoice. It never runs any other command and never reads FluidVoice's
files directly.

> Unofficial community project. Not affiliated with the FluidVoice developers.

## Requirements

- macOS with **FluidVoice** (including FluidMeet) installed, normally in `/Applications`
- In FluidVoice: **FluidMeet settings > Integrations**, then allow agent access. Without this,
  every tool returns "meetings not shared yet".

## Install

### Claude Desktop (recommended, one click)

1. Download `fluidmeet.mcpb` from the [latest release](https://github.com/dl6nm/fluid-meet-mcp-server/releases/latest).
2. Double-click it, or in Claude Desktop go to **Settings > Extensions** and drag the file in.
3. Click **Install**. Claude Desktop sets up Python and the dependencies itself.
4. Start a new chat and ask about your meetings.

If FluidVoice is not in `/Applications`, set **Path to fv-serve** in the extension's settings.

### Claude Desktop (manual config)

This needs [uv](https://docs.astral.sh/uv/). Add the following to
`~/Library/Application Support/Claude/claude_desktop_config.json`, then restart Claude Desktop:

```json
{
  "mcpServers": {
    "fluidmeet": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/dl6nm/fluid-meet-mcp-server", "fluidmeet-mcp"]
    }
  }
}
```

If Claude Desktop reports that `uvx` can't be found, replace `"uvx"` with the absolute path that
`which uvx` prints. GUI apps don't always see your shell's `PATH`.

### Claude Code

```sh
claude mcp add fluidmeet -- uvx --from git+https://github.com/dl6nm/fluid-meet-mcp-server fluidmeet-mcp
```

## Tools

| Tool | What it does | fv-serve call |
|---|---|---|
| `meet_list(since?, limit?)` | Meetings, newest first, as JSON | `meet list … --json` |
| `meet_show(id="latest", from_?, to?, json=false)` | Transcript, optionally a time window | `meet show <id> [--from] [--to] [--json]` |
| `meet_summary(id="latest", style?)` | Summaries saved in FluidVoice | `meet summary <id> [--style]` |
| `meet_search(text, since?, limit?)` | Matching lines with timestamps | `meet search … -- <text>` |
| `status()` | Is access granted? How many meetings? | `status --json` |
| `skill()` | FluidVoice's own usage guide | `skill` |

- **Input formats:** `since` is `7d`, `24h` or `YYYY-MM-DD`. `from_`/`to` are `MM:SS`; minutes can
  go above 59, e.g. `75:30`. `id` is `latest` or an id prefix from `meet_list`.
- **Long transcripts:** a 1-hour meeting is about 10,000 words. The tool descriptions steer Claude
  to `meet_search` and time windows, and output above 50,000 characters is truncated with a hint.
- **Transcript content:** the tool descriptions mark transcript text as data, not instructions.

## Configuration

All settings are optional environment variables:

| Variable | Default | Purpose |
|---|---|---|
| `FLUIDMEET_FV_SERVE` | `/Applications/FluidVoice.app/Contents/Helpers/fv-serve` | Path to `fv-serve` |
| `FLUIDMEET_TIMEOUT` | `30` | Seconds per `fv-serve` call |
| `FLUIDMEET_MAX_CHARS` | `50000` | Output size limit before truncation |

## Troubleshooting

- **"meetings not shared yet":** in FluidVoice open FluidMeet settings > Integrations and add the agent.
- **"command not found":** FluidVoice was moved or removed. Reinstall it, or set `FLUIDMEET_FV_SERVE`.
  Then use **Update skill** under FluidMeet settings > Integrations.
- **"No current saved summary":** summaries are created in FluidVoice. Ask Claude to read or
  search the transcript instead.
- **Claude Desktop logs:** `~/Library/Logs/Claude/mcp-server-fluidmeet.log`

## Privacy

Everything runs locally. The server only passes along what `fv-serve` prints, and only when Claude
calls a tool. Transcript text that Claude reads becomes part of your conversation with Claude.

## Development

```sh
uv sync
uv run pytest                         # unit tests, fv-serve is mocked
uv run fluidmeet-mcp                  # run the server on stdio
npx -y @anthropic-ai/mcpb@2.1.2 pack . dist/fluidmeet.mcpb   # build the Claude Desktop bundle
```

To release: bump `version` in both `pyproject.toml` and `manifest.json`, then push a tag such as
`v0.1.0`. The GitHub workflow runs the tests, builds `fluidmeet.mcpb` and attaches it to the release.

## License

MIT, see [LICENSE](LICENSE). FluidVoice itself is GPL-3.0 and is not included here.
