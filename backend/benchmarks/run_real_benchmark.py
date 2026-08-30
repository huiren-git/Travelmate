"""Run reproducible real-model benchmarks against an isolated TravelMate API."""
import argparse
import json
import os
import time
import uuid
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

ROOT = Path(__file__).parent
API = os.getenv("BENCHMARK_API_BASE", "http://127.0.0.1:8000/api/v1")
RUN_ID = datetime.now().strftime("%Y%m%d-%H%M%S")
OUT = ROOT / "artifacts" / RUN_ID
SCENARIOS = json.loads((ROOT / "scenarios.json").read_text(encoding="utf-8"))
PRICES = json.loads((ROOT / "price_snapshot_2026-08-30.json").read_text(encoding="utf-8"))


def _sse(response, started):
    events, first, final = [], None, None
    event, data = "message", []
    for raw in response.iter_lines(decode_unicode=True):
        if not raw:
            payload = json.loads("\n".join(data)) if data else None
            now = time.perf_counter()
            events.append({"event": event, "data": payload, "elapsed_ms": round((now - started) * 1000, 2)})
            if first is None and event in {"node", "done", "error", "stopped"}:
                first = now
            if event in {"done", "error", "stopped"}:
                final = payload
            event, data = "message", []
        elif raw.startswith("event:"):
            event = raw[6:].strip()
        elif raw.startswith("data:"):
            data.append(raw[5:].strip())
    return events, first, final


def _price_period():
    now = datetime.now(ZoneInfo("Asia/Shanghai"))
    minute = now.hour * 60 + now.minute
    return "peak" if 540 <= minute < 720 or 840 <= minute < 1080 else "off_peak"


def _trace_metrics(trace_ids):
    calls, models, prompt, completion, total = [], [], 0, 0, 0
    for trace_id in trace_ids:
        detail = requests.get(f"{API}/traces/{trace_id}", timeout=30).json()["data"]
        stack = list(detail.get("spans", []))
        while stack:
            node = stack.pop()
            stack.extend(node.get("children", []))
            for event in node.get("llm_events", []):
                calls.append(event); models.append(event.get("model_name"))
                prompt += int(event.get("prompt_tokens") or 0)
                completion += int(event.get("response_tokens") or 0)
                total += int(event.get("total_tokens") or 0)
    period = _price_period(); price = PRICES[period]
    cost = prompt / 1_000_000 * price["input_cache_miss"] + completion / 1_000_000 * price["output"]
    return {"trace_ids": trace_ids, "models": sorted({x for x in models if x}), "llm_calls": len(calls),
            "prompt_tokens": prompt, "completion_tokens": completion, "total_tokens": total,
            "estimated_cost_usd": round(cost, 8), "price_period": period,
            "cost_assumption": "input tokens billed as cache_miss; cached-token split is unavailable in trace events"}


def _hard_rules(snapshot, rules, all_finals):
    values = ((snapshot or {}).get("values") or {})
    itinerary = values.get("daily_itinerary") or values.get("draft_daily_itinerary") or []
    text = json.dumps(itinerary, ensure_ascii=False)
    observed = {"valid_structure": bool(itinerary and all(day.get("items") for day in itinerary)),
                "one_day": len(itinerary) == 1, "two_days": len(itinerary) == 2,
                "three_days": len(itinerary) == 3, "seven_days": len(itinerary) == 7,
                "no_seafood": not any(x in text for x in ("海鲜", "海蛎", "螃蟹", "虾", "鱼生")),
                "budget_handling": bool(values.get("budget") or values.get("validation_report")),
                "user_isolation": len(all_finals) == 2 and all_finals[0].get("values") != all_finals[1].get("values"),
                "reference_adopted": bool(values.get("daily_itinerary") or values.get("draft_daily_itinerary"))}
    return {rule: observed.get(rule, False) for rule in rules}


def _stream(path, user_id, payload, started):
    response = requests.post(f"{API}{path}", headers={"X-User-Id": user_id}, json=payload, stream=True, timeout=360)
    response.raise_for_status()
    return _sse(response, started)


def run_once(scenario, index):
    started = time.perf_counter(); default_thread = f"bench_{scenario['id'].lower()}_{index}_{uuid.uuid4().hex[:8]}"
    events, trace_ids, finals, first = [], [], [], None
    for step in scenario["steps"]:
        thread = step.get("thread_id") or default_thread; user_id = step.get("user_id") or scenario["user_id"]
        if step.get("kind") == "reference_adopt":
            path = f"/reference/{step['reference_id']}/adopt/stream"
            payload = {key: step[key] for key in ("start_date", "duration", "travelers", "destination")}
            payload.update({"thread_id": thread, "structured_preferences": step.get("structured_preferences", {})})
        else:
            path = "/chat/stream"; payload = {"thread_id": thread, "message": step["message"], "current_time": step.get("current_time", "2026-08-30T09:00:00+08:00")}
        got, step_first, final = _stream(path, user_id, payload, started)
        events.extend(got); first = first or step_first; finals.append(final or {})
        if final and final.get("trace_id"): trace_ids.append(final["trace_id"])
        if step.get("resume") and final and final.get("tasks"):
            got, resume_first, final = _stream("/chat/resume", user_id, {"thread_id": thread, "user_decision": {"action": step["resume"]}}, started)
            events.extend(got); first = first or resume_first; finals[-1] = final or {}
            if final and final.get("trace_id"): trace_ids.append(final["trace_id"])
    final = finals[-1] if finals else {}; elapsed = round((time.perf_counter() - started) * 1000, 2)
    artifact = {"run_id": RUN_ID, "scenario_id": scenario["id"], "index": index, "input": scenario,
                "events": events, "final": final, "all_finals": finals,
                "ttft_ms": round((first - started) * 1000, 2) if first else None, "e2e_ms": elapsed,
                "hard_rules": _hard_rules(final, scenario["rules"], finals), "metrics": _trace_metrics(trace_ids), "price_snapshot": PRICES}
    (OUT / f"{scenario['id']}-{index}.json").write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")
    return artifact


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--ids", nargs="*"); parser.add_argument("--repetitions", type=int, default=3)
    args = parser.parse_args(); selected = [s for s in SCENARIOS if not args.ids or s["id"] in args.ids]
    if not selected: raise SystemExit("No selected scenarios")
    OUT.mkdir(parents=True, exist_ok=True)
    rows = [run_once(s, i) for s in selected for i in range(1, args.repetitions + 1)]
    (OUT / "results.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {"run_id": RUN_ID, "scenario_count": len(selected), "sample_count": len(rows),
               "hard_rule_pass_rate": sum(all(x["hard_rules"].values()) for x in rows) / len(rows), "artifact_dir": str(OUT)}
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"); print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__": main()
