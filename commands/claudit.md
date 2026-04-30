---
description: Audit Claude Code usage (sessions, tokens, cost, tool calls).
argument-hint: "[stats|daily|tools|history|sessions|projects] [--json] [-n N] [--project=NAME]"
allowed-tools: Bash(claudit:*)
---

Run the `claudit` CLI and show its output verbatim.

Default to `stats` if the user did not provide a subcommand.

```bash
claudit ${ARGUMENTS:-stats}
```

If the output is a pretty table, summarize it in one or two sentences after the table — e.g. "Today: 14 messages, 32 tool calls, ~$0.42. All-time: $18.30 across 240 sessions."

If `--json` was passed, do not summarize; just relay the JSON unchanged.
