"""Same data, scenario and V2 optimizer; centralized versus role-agent coordination."""
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from run_case import arguments, configured
from common import write_json
from orchestrator.orchestrator import Orchestrator, review_gate


def central(tools, scenario):
    start = time.perf_counter()
    risk = tools.risk_prediction(scenario.supplier_id)
    if not review_gate(risk, scenario, tools.snapshot):
        return {"status": "SKIPPED_LOW_RISK", "result": None, "elapsed_seconds": time.perf_counter()-start}
    impact = tools.graph_impact(scenario)
    financial = tools.financial(impact, scenario)
    options = tools.mitigation(impact, scenario)
    result = tools.optimize(impact, financial, options, scenario)
    return {"status": "RECOMMENDATION_READY", "result": result,
            "impact_orders": len(impact["potential_order_ids"]),
            "candidate_count": len(options["candidates"]),
            "elapsed_seconds": time.perf_counter()-start}


def signature(result):
    if result is None:
        return None
    a = result["audit"]
    return {"status": result["status"], "total_cost_cents": a["total_cost_cents"],
            "orders_protected": a["orders_protected"],
            "unresolved_order_ids": sorted(a["unresolved_order_ids"]), "audit": a["status"]}


def main():
    p = arguments()
    p.add_argument("--repetitions", type=int, default=2)
    args = p.parse_args()
    if args.repetitions < 1:
        p.error("Repetitions must be positive")
    root = Path(args.output)
    if root.exists():
        raise FileExistsError("Use a fresh benchmark output directory")
    tools, scenario = configured(args)
    # Warm model equally; exclude dataset/graph loading from both timings.
    tools.risk_prediction(scenario.supplier_id)
    rows = []
    for i in range(args.repetitions):
        def agents():
            begin = time.perf_counter()
            state = Orchestrator(tools).run(scenario, root / f"agents_{i+1}")
            result = state["messages"].get("optimization", {}).get("data")
            return {"status": state["status"], "result": result,
                    "elapsed_seconds": time.perf_counter()-begin}
        # Alternate order to reduce warm-cache bias. Serialization/validation overhead
        # is included for agents; base loading is not. No universal speed claim.
        if i % 2:
            b, a = agents(), central(tools, scenario)
        else:
            a, b = central(tools, scenario), agents()
        tools.assert_unchanged()
        sa, sb = signature(a["result"]), signature(b["result"])
        parity = a["status"] == b["status"] and sa == sb
        rows.append({"repeat": i+1, "centralized_seconds": a["elapsed_seconds"],
                     "agents_seconds": b["elapsed_seconds"], "outcome_parity": parity,
                     "centralized_outcome": sa, "agents_outcome": sb,
                     "constraint_violations": 0 if sb and sb["audit"] == "PASSED" else None})
        if not parity:
            raise AssertionError("Outcomes differ: investigate tie-breaking or handoff errors")
    write_json(root / "comparison.json", {"scenario": scenario.as_dict(), "rows": rows,
               "same_optimizer": True, "original_inputs_unchanged": True,
               "interpretation": "Architecture equivalence check, not evidence of improved decision quality or scalability. Agent timing includes tracing, schema validation, serialization and immutability verification. Warm model; shared preloaded graph; alternate execution order.",
               "limitations": ["Synthetic historical snapshot demonstration", "Small experiment; no statistical superiority claim", "No independent routing/replanning policies tested"]})
    print("Verified parity across", len(rows), "repetitions")


if __name__ == "__main__":
    main()
