# claudit

Audit your [Claude Code](https://claude.ai/code) usage from the terminal — sessions, tokens, cost, cache hit rate, tool calls, daily breakdown.

Pure Python, stdlib only, single file. Runs anywhere Python 3.8+ runs (macOS, Linux, Windows).

## Requirements

- Python 3.8 or newer (`python3 --version`)
- That's it — no third-party dependencies.

## Install

The recommended way is **`pipx`**, because it puts the `claudit` binary in `~/.local/bin` (which is on your `PATH`) and isolates it in its own virtualenv:

```bash
# macOS
brew install pipx
pipx ensurepath           # one-time; restart your shell after this

# Linux / WSL
python3 -m pip install --user pipx
python3 -m pipx ensurepath

# Then, on any platform:
pipx install git+https://github.com/asraful/claudit.git
```

If you prefer plain pip:

```bash
pip install git+https://github.com/asraful/claudit.git
```

> **Heads up about plain `pip`:** depending on which Python you used, pip's script directory may not be on your `PATH`, so the `claudit` command might be missing even after a successful install. See [Troubleshooting](#troubleshooting) below if you hit `command not found`.

### Verify

```bash
claudit --help
claudit stats
```

If `claudit --help` works, you're done. If you get `command not found`, jump to [Troubleshooting](#troubleshooting).

### Upgrade

```bash
pipx upgrade claudit
# or
pip install --upgrade git+https://github.com/asraful/claudit.git
```

When installing from a local clone of this repo, force a reinstall to pick up your edits:

```bash
cd ~/dev/claudit
pip install --force-reinstall .
# or
pipx install --force ~/dev/claudit
```

### Uninstall

```bash
pipx uninstall claudit
# or
pip uninstall claudit
```

## Usage

```bash
claudit stats                # today vs all-time summary + cost + cache hit %
claudit daily                # per-day token + cost table
claudit tools                # tool-call counts across all projects
claudit tools --project=NAME # tool counts for a single project (note the =)
claudit history -n 30        # last 30 prompts
claudit projects             # per-project messages + sessions
claudit sessions             # one row per session (auto-derives from transcripts
                             #   if ~/.claude/sessions/ is missing or empty)

claudit --json stats         # JSON output, pipe to jq / scripts
```

Run `claudit --help` or `claudit <subcommand> --help` for full options.

### Example output

`claudit stats` — today vs all-time summary:

```
$ claudit stats
CLAUDE_DIR : /Users/asraful/.claude
Days seen  : 3

All-time
--------
  Sessions   : 7
  Messages   : 293
  Tool calls : 228
  Input tok  : 2,938
  Output tok : 928,094
  Cache read : 42,676,419
  Cache write: 2,730,276
  Est. cost  : $61.62
  Cache hit  : 94.0%

Today (2026-04-30)
--------
  Sessions   : 2
  Messages   : 72
  Tool calls : 59
  Est. cost  : $25.41
```

`claudit daily` — per-day token + cost breakdown:

```
$ claudit daily
date        sess  msgs  tools  input   output      c.read    c.write    cost
----------  ----  ----  -----  -----  -------  ----------  ---------  ------
2026-04-28     4   205    161    657  433,388  26,950,363  1,712,809  $35.02
2026-04-29     1    16      8     30    4,134     216,453    156,099   $1.19
2026-04-30     2    72     59  2,251  490,572  15,509,603    861,368  $25.41
TOTAL          7   293    228  2,938  928,094  42,676,419  2,730,276  $61.62
```

`claudit tools` — which tools Claude reaches for most:

```
$ claudit tools
tool   count  share
-----  -----  -----
Bash     120  52.6%
Read      77  33.8%
Edit      18   7.9%
Write     12   5.3%
Agent      1   0.4%
```

`claudit --json daily | jq` — same data, machine-readable:

```json
{
  "days": [
    {
      "date": "2026-04-28",
      "messages": 205,
      "toolCalls": 161,
      "sessions": 4,
      "input": 657,
      "output": 433388,
      "cacheRead": 26950363,
      "cacheCreate": 1712809,
      "cost": 35.02
    },
    {
      "date": "2026-04-29",
      "messages": 16,
      "toolCalls": 8,
      "sessions": 1,
      "input": 30,
      "output": 4134,
      "cacheRead": 216453,
      "cacheCreate": 156099,
      "cost": 1.19
    },
    {
      "date": "2026-04-30",
      "messages": 72,
      "toolCalls": 59,
      "sessions": 2,
      "input": 2251,
      "output": 490572,
      "cacheRead": 15509603,
      "cacheCreate": 861368,
      "cost": 25.41
    }
  ],
  "totals": {
    "messages": 293,
    "toolCalls": 228,
    "sessions": 7,
    "input": 2938,
    "output": 928094,
    "cacheRead": 42676419,
    "cacheCreate": 2730276,
    "cost": 61.62
  },
  "rates": {
    "input": 0.000005,
    "output": 0.000025,
    "cacheRead": 5e-7,
    "cacheCreate": 6.25e-6
  }
}
```

> **Tip on `--project`:** Claude Code's project directories start with a dash (e.g. `-Users-foo-myapp`). `argparse` will treat that as a flag unless you pass it with `=`:
>
> ```bash
> claudit tools --project=-Users-foo-myapp        # works
> claudit tools --project -Users-foo-myapp        # argparse error
> ```

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

`claudit` is a normal CLI, so you can also invoke it from inside Claude Code as a slash command. Drop [`commands/claudit.md`](commands/claudit.md) into `~/.claude/commands/` (global) or your project's `.claude/commands/` directory:

```bash
mkdir -p ~/.claude/commands
cp commands/claudit.md ~/.claude/commands/
```

Then in any Claude Code session:

```
/claudit stats
/claudit daily
/claudit tools --project=-Users-foo-myapp
/claudit --json daily
```

The slash command shells out to the installed `claudit` binary, so it works as long as `claudit` is on the `PATH` Claude Code sees.

## What it reads

`claudit` is read-only. It reads JSON / JSONL files Claude Code already writes:

- `$CLAUDE_DIR/stats-cache.json` — Claude Code's own cached summary (used by `stats` if present)
- `$CLAUDE_DIR/history.jsonl` — recent prompts (used by `history` and `projects`)
- `$CLAUDE_DIR/sessions/*.json` — session metadata (used by `sessions` on older Claude Code)
- `$CLAUDE_DIR/projects/<project>/**/*.jsonl` — full transcripts; the source of truth for token usage, tool-call counts, daily breakdowns, and (on newer Claude Code) the session list

Nothing is sent to a server, no telemetry, no network calls.

## Troubleshooting

### `claudit: command not found` after a successful install

This means the install worked but pip's script directory isn't on your `PATH`. Two fixes:

**Fix A — find the script dir and add it to `PATH`** (one-time):

```bash
python3 -c "import sysconfig; print(sysconfig.get_path('scripts'))"
# Example output: /Library/Frameworks/Python.framework/Versions/3.13/bin
```

Append the printed path to your shell rc:

```bash
# zsh (default macOS)
echo 'export PATH="/Library/Frameworks/Python.framework/Versions/3.13/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc

# bash
echo 'export PATH="/Library/Frameworks/Python.framework/Versions/3.13/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

**Fix B — switch to `pipx`** (recommended; permanent fix):

```bash
brew install pipx           # or: python3 -m pip install --user pipx
pipx ensurepath
# restart shell
pipx install git+https://github.com/asraful/claudit.git
```

### Last-resort fallback: `python3 -m claudit`

You can always invoke the module directly without needing the script on `PATH`:

```bash
python3 -m claudit stats
python3 -m claudit history -n 30
python3 -m claudit --json daily
```

This works as long as the `claudit` package is installed in the Python you're calling.

### `TypeError: 'int' object is not subscriptable`

You're on a `claudit` older than 0.1.1. Newer Claude Code writes timestamps as integer milliseconds; pre-0.1.1 sliced them as strings. Upgrade:

```bash
pipx upgrade claudit
# or
pip install --upgrade --force-reinstall git+https://github.com/asraful/claudit.git
```

### `claudit sessions` shows `(no data)` or "No sessions directory"

You're on a `claudit` older than 0.1.1, *and* your Claude Code version doesn't write `~/.claude/sessions/`. From 0.1.1 onward, `claudit sessions` falls back to deriving sessions from `~/.claude/projects/<project>/**/*.jsonl`. Upgrade.

### Windows: `pipx ensurepath` didn't seem to work

Close and reopen your terminal (PowerShell / cmd) after running `pipx ensurepath`. The new `PATH` only applies to new shells.

## Credit

Inspired by [foyzulkarim/claude-lens](https://github.com/foyzulkarim/claude-lens), which does the same thing in a browser dashboard. `claudit` reuses the same data model and pricing knobs but stays in the terminal.

## License

MIT — see [LICENSE](LICENSE).

## Changelog

- **0.1.1** — Handle integer-millisecond timestamps in `history.jsonl` and transcripts (newer Claude Code shape). `claudit sessions` now falls back to deriving sessions from project transcripts when `~/.claude/sessions/` is empty or missing.
- **0.1.0** — Initial release.
