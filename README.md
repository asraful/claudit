# claudit

Audit your [Claude Code](https://claude.ai/code) usage from the terminal — sessions, tokens, cost, cache hit rate, tool calls, daily breakdown.

Pure Python, stdlib only, single file. Runs anywhere Python 3.8+ runs (macOS, Linux, Windows).

## Install

One command, any platform:

```bash
pip install git+https://github.com/asraful/claudit.git
```

Or, recommended (isolated virtualenv per CLI):

```bash
pipx install git+https://github.com/asraful/claudit.git
```

`pip` ships with Python; `pipx` is `python -m pip install --user pipx` then `pipx ensurepath`. Either way, after install the `claudit` command is on your `PATH`.

### Upgrade

```bash
pip install --upgrade git+https://github.com/asraful/claudit.git
# or
pipx upgrade claudit
```

### Uninstall

```bash
pip uninstall claudit
# or
pipx uninstall claudit
```

## Usage

```bash
claudit stats                # today vs all-time summary + cost + cache hit %
claudit daily                # per-day token + cost table
claudit tools                # tool-call counts across all projects
claudit tools --project=NAME # tool counts for a single project (note the =)
claudit history -n 30        # last 30 prompts
claudit projects             # per-project messages + sessions
claudit sessions             # session files on disk

claudit --json stats         # JSON output, pipe to jq / scripts
```

Run `claudit --help` or `claudit <subcommand> --help` for full options.

## Configuration

All options are environment variables. None are required — defaults work.

| Variable           | Default       | Description                                |
|--------------------|---------------|--------------------------------------------|
| `CLAUDE_DIR`       | `~/.claude`   | Path to Claude Code's data directory       |
| `RATE_INPUT`       | `5.0`         | Input token price (USD per 1M tokens)      |
| `RATE_OUTPUT`      | `25.0`        | Output token price (USD per 1M tokens)     |
| `RATE_CACHE_READ`  | `0.5`         | Cache read price (USD per 1M tokens)       |
| `RATE_CACHE_CREATE`| `6.25`        | Cache write price (USD per 1M tokens)      |

Default rates match **Bedrock cross-region inference (ap-southeast-2)**. For Anthropic API rates use:

```bash
RATE_INPUT=15 RATE_OUTPUT=75 RATE_CACHE_READ=1.5 RATE_CACHE_CREATE=18.75 claudit stats
```

Or persist them in your shell profile / a `.envrc`.

## Inside Claude Code (slash command)

`claudit` is a normal CLI, so you can also invoke it from inside Claude Code as a slash command. Drop [`commands/claudit.md`](commands/claudit.md) into `~/.claude/commands/` (global) or your project's `.claude/commands/` directory, then:

```
/claudit stats
/claudit daily
/claudit tools --project=-Users-foo-myapp
/claudit --json daily
```

The slash command shells out to the installed `claudit` binary, so it works as long as `claudit` is on Claude Code's `PATH`.

## What it reads

`claudit` is read-only. It reads JSON / JSONL files Claude Code already writes:

- `$CLAUDE_DIR/stats-cache.json` — Claude Code's own cached summary
- `$CLAUDE_DIR/history.jsonl` — recent prompts
- `$CLAUDE_DIR/sessions/*.json` — session metadata
- `$CLAUDE_DIR/projects/<project>/**/*.jsonl` — full transcripts (used for token usage and tool-call aggregation)

Nothing is sent to a server, no telemetry, no network calls.

## Credit

Inspired by [foyzulkarim/claude-lens](https://github.com/foyzulkarim/claude-lens), which does the same thing in a browser dashboard. `claudit` reuses the same data model and pricing knobs but stays in the terminal.

## License

MIT — see [LICENSE](LICENSE).
