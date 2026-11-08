"""Small open-loop SSE load probe for the study-room course (Python 3.10+)."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import http.client
import json
import math
from pathlib import Path
import socket
import threading
import time
import uuid
from urllib.parse import urlsplit


def events(response):
    """Parse UTF-8 SSE data, including comments and multiline data fields."""
    event_name = "message"
    data = []
    for raw in response:
        line = raw.decode("utf-8").rstrip("\r\n")
        if not line:
            if data:
                yield event_name, json.loads("\n".join(data))
            event_name, data = "message", []
        elif not line.startswith(":"):
            key, _, value = line.partition(":")
            value = value.removeprefix(" ")
            if key == "event":
                event_name = value
            elif key == "data":
                data.append(value)


def stop_socket(sock):
    try:
        sock.shutdown(socket.SHUT_RDWR)
    except OSError:
        pass


def request(args, url, case, index, scheduled):
    started = time.perf_counter()
    expires = scheduled + args.deadline
    def milliseconds(now):
        return round((now - scheduled) * 1000, 2)

    request_id = uuid.uuid4().hex
    row = {"request_id": request_id, "index": index, "case": case["id"], "strategy": args.strategy,
           "start_lag_ms": milliseconds(started), "first_usable_ms": None,
           "terminal_ms": None, "outcome": "error", "correct": False}
    expected = {(f["room_id"], f["field"]): f for f in case["expected"]}
    seen = set()
    contradictory = False
    conn = None
    timer = None
    try:
        remaining = expires - time.perf_counter()
        if remaining <= 0:
            raise TimeoutError("deadline before connection")
        cls = http.client.HTTPSConnection if url.scheme == "https" else http.client.HTTPConnection
        conn = cls(url.hostname, url.port, timeout=remaining)
        conn.connect()
        sock = conn.sock
        timer = threading.Timer(max(0, expires - time.perf_counter()), stop_socket, args=(sock,))
        timer.daemon = True
        timer.start()
        path = url.path or "/"
        if url.query:
            path += "?" + url.query
        body = json.dumps({"query": case["query"], "strategy": args.strategy,
                           "stream": True}, ensure_ascii=False).encode("utf-8")
        conn.request("POST", path, body, {"Content-Type": "application/json",
                                        "Accept": "text/event-stream", "X-Request-ID": request_id})
        response = conn.getresponse()
        row["http_status"] = response.status
        if response.status != 200:
            raise ValueError("HTTP " + str(response.status))
        if response.headers.get_content_type() != "text/event-stream":
            raise ValueError("expected text/event-stream")
        for event_name, payload in events(response):
            received = time.perf_counter()
            if received >= expires:
                raise TimeoutError("deadline reading events")
            if event_name == "fact":
                key = (payload.get("room_id"), payload.get("field"))
                answer = expected.get(key)
                if answer is None:
                    continue
                # Require both the exact JSON type/value and an accepted evidence ID.
                value = payload.get("value")
                evidence = payload.get("evidence_ids", [])
                matches = (type(value) is type(answer["value"]) and value == answer["value"]
                           and isinstance(evidence, list)
                           and any(e in answer["evidence_ids"] for e in evidence))
                if matches:
                    seen.add(key)
                    if row["first_usable_ms"] is None:
                        row["first_usable_ms"] = milliseconds(received)
                else:
                    contradictory = True
            elif event_name == "done":
                status = payload.get("status")
                if status not in ("complete", "partial"):
                    raise ValueError("invalid done status")
                row["terminal_ms"] = milliseconds(received)
                row["outcome"] = status
                row["correct"] = (status == "complete" and seen == set(expected)
                                  and not contradictory)
                break
        else:
            raise EOFError("closed before done")
    except (TimeoutError, OSError, ValueError, KeyError, EOFError,
            AttributeError, http.client.HTTPException) as exc:
        row["outcome"] = ("timeout" if time.perf_counter() >= expires or
                          isinstance(exc, TimeoutError) else "error")
        row["error"] = str(exc)
    finally:
        if timer is not None:
            timer.cancel()
        if conn is not None:
            conn.close()
    row["end_ms"] = milliseconds(time.perf_counter())
    return row


def quantiles(rows, field):
    values = sorted(r[field] for r in rows if r.get(field) is not None)
    return {"n": len(values), **{
        name: values[math.ceil(p * len(values)) - 1] if values else None
        for name, p in (("p50", .50), ("p95", .95), ("p99", .99))}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--strategy", required=True)
    parser.add_argument("--cases", type=Path, default=Path(__file__).with_name("smoke-cases.json"))
    parser.add_argument("--rps", type=float, default=2)
    parser.add_argument("--seconds", type=float, default=30)
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--deadline", type=float, default=6)
    parser.add_argument("--first-slo-ms", type=float, default=800)
    parser.add_argument("--complete-slo-ms", type=float, default=2500)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if min(args.rps, args.seconds, args.workers, args.deadline, args.first_slo_ms, args.complete_slo_ms) <= 0:
        parser.error("rate, duration, workers, and deadline must be positive")
    count = int(args.rps * args.seconds)
    url = urlsplit(args.url)
    if not count or url.scheme not in ("https", "http") or not url.hostname:
        parser.error("specify a valid HTTP(S) endpoint and at least one arrival")
    cases = json.loads(args.cases.read_text(encoding="utf-8-sig"))
    if not cases or not all(c.get("expected") for c in cases):
        parser.error("each case must include expected facts")
    output = []
    futures = []
    slots = threading.BoundedSemaphore(args.workers)
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        base = time.perf_counter()
        for i in range(count):
            due = base + i / args.rps
            time.sleep(max(0, due - time.perf_counter()))
            case = cases[i % len(cases)]
            if not slots.acquire(blocking=False):
                output.append({"index": i, "strategy": args.strategy, "case": case["id"],
                               "outcome": "loadgen_dropped", "correct": False})
                continue
            future = pool.submit(request, args, url, case, i, due)
            future.add_done_callback(lambda completed: slots.release())
            futures.append(future)
        output.extend(f.result() for f in futures)
    output.sort(key=lambda r: r["index"])
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as handle:
        for row in output:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    outcomes = {key: sum(r["outcome"] == key for r in output)
                for key in ("complete", "partial", "error", "timeout", "loadgen_dropped")}
    attempted = count - outcomes["loadgen_dropped"]
    first_good = sum(r.get("first_usable_ms") is not None and
                     r["first_usable_ms"] <= args.first_slo_ms for r in output)
    complete_good = sum(r["correct"] and r["terminal_ms"] <= args.complete_slo_ms
                        for r in output)
    print(json.dumps({"offered": count, "attempted": attempted, "outcomes": outcomes,
                      "first_slo_ms": args.first_slo_ms, "first_within_slo": first_good,
                      "complete_slo_ms": args.complete_slo_ms, "correct_within_slo": complete_good,
                      "correct_complete": sum(r["correct"] for r in output),
                      "start_lag_ms": quantiles(output, "start_lag_ms"),
                      "first_usable_ms": quantiles(output, "first_usable_ms"),
                      "terminal_ms": quantiles(output, "terminal_ms"),
                      "attempt_end_ms": quantiles(output, "end_ms")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
