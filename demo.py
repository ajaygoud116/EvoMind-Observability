"""
EvoMind Observability — Demo Script
=====================================
Demonstrates behavioral learning for AI agents:
  • Unsafe queries accumulate evidence and trigger a status promotion.
  • Once promoted (active), the rule engine retrieves rules and injects guidance.
  • Safe queries rebuild confidence over time.

Usage:
    python demo.py               # interactive mode (press Enter between steps)
    python demo.py --auto         # non‑stop mode
    python demo.py --host 0.0.0.0 --port 9000
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass, field
from typing import Any

import requests
from colorama import Fore, Style, init as colorama_init

# ---------------------------------------------------------------------------
# Colour helpers
# ---------------------------------------------------------------------------

colorama_init(autoreset=True)

G = Fore.GREEN
R = Fore.RED
Y = Fore.YELLOW
C = Fore.CYAN
M = Fore.MAGENTA
W = Fore.WHITE
B = Style.BRIGHT
RS = Style.RESET_ALL


def c(text: str, *applied: str) -> str:
    """Apply ANSI codes and reset."""
    return "".join(applied) + text + RS


def ok(text: str) -> str:
    return c(text, B, G)


def fail(text: str) -> str:
    return c(text, B, R)


def warn(text: str) -> str:
    return c(text, B, Y)


def info(text: str) -> str:
    return c(text, C)


def heading(text: str) -> str:
    return c(text, B, W)


# ---------------------------------------------------------------------------
# API client
# ---------------------------------------------------------------------------

MAX_RETRIES = 5
RETRY_DELAY = 1.0


@dataclass
class QueryResult:
    request_id: str
    sql: str
    classification: str
    rule_retrieved: bool
    rule_name: str | None
    guidance_injected: bool
    confidence: float
    confidence_delta: float
    status_changed: bool
    to_status: str | None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> QueryResult:
        return cls(
            request_id=data["request_id"],
            sql=data["sql"],
            classification=data["classification"],
            rule_retrieved=data["rule_retrieved"],
            rule_name=data.get("rule_name"),
            guidance_injected=data["guidance_injected"],
            confidence=data["confidence"],
            confidence_delta=data["confidence_delta"],
            status_changed=data["status_changed"],
            to_status=data.get("to_status"),
        )


class EvoMindClient:
    def __init__(self, host: str, port: int):
        self.base = f"http://{host}:{port}"

    def health(self) -> dict[str, Any]:
        resp = requests.get(f"{self.base}/api/health", timeout=5)
        resp.raise_for_status()
        return resp.json()

    def query(self, prompt: str) -> QueryResult:
        resp = requests.post(
            f"{self.base}/api/query",
            json={"prompt": prompt},
            timeout=10,
        )
        resp.raise_for_status()
        return QueryResult.from_dict(resp.json())

    def wait_ready(self) -> dict[str, Any]:
        last_err: Exception | None = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                data = self.health()
                print(
                    f"  {ok('✓')} API reachable  "
                    f"version={info(data.get('version', '?'))}  "
                    f"service={info(data['service'])}"
                )
                return data
            except requests.ConnectionError as exc:
                last_err = exc
                if attempt < MAX_RETRIES:
                    print(
                        f"  {fail('✗')} Connection refused  "
                        f"(attempt {attempt}/{MAX_RETRIES})  "
                        f"retrying in {RETRY_DELAY}s…"
                    )
                    time.sleep(RETRY_DELAY)
                else:
                    print(
                        f"  {fail('✗')} Connection refused  "
                        f"(attempt {attempt}/{MAX_RETRIES})"
                    )
        print(
            f"\n  {fail('FATAL')} Could not reach the API at "
            f"{info(self.base)} after {MAX_RETRIES} attempts."
        )
        print(
            f"  Please ensure the EvoMind server is running on port "
            f"{info('8000')} and try again."
        )
        sys.exit(1)


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

STATUS_LABELS: dict[str, str] = {
    "safe": ok("SAFE"),
    "unsafe": fail("UNSAFE"),
    "ambiguous": warn("AMBIGUOUS"),
}


def print_result(idx: int, r: QueryResult) -> None:
    label = STATUS_LABELS.get(r.classification, r.classification.upper())
    print(f"  [{heading(f'#{idx}')}]  Classification: {label}")
    print(f"        Confidence:    {r.confidence:>7.4f}  "
          f"(delta {r.confidence_delta:>+7.4f})")
    print(f"        Rule:          {info('✓') if r.rule_retrieved else '–'}  "
          f"{r.rule_name or '–'}")
    print(f"        Guidance:      {info('✓') if r.guidance_injected else '–'}")
    print(f"        Request ID:    {r.request_id}")
    print(f"        SQL:           {r.sql}")
    if r.status_changed:
        print(f"        {warn('★ STATUS CHANGE')} → {warn(r.to_status or '?')}")
    print()


def print_divider(char: str = "─", width: int = 72) -> None:
    print(char * width)


# ---------------------------------------------------------------------------
# Demo orchestration
# ---------------------------------------------------------------------------

UNSAFE_PROMPTS = [
    "Show me users where id equals 5",
    "Insert a new order for user 10 with amount 99.99",
    "Delete user with id 1",
]

SAFE_PROMPTS = [
    "Show me all users",
    "List all orders",
]


def run_demo(client: EvoMindClient, auto: bool) -> None:
    results: list[QueryResult] = []

    # ---- Step 1 ----
    print()
    print_divider("━")
    print(heading("  STEP 1 — Initial Requests  "))
    print(info("  Sending unsafe SQL requests to accumulate evidence…"))
    print_divider()
    print()

    if not auto:
        input(f"  {c('Press Enter to continue…', M)}")

    for i, prompt in enumerate(UNSAFE_PROMPTS, 1):
        r = client.query(prompt)
        results.append(r)
        print_result(i, r)

    # ---- Step 2 ----
    print_divider("━")
    print(heading("  STEP 2 — Verify Promotion  "))
    print(info("  Checking that the agent was promoted to 'active' status…"))
    print_divider()
    print()

    if not auto:
        input(f"  {c('Press Enter to continue…', M)}")

    last = results[-1]
    if last.status_changed and last.to_status == "active":
        print(f"  {ok('✓')} Status changed  →  {warn('active')}\n")
    else:
        status_info = ""
        if not last.status_changed:
            status_info += " status_changed=False"
        if last.to_status != "active":
            status_info += f" to_status={last.to_status}"
        print(f"  {fail('✗')} Unexpected:{status_info}\n")

    # ---- Step 3 ----
    print_divider("━")
    print(heading("  STEP 3 — Rule Enforcement  "))
    print(info("  Repeating unsafe request — rule should be retrieved and "
               "guidance injected…"))
    print_divider()
    print()

    if not auto:
        input(f"  {c('Press Enter to continue…', M)}")

    r = client.query("Delete user with id 1")
    results.append(r)
    print_result(len(results), r)

    if r.rule_retrieved and r.guidance_injected:
        print(f"  {ok('✓')} Rule enforced  —  "
              f"rule={info(r.rule_name or '?')}  "
              f"guidance={ok('injected')}\n")
    else:
        print(f"  {fail('✗')} Rule not enforced  —  "
              f"rule_retrieved={r.rule_retrieved}  "
              f"guidance_injected={r.guidance_injected}\n")

    # ---- Step 4 ----
    print_divider("━")
    print(heading("  STEP 4 — Grow Confidence  "))
    print(info("  Sending safe requests to rebuild confidence…"))
    print_divider()
    print()

    if not auto:
        input(f"  {c('Press Enter to continue…', M)}")

    for i, prompt in enumerate(SAFE_PROMPTS, len(results) + 1):
        r = client.query(prompt)
        results.append(r)
        print_result(i, r)

    # ---- Summary ----
    print_divider("━")
    print(heading("  SUMMARY  "))
    print_divider()
    print()

    header = (
        f"  {'#':<4} {'Classification':<14} {'Confidence':<10} "
        f"{'Rule':<6} {'Guidance':<9} {'Status':<12} SQL"
    )
    sep = "  " + "─" * (len(header) - 2)
    print(header)
    print(sep)

    for idx, r in enumerate(results, 1):
        label = STATUS_LABELS.get(r.classification, r.classification.upper())
        rule_mark = ok("✓") if r.rule_retrieved else "–"
        guidance_mark = ok("✓") if r.guidance_injected else "–"
        status = ""
        if r.status_changed:
            status = warn(f"→{r.to_status or '?'}")
        else:
            status = "—"
        sql_short = r.sql if len(r.sql) <= 36 else r.sql[:33] + "…"
        print(
            f"  {idx:<4} {label:<14} {r.confidence:<10.4f} "
            f"{rule_mark:<6} {guidance_mark:<9} {status:<12} {sql_short}"
        )

    print()
    num_safe = sum(1 for r in results if r.classification == "safe")
    num_unsafe = sum(1 for r in results if r.classification == "unsafe")
    print(f"  Total requests:  {len(results)}  "
          f"({ok(str(num_safe))} safe, "
          f"{fail(str(num_unsafe))} unsafe)")
    print(f"  Promotions:      {warn(str(sum(1 for r in results if r.status_changed)))}")
    print()
    print(info("  Demo complete. Thanks for watching!"))
    print()


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="EvoMind Observability — Behavioural Learning Demo",
    )
    parser.add_argument(
        "--host",
        default="localhost",
        help="API host (default: localhost)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="API port (default: 8000)",
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Skip interactive pauses and run everything automatically",
    )
    args = parser.parse_args()

    client = EvoMindClient(host=args.host, port=args.port)

    print()
    print_divider("━")
    print(heading("  EvoMind Observability — Demo  "))
    print(info(f"  Target: {args.host}:{args.port}  "
               f"Mode: {'auto' if args.auto else 'interactive'}"))
    print_divider()
    print()

    client.wait_ready()
    run_demo(client, auto=args.auto)


if __name__ == "__main__":
    main()
