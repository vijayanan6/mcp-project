#!/usr/bin/env python3
"""
Eval Runner — MCP Learning Project

Tests whether Claude follows your system prompt rules:
  - Does Claude call the right tool for each question type?
  - Does the model router pick the right model?

Usage:
  1. Start the app:  python -m uvicorn api:app --reload --port 8000
  2. Run evals:      python evals/run_evals.py

Options:
  --url   Base URL of the app (default: http://localhost:8000)
  --verbose   Show full response for each test case
"""
import argparse
import json
import sys
import time
from pathlib import Path

import httpx

DATASET = Path(__file__).parent / "dataset.json"
BASE_URL = "http://localhost:8000"

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
RESET  = "\033[0m"
BOLD   = "\033[1m"


def run_case(client: httpx.Client, case: dict, base_url: str, verbose: bool) -> dict:
    """Run a single eval case against the /chat endpoint. Returns result dict."""
    start = time.time()
    try:
        response = client.post(
            f"{base_url}/chat",
            json={"message": case["input"], "session_id": f"eval-{case['id']}"},
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        return {
            "id": case["id"],
            "passed": False,
            "error": str(e),
            "latency": round(time.time() - start, 2),
        }

    latency = round(time.time() - start, 2)
    tools_used = data.get("tools_used", [])
    actual_tool  = tools_used[0] if tools_used else None
    actual_model = data.get("model")

    # Score tool selection
    tool_pass = True
    tool_note = ""
    if case["expected_tool"] is not None:
        if actual_tool != case["expected_tool"]:
            tool_pass = False
            tool_note = f"expected tool={case['expected_tool']!r}, got={actual_tool!r}"
    else:
        # No tool expected — but some tools are fine (e.g. calculate for math)
        if actual_tool in ("search_docs", "index_docs"):
            tool_pass = False
            tool_note = f"expected no doc tool, got={actual_tool!r}"

    # Score model routing
    model_pass = True
    model_note = ""
    if case["expected_model"] is not None:
        if actual_model != case["expected_model"]:
            model_pass = False
            model_note = f"expected model={case['expected_model']!r}, got={actual_model!r}"

    passed = tool_pass and model_pass
    notes = " | ".join(filter(None, [tool_note, model_note]))

    if verbose:
        print(f"  Response: {data.get('response', '')[:120]}...")
        print(f"  Tools used: {tools_used}")
        print(f"  Model: {actual_model}")

    return {
        "id": case["id"],
        "description": case["description"],
        "passed": passed,
        "tool_pass": tool_pass,
        "model_pass": model_pass,
        "notes": notes,
        "latency": latency,
    }


def main():
    parser = argparse.ArgumentParser(description="Run evals against the MCP app")
    parser.add_argument("--url", default=BASE_URL, help="Base URL of the running app")
    parser.add_argument("--verbose", action="store_true", help="Show full response for each case")
    args = parser.parse_args()

    cases = json.loads(DATASET.read_text())
    print(f"\n{BOLD}Running {len(cases)} eval cases against {args.url}{RESET}\n")
    print(f"{'ID':<15} {'Description':<45} {'Tool':<8} {'Model':<8} {'ms':<6} {'Result'}")
    print("-" * 100)

    results = []
    with httpx.Client() as client:
        # Check app is running
        try:
            client.get(f"{args.url}/tools", timeout=5).raise_for_status()
        except Exception:
            print(f"{RED}ERROR: App is not running at {args.url}{RESET}")
            print("Start it with:  python -m uvicorn api:app --reload --port 8000")
            sys.exit(1)

        for case in cases:
            result = run_case(client, case, args.url, args.verbose)
            results.append(result)

            status = f"{GREEN}PASS{RESET}" if result["passed"] else f"{RED}FAIL{RESET}"
            tool_icon  = "OK" if result.get("tool_pass", True) else "XX"
            model_icon = "OK" if result.get("model_pass", True) else "XX"
            notes = f"  <- {result['notes']}" if result.get("notes") else ""

            print(
                f"{result['id']:<15} "
                f"{result.get('description', '')[:44]:<45} "
                f"{tool_icon:<8} {model_icon:<8} "
                f"{result['latency']*1000:>5.0f}ms  "
                f"{status}{notes}"
            )

    # Summary
    total  = len(results)
    passed = sum(1 for r in results if r["passed"])
    failed = total - passed
    score  = passed / total * 100

    print("\n" + "=" * 100)
    print(f"{BOLD}Score: {passed}/{total} ({score:.0f}%){RESET}", end="  ")
    if score == 100:
        print(f"{GREEN}All evals passed!{RESET}")
    elif score >= 80:
        print(f"{YELLOW}{failed} case(s) need attention{RESET}")
    else:
        print(f"{RED}Evals failing — review your system prompt and model routing{RESET}")

    avg_latency = sum(r["latency"] for r in results) / total
    print(f"Average latency: {avg_latency*1000:.0f}ms per request\n")

    sys.exit(0 if score == 100 else 1)


if __name__ == "__main__":
    main()
