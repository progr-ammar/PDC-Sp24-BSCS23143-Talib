Muhammad Ammar Bin Talib - BSCS23143

# PDC-Sp24-BSCS23143-Talib

**Course:** Parallel and Distributed Computing (PDC) — Spring 2024  
**Assignment 4:** Building Resilient Distributed Systems  
**Problem Solved:** Problem 3 — Fault Tolerance (Circuit Breaker Pattern for LLM API)

---

## Project Structure

```
PDC-Sp24-BSCS23143-Talib/
├── main.py          # FastAPI application with Circuit Breaker + Middleware
├── test.py          # Stress-test script that triggers and proves the CB
├── FInalReport.pdf       # Part 1 (Analysis) + Part 2 (Design + Diagram)
└── README.md        # This file
```

---

## Prerequisites

- Python 3.9 or higher
- `pip` package manager

Install dependencies:

```bash
pip install fastapi uvicorn requests
```

---

## How to Run the FastAPI Server

Open a terminal and run:

```bash
uvicorn main:app --reload --port 8000
```

You should see:

```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
```

---

## How to Run the Test Script

Open a **second terminal** (keep the server running in the first one) and run:

```bash
python test.py
```

### What the test does

1. Resets the demo counter on the server so you start from a clean state.
2. Fires **10 sequential GET requests** to `/summarize?topic=photosynthesis`.
3. For every response it prints the HTTP status code, circuit breaker state, source, and response time.
4. Verifies the mandatory `X-Student-ID: BSCS23143` header is present on every response.

### Expected output pattern

| Request | Status | Source     | Circuit State | Behaviour              |
|---------|--------|------------|---------------|------------------------|
| 1 – 2   | 200 OK | `llm`      | `CLOSED`      | Normal LLM response    |
| 3 – 5   | 503    | `error`    | `CLOSED`      | LLM fails, CB counting |
| 6 – 10  | 503    | `fallback` | `OPEN`        | CB trips — instant response, no blocking |

---

## API Endpoints

| Method | Path              | Description                          |
|--------|-------------------|--------------------------------------|
| GET    | `/`               | Health check                         |
| GET    | `/summarize`      | LLM study summariser (Circuit Breaker protected) |
| GET    | `/circuit-status` | Inspect the live circuit breaker state |
| POST   | `/reset-demo`     | Reset mock LLM counter (demo only)   |

Interactive docs available at: `http://127.0.0.1:8000/docs`

---

## Middleware — X-Student-ID Header

Every API response includes the header:

```
X-Student-ID: BSCS23143
```

This is enforced by the `add_student_id_header` middleware in `main.py` and verified automatically by `test.py`.

---

## Demo Video

A 2-minute screen-share video demonstrating:
- The server hanging/failing **without** the Circuit Breaker.
- The server returning instant fallbacks **with** the Circuit Breaker.

Link: Video uploaded directly on GCR
