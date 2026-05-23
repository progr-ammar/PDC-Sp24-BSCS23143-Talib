"""
StudySync - FastAPI Backend with Circuit Breaker Pattern
Author : Muhammad Ammar Bin Talib
Student: BSCS23143
Problem: Fault Tolerance — LLM API acting as a single point of failure

Run with:
    uvicorn main:app --reload --port 8000
"""

import time
import random
import threading
from enum import Enum

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

# ---------------------------------------------------------------------------
# Custom Circuit Breaker Implementation
# ---------------------------------------------------------------------------

class CBState(Enum):
    CLOSED   = "CLOSED"    # Normal operation — requests pass through
    OPEN     = "OPEN"      # Tripped — requests are SHORT-CIRCUITED immediately
    HALF_OPEN = "HALF_OPEN" # Recovery probe — one test request is allowed


class CircuitBreaker:
    """
    A thread-safe Circuit Breaker that wraps any callable.

    States:
        CLOSED   → calls go through; failures are counted.
        OPEN     → calls are blocked; a fallback is returned immediately.
        HALF_OPEN→ after `recovery_timeout` seconds one probe call is allowed.
                   Success  → CLOSED.  Failure → OPEN again.

    Args:
        failure_threshold : consecutive failures before tripping to OPEN.
        recovery_timeout  : seconds to wait in OPEN before probing (HALF_OPEN).
    """

    def __init__(self, failure_threshold: int = 3, recovery_timeout: float = 10.0):
        self.failure_threshold = failure_threshold
        self.recovery_timeout  = recovery_timeout

        self._state          = CBState.CLOSED
        self._failure_count  = 0
        self._last_opened_at = 0.0
        self._lock           = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def state(self) -> CBState:
        """Return current state, automatically transitioning OPEN → HALF_OPEN."""
        with self._lock:
            if (
                self._state == CBState.OPEN
                and time.monotonic() - self._last_opened_at >= self.recovery_timeout
            ):
                self._state = CBState.HALF_OPEN
            return self._state

    def call(self, func, *args, fallback=None, **kwargs):
        """
        Execute `func`. If the breaker is OPEN return `fallback` immediately.
        Record successes and failures to manage state transitions.
        """
        current = self.state  # may flip OPEN → HALF_OPEN

        if current == CBState.OPEN:
            # Circuit is open — skip the call entirely
            return fallback

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as exc:
            self._on_failure()
            raise exc

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _on_success(self):
        with self._lock:
            self._failure_count = 0
            self._state = CBState.CLOSED

    def _on_failure(self):
        with self._lock:
            self._failure_count += 1
            if self._failure_count >= self.failure_threshold:
                self._state          = CBState.OPEN
                self._last_opened_at = time.monotonic()


# ---------------------------------------------------------------------------
# Mock LLM — simulates an unreliable external API
# ---------------------------------------------------------------------------

# Global counter so we can make the first N calls succeed, then always fail
_call_counter = 0
_call_counter_lock = threading.Lock()

# After this many successful calls the mock LLM starts crashing
CRASH_AFTER = 2


def mock_llm_api(prompt: str) -> str:
    """
    Simulates an external LLM API that:
      - Succeeds on the first CRASH_AFTER calls.
      - Then raises a TimeoutError (like a 60-second hang) on every subsequent call.

    In a real app this would be:  openai.ChatCompletion.create(...)
    """
    global _call_counter
    with _call_counter_lock:
        _call_counter += 1
        call_number = _call_counter

    if call_number > CRASH_AFTER:
        # Simulate a network timeout / hung external service
        # (We raise immediately to avoid actually sleeping 60 s in tests)
        raise TimeoutError(
            f"LLM API timed out on call #{call_number} — external service is down."
        )

    # Happy path — return a fake LLM response
    return f"[LLM Response #{call_number}] Here is a study summary for: '{prompt}'"


# ---------------------------------------------------------------------------
# Circuit Breaker instance (shared across all requests)
# ---------------------------------------------------------------------------

llm_breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=10.0)

# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="StudySync API",
    description="Resilient backend with Circuit Breaker for LLM calls.",
    version="1.0.0",
)

# ---------------------------------------------------------------------------
# STRICT REQUIREMENT: Middleware that injects X-Student-ID on every response
# ---------------------------------------------------------------------------

@app.middleware("http")
async def add_student_id_header(request: Request, call_next):
    """
    Assignment requirement: every API response MUST include the header
        X-Student-ID: BSCS23143
    This middleware intercepts the response and adds it unconditionally.
    """
    response = await call_next(request)
    response.headers["X-Student-ID"] = "BSCS23143"
    return response


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/", summary="Health check")
async def root():
    return {"status": "ok", "service": "StudySync API"}


@app.get("/circuit-status", summary="Inspect Circuit Breaker state")
async def circuit_status():
    """Returns the current state of the LLM circuit breaker."""
    return {
        "state"          : llm_breaker.state.value,
        "failure_count"  : llm_breaker._failure_count,
        "failure_threshold": llm_breaker.failure_threshold,
        "recovery_timeout_seconds": llm_breaker.recovery_timeout,
    }


@app.get("/summarize", summary="Generate a study summary via LLM")
async def summarize(topic: str = "photosynthesis"):
    """
    Asks the LLM to summarise a study topic.

    WITHOUT Circuit Breaker:
        If the LLM hangs, FastAPI blocks the thread for 60 s.
        Every subsequent user is also stuck — cascading failure.

    WITH Circuit Breaker:
        After `failure_threshold` consecutive failures the breaker OPENS.
        All further requests are SHORT-CIRCUITED in microseconds and
        receive a polite fallback message — no blocking, no cascade.
    """

    # Fallback payload returned when the circuit is OPEN
    fallback_payload = {
        "source" : "fallback",
        "circuit": llm_breaker.state.value,
        "message": (
            "Our AI tutor is temporarily unavailable. "
            "Please try again in a few seconds, or browse your saved notes. "
            "We're working on restoring the service."
        ),
    }

    try:
        result = llm_breaker.call(
            mock_llm_api,
            topic,
            fallback=None,   # sentinel — None means we'll use fallback_payload below
        )

        if result is None:
            # Circuit is OPEN — breaker returned the sentinel None
            return JSONResponse(
                status_code=503,
                content={
                    **fallback_payload,
                    "circuit": llm_breaker.state.value,
                },
            )

        # Happy path
        return {
            "source" : "llm",
            "circuit": llm_breaker.state.value,
            "message": result,
        }

    except TimeoutError as exc:
        # Circuit is CLOSED or HALF_OPEN but the call just failed — breaker recorded it
        return JSONResponse(
            status_code=503,
            content={
                "source" : "error",
                "circuit": llm_breaker.state.value,
                "error"  : str(exc),
                "message": fallback_payload["message"],
            },
        )


@app.post("/reset-demo", summary="Reset mock LLM counter (for demo purposes only)")
async def reset_demo():
    """
    Resets the global call counter so the demo can be run multiple times
    without restarting the server.  NOT for production use.
    """
    global _call_counter
    with _call_counter_lock:
        _call_counter = 0
    llm_breaker._failure_count = 0
    llm_breaker._state         = CBState.CLOSED
    return {"status": "reset", "circuit": llm_breaker.state.value}
