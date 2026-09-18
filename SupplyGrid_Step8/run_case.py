"""Standalone Step 8 entry point. Required scenario assumptions are explicit."""
import argparse
from pathlib import Path
from adapters import Tools
from state.case_state import Scenario
from orchestrator.orchestrator import Orchestrator


def arguments():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--project-root", required=True)
    p.add_argument("--data", required=True, help="Corrected 14-table CSV directory or ZIP")
    p.add_argument("--v2-root", required=True, help="Directory containing optimize_mitigation_v2.py")
    p.add_argument("--extensions", required=True, help="Directory containing CSVs 15–17")
    p.add_argument("--risk-root", required=True, help="Frozen SupplyGrid_Step7 directory")
    p.add_argument("--risk-features", default=None)
    p.add_argument("--supplier", required=True)
    p.add_argument("--capacity-loss", required=True, type=float)
    p.add_argument("--duration", required=True, type=int)
    p.add_argument("--assumed-delay-days", required=True, type=int)
    p.add_argument("--daily-penalty-rate", default="0.001")
    p.add_argument("--uncovered-unit-cost-cents", default=0, type=int)
    p.add_argument("--route-capacity-mode", choices=["single-batch", "per-consignment"], default="single-batch")
    p.add_argument("--time-limit-seconds", type=int, default=60)
    p.add_argument("--snapshot-what-if", action="store_true")
    p.add_argument("--analyze-low-risk-reason", default="")
    p.add_argument("--output", required=True)
    return p


def configured(args):
    scenario = Scenario(args.supplier, args.capacity_loss, args.duration, args.assumed_delay_days,
                        args.daily_penalty_rate, args.uncovered_unit_cost_cents,
                        args.route_capacity_mode, args.time_limit_seconds,
                        args.snapshot_what_if, args.analyze_low_risk_reason)
    tools = Tools(args.project_root, args.data, args.v2_root, args.extensions,
                  args.risk_root, args.risk_features)
    return tools, scenario


def main():
    args = arguments().parse_args()
    tools, scenario = configured(args)
    case = Orchestrator(tools).run(scenario, args.output)
    print("Case:", case["case_id"], "Status:", case["status"])
    if "optimization" in case["messages"]:
        result = case["messages"]["optimization"]["data"]
        audit = result["audit"]
        print("Solver:", result["status"], "Protected orders:", audit["orders_protected"],
              "Unresolved orders:", len(audit["unresolved_order_ids"]),
              "Conditional objective USD:", result["objective_value"])
    print("Analysis only. No actions executed. Human review required.")


if __name__ == "__main__":
    main()
