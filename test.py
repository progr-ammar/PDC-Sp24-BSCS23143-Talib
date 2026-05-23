"""
test.py — Circuit Breaker Stress Test for StudySync /summarize endpoint
========================================================================
Author : Muhammad Ammar Bin Talib  |  BSCS23143

This script:
  1. Resets the demo counter so each test run starts fresh.
  2. Fires 10 sequential GET requests to /summarize.
  3. Prints the HTTP status, circuit state, and source for every response.
  4. Verifies that every response carries the X-Student-ID: BSCS23143 header.
  5. Confirms that once the breaker trips the server stops blocking and
     returns 503 fallbacks within milliseconds.

Prerequisites:
    pip install requests
    # In a separate terminal:
    uvicorn main:app --reload --port 8000

Run:
    python test.py
"""

import time
import requests

BASE_URL = "http://127.0.0.1:8000"
TOTAL_REQUESTS = 10


def separator(char="─", width=65):
    print(char * width)


def reset_demo():
    """Reset the mock LLM counter and circuit breaker state on the server."""
    r = requests.post(f"{BASE_URL}/reset-demo")
    r.raise_for_status()
    data = r.json()
    print(f"[RESET]  Server state reset — circuit is now: {data['circuit']}")


def check_student_header(response: requests.Response, req_num: int):
    """Assert the mandatory X-Student-ID header is present and correct."""
    sid = response.headers.get("X-Student-ID", "MISSING")
    ok  = "✓" if sid == "BSCS23143" else "✗ WRONG"
    print(f"         X-Student-ID: {sid}  [{ok}]")


def blast_endpoint():
    separator("═")
    print("  StudySync — Circuit Breaker Stress Test")
    print(f"  Target : {BASE_URL}/summarize?topic=photosynthesis")
    print(f"  Rounds : {TOTAL_REQUESTS}")
    separator("═")

    reset_demo()
    separator()

    for i in range(1, TOTAL_REQUESTS + 1):
        t0 = time.perf_counter()
        try:
            resp = requests.get(
                f"{BASE_URL}/summarize",
                params={"topic": "photosynthesis"},
                timeout=5,  # client-side safety; should never be hit when CB is open
            )
            elapsed_ms = (time.perf_counter() - t0) * 1000
            data = resp.json()

            source  = data.get("source",  "?")
            circuit = data.get("circuit", "?")
            status  = resp.status_code

            # Colour the status visually
            tag = {200: "✅ 200 OK ", 503: "⚠️  503 SVC"}.get(status, f"❓ {status}")

            print(
                f"[Req {i:02d}] {tag}  |  source={source:<8}  "
                f"circuit={circuit:<10}  ({elapsed_ms:.1f} ms)"
            )
            check_student_header(resp, i)

        except requests.exceptions.ConnectionError:
            elapsed_ms = (time.perf_counter() - t0) * 1000
            print(
                f"[Req {i:02d}] ❌ CONNECTION ERROR — is the server running?  "
                f"({elapsed_ms:.1f} ms)"
            )

        separator()


def print_summary():
    """Fetch and print the final circuit breaker state."""
    try:
        r = requests.get(f"{BASE_URL}/circuit-status")
        d = r.json()
        print("\n  Final Circuit Breaker Status")
        separator()
        for k, v in d.items():
            print(f"  {k:<30}: {v}")
        separator()
    except Exception as exc:
        print(f"Could not fetch circuit status: {exc}")


if __name__ == "__main__":
    blast_endpoint()
    print_summary()
    print()
    print("  What you should observe:")
    print("  • Requests 1-2  → source=llm,      circuit=CLOSED  (200 OK, fast)")
    print("  • Requests 3-5  → source=error,    circuit grows   (503, still fast)")
    print("  • Requests 6+   → source=fallback, circuit=OPEN    (503, <1 ms!)")
    print("  • Every response carries  X-Student-ID: BSCS23143")
    print()
