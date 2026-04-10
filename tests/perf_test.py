"""
Ops Assistant — Performance Test Script

Connects via WebSocket, sends a series of test questions, and measures
end-to-end latency for each. Prints a summary table at the end.

Usage:
    python tests/perf_test.py                          # test against ACA
    python tests/perf_test.py --url ws://localhost:8000/ws  # test locally
    python tests/perf_test.py --rounds 3               # run 3 rounds
"""
import argparse
import asyncio
import json
import statistics
import time

import websockets

# ── Default target ──
DEFAULT_URL = "wss://ca-opsassistant.thankfulhill-7caa8389.northcentralus.azurecontainerapps.io/ws"

# ── Test scenarios covering all specialist agents ──
TEST_QUESTIONS = [
    {"label": "Operations — status",      "q": "How are we doing?"},
    {"label": "Operations — drill-down",  "q": "What's the cold bar wait time?"},
    {"label": "Diagnostics — bottleneck", "q": "Why is cold bar over capacity?"},
    {"label": "Diagnostics — action",     "q": "Move Emma to cold bar"},
    {"label": "Forecasting — demand",     "q": "Should I start batch prep now?"},
    {"label": "Forecasting — pipeline",   "q": "How many mobile orders are pending?"},
    {"label": "Safety — policy",          "q": "What content safety policies do we have?"},
]


async def send_and_measure(ws, question: str, timeout: float = 120) -> dict:
    """
    Send a question and wait for the full response ([DONE] marker).
    Returns timing info and response metadata.
    """
    t_start = time.perf_counter()
    t_first_chunk = None

    await ws.send(question)

    agent_name = ""
    safety = {}
    chunks = []
    suggestions = []

    try:
        while True:
            msg = await asyncio.wait_for(ws.recv(), timeout=timeout)

            if msg.startswith("[AGENT:"):
                agent_name = msg[7:-1]
                continue

            if msg.startswith("[SAFETY:"):
                try:
                    safety = json.loads(msg[8:-1])
                except Exception:
                    pass
                continue

            if msg.startswith("[SUGGESTIONS:"):
                try:
                    suggestions = json.loads(msg[13:-1])
                except Exception:
                    pass
                continue

            if msg == "[DONE]":
                # After DONE, try to grab SUGGESTIONS (sent right after)
                try:
                    extra = await asyncio.wait_for(ws.recv(), timeout=2)
                    if extra.startswith("[SUGGESTIONS:"):
                        suggestions = json.loads(extra[13:-1])
                except Exception:
                    pass
                break

            # Content chunk
            if t_first_chunk is None:
                t_first_chunk = time.perf_counter()
            chunks.append(msg)

    except asyncio.TimeoutError:
        return {"error": f"Timeout after {timeout}s", "total_s": time.perf_counter() - t_start}
    except Exception as e:
        return {"error": str(e), "total_s": time.perf_counter() - t_start}

    t_end = time.perf_counter()
    response_text = "".join(chunks)

    return {
        "agent": agent_name,
        "total_s": round(t_end - t_start, 2),
        "ttfc_s": round(t_first_chunk - t_start, 2) if t_first_chunk else None,
        "response_len": len(response_text),
        "suggestions": len(suggestions),
        "safe": safety.get("input_safe", "?") and safety.get("output_safe", "?"),
        "safety_available": safety.get("available", False),
        "error": None,
    }


async def run_tests(url: str, rounds: int = 1, delay: float = 1.0):
    """Run all test questions and collect results."""
    all_results = []

    for round_num in range(1, rounds + 1):
        if rounds > 1:
            print(f"\n{'='*60}")
            print(f"  ROUND {round_num}/{rounds}")
            print(f"{'='*60}")

        async with websockets.connect(url, max_size=2**20) as ws:
            # No server-side welcome message (rendered client-side), go straight to tests

            for i, test in enumerate(TEST_QUESTIONS):
                label = test["label"]
                question = test["q"]

                print(f"\n  [{i+1}/{len(TEST_QUESTIONS)}] {label}")
                print(f"  Q: \"{question}\"")

                result = await send_and_measure(ws, question)
                result["label"] = label
                result["question"] = question
                result["round"] = round_num

                if result.get("error"):
                    print(f"  ❌ ERROR: {result['error']} ({result['total_s']}s)")
                else:
                    print(f"  ✅ {result['agent']} | {result['total_s']}s total | "
                          f"TTFC {result['ttfc_s']}s | {result['response_len']} chars | "
                          f"{result['suggestions']} suggestions")

                all_results.append(result)

                # Brief pause between questions to avoid rate limits
                if i < len(TEST_QUESTIONS) - 1:
                    await asyncio.sleep(delay)

    return all_results


def print_summary(results: list[dict]):
    """Print a summary table of all results."""
    print(f"\n{'='*90}")
    print("  PERFORMANCE SUMMARY")
    print(f"{'='*90}")

    # Header
    print(f"  {'Test':<30} {'Agent':<20} {'Total (s)':<12} {'TTFC (s)':<10} {'Chars':<8} {'Status'}")
    print(f"  {'-'*30} {'-'*20} {'-'*12} {'-'*10} {'-'*8} {'-'*8}")

    times = []
    ttfcs = []
    errors = 0

    for r in results:
        label = r["label"][:30]
        agent = r.get("agent", "?")[:20]
        total = r.get("total_s", "?")
        ttfc = r.get("ttfc_s", "?")
        chars = r.get("response_len", "?")
        status = "❌ " + str(r["error"])[:30] if r.get("error") else "✅"

        print(f"  {label:<30} {agent:<20} {str(total):<12} {str(ttfc):<10} {str(chars):<8} {status}")

        if not r.get("error") and isinstance(total, (int, float)):
            times.append(total)
        if not r.get("error") and isinstance(ttfc, (int, float)):
            ttfcs.append(ttfc)
        if r.get("error"):
            errors += 1

    print(f"\n  {'─'*60}")
    if times:
        print(f"  Total requests:   {len(results)}")
        print(f"  Successful:       {len(results) - errors}")
        print(f"  Errors:           {errors}")
        print(f"  Avg total time:   {statistics.mean(times):.2f}s")
        print(f"  Median total:     {statistics.median(times):.2f}s")
        print(f"  Min / Max:        {min(times):.2f}s / {max(times):.2f}s")
        if len(times) >= 2:
            print(f"  Std dev:          {statistics.stdev(times):.2f}s")
        if ttfcs:
            print(f"  Avg TTFC:         {statistics.mean(ttfcs):.2f}s")
            print(f"  Median TTFC:      {statistics.median(ttfcs):.2f}s")
        print(f"  P90 total:        {sorted(times)[int(len(times)*0.9)]:.2f}s")
    else:
        print("  No successful results to summarize.")

    print(f"{'='*90}\n")


def main():
    parser = argparse.ArgumentParser(description="Ops Assistant Performance Test")
    parser.add_argument("--url", default=DEFAULT_URL, help="WebSocket URL to test")
    parser.add_argument("--rounds", type=int, default=1, help="Number of test rounds")
    parser.add_argument("--delay", type=float, default=2.0, help="Delay between questions (seconds)")
    args = parser.parse_args()

    print(f"\n  Ops Assistant — Performance Test")
    print(f"  Target: {args.url}")
    print(f"  Rounds: {args.rounds}")
    print(f"  Questions per round: {len(TEST_QUESTIONS)}")
    print(f"  Inter-question delay: {args.delay}s")

    results = asyncio.run(run_tests(args.url, args.rounds, args.delay))
    print_summary(results)


if __name__ == "__main__":
    main()
