#!/usr/bin/env python3
"""
claudit: audit your Claude Code usage from the terminal.

Reads the data Claude Code writes under $CLAUDE_DIR (default ~/.claude):
  stats-cache.json
  history.jsonl
  sessions/*.json
  projects/<project>/**/*.jsonl   (full transcripts)

Usage:
    claudit stats              Today / all-time summary + cost
    claudit daily              Per-day token + cost table
    claudit tools              Tool-call counts across all projects
    claudit projects           Per-project message + session counts
    claudit history -n 20      Last N prompts
    claudit sessions           Sessions on disk

Add --json to any subcommand for machine-readable output.

Pricing knobs (USD per 1M tokens):
    RATE_INPUT          (default 5.0)
    RATE_OUTPUT         (default 25.0)
    RATE_CACHE_READ     (default 0.5)
    RATE_CACHE_CREATE   (default 6.25)

Defaults are Bedrock cross-region (ap-southeast-2). For Anthropic API rates:
    RATE_INPUT=15 RATE_OUTPUT=75 RATE_CACHE_READ=1.5 RATE_CACHE_CREATE=18.75
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def claude_dir() -> Path:
    return Path(os.environ.get("CLAUDE_DIR") or Path.home() / ".claude").expanduser()

def rates() -> dict:
    return {
        "input":       float(os.environ.get("RATE_INPUT",       "5.0"))  / 1e6,
        "output":      float(os.environ.get("RATE_OUTPUT",      "25.0")) / 1e6,
        "cacheRead":   float(os.environ.get("RATE_CACHE_READ",  "0.5"))  / 1e6,
        "cacheCreate": float(os.environ.get("RATE_CACHE_CREATE","6.25")) / 1e6,
    }

# ---------------------------------------------------------------------------
# Tiny table formatter (zero dependencies)
# ---------------------------------------------------------------------------

def render_table(headers: list[str], rows: list[list], aligns: list[str] | None = None) -> str:
    if not rows:
        return "(no data)"
    str_rows = [[("" if c is None else str(c)) for c in r] for r in rows]
    widths = [len(h) for h in headers]
    for r in str_rows:
        for i, c in enumerate(r):
            if len(c) > widths[i]:
                widths[i] = len(c)
    aligns = aligns or ["left"] * len(headers)

    def fmt(cells: list[str]) -> str:
        out = []
        for c, w, a in zip(cells, widths, aligns):
            out.append(c.rjust(w) if a == "right" else c.ljust(w))
        return "  ".join(out).rstrip()

    sep = "  ".join("-" * w for w in widths)
    lines = [fmt(headers), sep]
    lines.extend(fmt(r) for r in str_rows)
    return "\n".join(lines)

def fmt_int(n) -> str:
    try:
        return f"{int(n):,}"
    except Exception:
        return str(n)

def fmt_money(n) -> str:
    try:
        return f"${float(n):,.2f}"
    except Exception:
        return str(n)

# ---------------------------------------------------------------------------
# JSONL helpers
# ---------------------------------------------------------------------------

def iter_jsonl(path: Path):
    try:
        with path.open("r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue
    except FileNotFoundError:
        return

def find_jsonl(root: Path):
    if not root.exists():
        return
    for p in root.rglob("*.jsonl"):
        if p.is_file():
            yield p

# ---------------------------------------------------------------------------
# Aggregations (mirror server.js)
# ---------------------------------------------------------------------------

def aggregate_daily(projects_dir: Path) -> dict:
    """Group token usage + tool-calls + sessions by YYYY-MM-DD."""
    daily: dict = {}
    for fp in find_jsonl(projects_dir):
        for obj in iter_jsonl(fp):
            ts = obj.get("timestamp")
            if not ts:
                continue
            day = ts[:10]
            d = daily.setdefault(day, {
                "input": 0, "output": 0, "cacheRead": 0, "cacheCreate": 0,
                "messages": 0, "toolCalls": 0, "sessions": set(),
            })
            sid = obj.get("sessionId") or ""
            t = obj.get("type")
            if t == "user":
                d["messages"] += 1
                if sid:
                    d["sessions"].add(sid)
            elif t == "assistant":
                msg = obj.get("message") or {}
                usage = msg.get("usage") or {}
                d["input"]       += usage.get("input_tokens", 0) or 0
                d["output"]      += usage.get("output_tokens", 0) or 0
                d["cacheRead"]   += usage.get("cache_read_input_tokens", 0) or 0
                d["cacheCreate"] += usage.get("cache_creation_input_tokens", 0) or 0
                content = msg.get("content")
                if isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict) and item.get("type") == "tool_use":
                            d["toolCalls"] += 1
    return daily

def daily_with_costs(daily: dict, r: dict) -> tuple[list[dict], dict]:
    days_sorted = sorted(daily.keys())
    rows = []
    totals = {k: 0 for k in ("messages", "toolCalls", "sessions",
                             "input", "output", "cacheRead", "cacheCreate", "cost")}
    for day in days_sorted:
        d = daily[day]
        cost = (d["input"]       * r["input"]
              + d["output"]      * r["output"]
              + d["cacheRead"]   * r["cacheRead"]
              + d["cacheCreate"] * r["cacheCreate"])
        cost = round(cost, 2)
        row = {
            "date": day,
            "messages": d["messages"],
            "toolCalls": d["toolCalls"],
            "sessions": len(d["sessions"]),
            "input": d["input"],
            "output": d["output"],
            "cacheRead": d["cacheRead"],
            "cacheCreate": d["cacheCreate"],
            "cost": cost,
        }
        rows.append(row)
        for k in totals:
            totals[k] += row[k]
    totals["cost"] = round(totals["cost"], 2)
    return rows, totals

def aggregate_tools(projects_dir: Path) -> tuple[list[dict], dict]:
    tool_counts: dict = defaultdict(int)
    by_project: dict = defaultdict(lambda: defaultdict(int))
    if not projects_dir.exists():
        return [], {}
    for proj_dir in sorted(p for p in projects_dir.iterdir() if p.is_dir()):
        for fp in find_jsonl(proj_dir):
            for obj in iter_jsonl(fp):
                if obj.get("type") != "assistant":
                    continue
                msg = obj.get("message") or {}
                content = msg.get("content")
                if not isinstance(content, list):
                    continue
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "tool_use":
                        name = item.get("name") or "(unknown)"
                        tool_counts[name] += 1
                        by_project[proj_dir.name][name] += 1
    sorted_tools = [{"tool": t, "count": c}
                    for t, c in sorted(tool_counts.items(), key=lambda kv: -kv[1])]
    return sorted_tools, {k: dict(v) for k, v in by_project.items()}

def project_summary(history_path: Path) -> list[dict]:
    projects: dict = {}
    for obj in iter_jsonl(history_path):
        proj = obj.get("project") or "unknown"
        p = projects.setdefault(proj, {
            "messages": 0, "sessions": set(),
            "firstSeen": None, "lastSeen": None,
        })
        p["messages"] += 1
        sid = obj.get("sessionId")
        if sid:
            p["sessions"].add(sid)
        ts = obj.get("timestamp")
        if ts:
            if not p["firstSeen"] or ts < p["firstSeen"]:
                p["firstSeen"] = ts
            if not p["lastSeen"] or ts > p["lastSeen"]:
                p["lastSeen"] = ts
    out = [{
        "name": name,
        "shortName": name.rsplit("/", 1)[-1],
        "messages": d["messages"],
        "sessions": len(d["sessions"]),
        "firstSeen": d["firstSeen"],
        "lastSeen":  d["lastSeen"],
    } for name, d in projects.items()]
    out.sort(key=lambda x: -x["messages"])
    return out

# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------

def cmd_stats(args) -> int:
    cd = claude_dir()
    r = rates()
    cache_path = cd / "stats-cache.json"
    cached = {}
    if cache_path.exists():
        try:
            cached = json.loads(cache_path.read_text())
        except Exception as e:
            print(f"warning: could not parse stats-cache.json: {e}", file=sys.stderr)

    daily = aggregate_daily(cd / "projects")
    rows, totals = daily_with_costs(daily, r)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    today_row = next((row for row in rows if row["date"] == today), None)

    payload = {
        "claudeDir": str(cd),
        "rates": r,
        "today": today_row,
        "allTime": totals,
        "statsCache": cached,
    }
    if args.json:
        print(json.dumps(payload, indent=2, default=str))
        return 0

    print(f"CLAUDE_DIR : {cd}")
    print(f"Days seen  : {len(rows)}")
    print()
    print("All-time")
    print("--------")
    print(f"  Sessions   : {fmt_int(totals['sessions'])}")
    print(f"  Messages   : {fmt_int(totals['messages'])}")
    print(f"  Tool calls : {fmt_int(totals['toolCalls'])}")
    print(f"  Input tok  : {fmt_int(totals['input'])}")
    print(f"  Output tok : {fmt_int(totals['output'])}")
    print(f"  Cache read : {fmt_int(totals['cacheRead'])}")
    print(f"  Cache write: {fmt_int(totals['cacheCreate'])}")
    print(f"  Est. cost  : {fmt_money(totals['cost'])}")
    cache_total = totals["cacheRead"] + totals["cacheCreate"]
    if cache_total:
        hit_rate = 100 * totals["cacheRead"] / cache_total
        print(f"  Cache hit  : {hit_rate:.1f}%")
    print()
    print(f"Today ({today})")
    print("--------")
    if today_row is None:
        print("  (no activity yet today)")
    else:
        print(f"  Sessions   : {fmt_int(today_row['sessions'])}")
        print(f"  Messages   : {fmt_int(today_row['messages'])}")
        print(f"  Tool calls : {fmt_int(today_row['toolCalls'])}")
        print(f"  Est. cost  : {fmt_money(today_row['cost'])}")
    return 0

def cmd_daily(args) -> int:
    cd = claude_dir()
    r = rates()
    daily = aggregate_daily(cd / "projects")
    rows, totals = daily_with_costs(daily, r)
    if args.json:
        print(json.dumps({"days": rows, "totals": totals, "rates": r}, indent=2))
        return 0
    if not rows:
        print("No daily data found in", cd / "projects")
        return 0
    headers = ["date", "sess", "msgs", "tools", "input", "output", "c.read", "c.write", "cost"]
    aligns  = ["left", "right", "right", "right", "right", "right", "right", "right", "right"]
    body = [[r_["date"], fmt_int(r_["sessions"]), fmt_int(r_["messages"]),
             fmt_int(r_["toolCalls"]), fmt_int(r_["input"]), fmt_int(r_["output"]),
             fmt_int(r_["cacheRead"]), fmt_int(r_["cacheCreate"]), fmt_money(r_["cost"])]
            for r_ in rows]
    body.append(["TOTAL", fmt_int(totals["sessions"]), fmt_int(totals["messages"]),
                 fmt_int(totals["toolCalls"]), fmt_int(totals["input"]),
                 fmt_int(totals["output"]), fmt_int(totals["cacheRead"]),
                 fmt_int(totals["cacheCreate"]), fmt_money(totals["cost"])])
    print(render_table(headers, body, aligns))
    return 0

def cmd_tools(args) -> int:
    cd = claude_dir()
    tools, by_project = aggregate_tools(cd / "projects")
    if args.project:
        tools_dict = by_project.get(args.project, {})
        tools = [{"tool": t, "count": c}
                 for t, c in sorted(tools_dict.items(), key=lambda kv: -kv[1])]
    if args.json:
        print(json.dumps({"tools": tools, "byProject": by_project}, indent=2))
        return 0
    if not tools:
        print("No tool calls found.")
        return 0
    total = sum(t["count"] for t in tools) or 1
    rows = [[t["tool"], fmt_int(t["count"]), f"{100 * t['count'] / total:.1f}%"]
            for t in tools]
    print(render_table(["tool", "count", "share"], rows, ["left", "right", "right"]))
    return 0

def cmd_history(args) -> int:
    cd = claude_dir()
    entries = list(iter_jsonl(cd / "history.jsonl"))
    entries = entries[-args.limit:] if args.limit else entries
    if args.json:
        print(json.dumps(entries, indent=2))
        return 0
    if not entries:
        print("No history.jsonl entries.")
        return 0
    rows = []
    for e in entries:
        disp = (e.get("display") or "").replace("\n", " ").strip()
        if len(disp) > 80:
            disp = disp[:77] + "..."
        rows.append([
            (e.get("timestamp") or "")[:19],
            (e.get("project") or "").rsplit("/", 1)[-1],
            disp,
        ])
    print(render_table(["timestamp", "project", "prompt"], rows))
    return 0

def cmd_sessions(args) -> int:
    cd = claude_dir()
    sess_dir = cd / "sessions"
    if not sess_dir.exists():
        print("No sessions directory at", sess_dir)
        return 0
    sessions = []
    for f in sorted(sess_dir.glob("*.json")):
        try:
            sessions.append(json.loads(f.read_text()))
        except Exception:
            continue
    if args.json:
        print(json.dumps(sessions, indent=2))
        return 0
    rows = [[s.get("id") or s.get("sessionId") or "?",
             (s.get("createdAt") or s.get("timestamp") or "")[:19],
             s.get("project") or s.get("cwd") or ""] for s in sessions]
    print(render_table(["id", "created", "project"], rows))
    return 0

def cmd_projects(args) -> int:
    cd = claude_dir()
    projs = project_summary(cd / "history.jsonl")
    if args.json:
        print(json.dumps(projs, indent=2))
        return 0
    if not projs:
        print("No project data found in history.jsonl.")
        return 0
    rows = [[p["shortName"], fmt_int(p["messages"]), fmt_int(p["sessions"]),
             (p["firstSeen"] or "")[:10], (p["lastSeen"] or "")[:10]]
            for p in projs]
    print(render_table(
        ["project", "msgs", "sess", "first", "last"], rows,
        ["left", "right", "right", "left", "left"]))
    return 0

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="claudit",
        description="Audit your Claude Code usage from the terminal.",
    )
    p.add_argument("--json", action="store_true",
                   help="Emit JSON instead of pretty tables.")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("stats",    help="Today / all-time summary").set_defaults(func=cmd_stats)
    sub.add_parser("daily",    help="Daily cost & token table").set_defaults(func=cmd_daily)

    pt = sub.add_parser("tools", help="Tool-call counts")
    pt.add_argument("--project", help="Limit to a single project directory name")
    pt.set_defaults(func=cmd_tools)

    ph = sub.add_parser("history", help="Recent prompts from history.jsonl")
    ph.add_argument("-n", "--limit", type=int, default=20,
                    help="How many prompts to show (default 20, 0 = all)")
    ph.set_defaults(func=cmd_history)

    sub.add_parser("sessions", help="Session files on disk").set_defaults(func=cmd_sessions)
    sub.add_parser("projects", help="Per-project summary").set_defaults(func=cmd_projects)
    return p

def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    cd = claude_dir()
    if not cd.exists():
        print(f"CLAUDE_DIR '{cd}' does not exist. Set CLAUDE_DIR or ensure ~/.claude exists.",
              file=sys.stderr)
        return 1
    return args.func(args)

if __name__ == "__main__":
    sys.exit(main())
