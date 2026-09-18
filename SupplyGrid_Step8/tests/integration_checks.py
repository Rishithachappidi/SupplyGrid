"""Optional real-tool integration checks, without source mutations or execution."""
import copy
import sys
from dataclasses import replace
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from run_case import arguments, configured
from orchestrator.orchestrator import Orchestrator
from common import write_json


def main():
    args = arguments().parse_args()
    tools, base = configured(args)
    output = Path(args.output)
    if output.exists():
        raise FileExistsError("Use a fresh integration-check directory")
    coordinator = Orchestrator(tools)
    checks = []
    # Demonstrate fail-closed date mismatch with the actual frozen model.
    mismatch = replace(base, snapshot_what_if=False, analyze_low_risk_reason="")
    try:
        coordinator.run(mismatch, output / "date_mismatch")
    except ValueError as error:
        if "dates differ" not in str(error):
            raise
        checks.append({"check": "date mismatch blocks downstream tools", "status": "PASSED"})
    else:
        raise AssertionError("Date mismatch unexpectedly accepted")
    # S037 is LOW under the actual frozen model, not a fabricated test probability.
    skipped = coordinator.run(replace(base, snapshot_what_if=True, analyze_low_risk_reason=""), output / "low_risk_skipped")
    assert skipped["status"] == "SKIPPED_LOW_RISK"
    assert set(skipped["messages"]) == {"risk"}
    checks.append({"check": "actual low risk skips downstream tools", "status": "PASSED"})
    # Explicit research sensitivity: extra service cost, not an observed financial loss.
    sensitivity = replace(base, snapshot_what_if=True, uncovered_unit_cost_cents=50000,
                          analyze_low_risk_reason="Academic production-path sensitivity; manually reviewed")
    case = coordinator.run(sensitivity, output / "production_path_sensitivity")
    messages = case["messages"]
    result = messages["optimization"]["data"]
    assert result["audit"]["production_orders"] > 0
    assert result["audit"]["status"] == "PASSED"
    ctx = tools.modules["optimize_mitigation_v2"].Context(
        tools.tables, tools.ext, messages["impact"]["data"], messages["mitigation"]["data"],
        messages["financial"]["data"], sensitivity.route_capacity_mode)
    tampered = copy.deepcopy(result["plan"])
    # A second copy of an already selected path must fail audit, not double-protect an order.
    category = "finished_transfers" if tampered["finished_transfers"] else "production_jobs"
    tampered[category].append(copy.deepcopy(tampered[category][0]))
    try:
        tools.modules["optimize_mitigation_v2"].audit_plan(ctx, tampered, sensitivity.uncovered_unit_cost_cents)
    except (ValueError, ArithmeticError) as error:
        if "more than once" not in str(error):
            raise
        checks.append({"check": "independent audit rejects duplicate selected recovery path", "status": "PASSED"})
    else:
        raise AssertionError("Tampered plan unexpectedly accepted")
    checks.append({"check": "production/procurement pathway sensitivity obeys independent V2 audit", "status": "PASSED",
                   "protected_orders": result["audit"]["orders_protected"],
                   "production_orders": result["audit"]["production_orders"],
                   "selected_procurement_lots": len(result["plan"]["procurement_lots"]),
                   "conditional_objective_usd": result["objective_value"]})
    tools.assert_unchanged()
    write_json(output / "integration_report.json", {"checks": checks, "source_inputs_unchanged": True,
               "actions_executed": False, "scope": "Explicit historical what-if; production run adds USD 500 per unresolved unit as a synthetic service-cost sensitivity"})
    print("Real integration checks passed:", len(checks))


if __name__ == "__main__":
    main()
