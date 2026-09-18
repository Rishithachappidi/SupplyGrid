"""Dependency-ordered agents; failures terminate the case rather than invent outputs."""
import json
import time
import uuid
from datetime import date
from pathlib import Path
from common import digest, safe, now, write_json
from state.case_state import CaseState
from agents.risk_agent import RiskAgent
from agents.graph_impact_agent import GraphImpactAgent
from agents.financial_agent import FinancialAgent
from agents.mitigation_agent import MitigationAgent
from agents.optimization_agent import OptimizationAgent

AGENTS = [RiskAgent, GraphImpactAgent, FinancialAgent, MitigationAgent, OptimizationAgent]


def review_gate(risk, scenario, snapshot):
    date.fromisoformat(str(risk["date"]))
    if risk["date"] != snapshot and not scenario.snapshot_what_if:
        raise ValueError("Forecast/operational dates differ. Explicit --snapshot-what-if is required for an academic historical demonstration.")
    return risk["risk_level"] == "HIGH" or bool(scenario.analyze_low_risk_reason)


class Orchestrator:
    def __init__(self, tools):
        self.tools = tools

    def run(self, scenario, output):
        output = Path(output).resolve()
        # Never permit output within datasets, existing packages or source directories.
        forbidden = [self.tools.data,
                     self.tools.extensions, self.tools.risk, self.tools.v2]
        if output == self.tools.project:
            raise ValueError("Output cannot overwrite the project root")
        if any(output == p or p in output.parents for p in forbidden):
            raise ValueError("Output must be separate from source data and existing step packages")
        if output.exists():
            raise FileExistsError("Case directory exists; use a new output directory")
        output.mkdir(parents=True)
        state = CaseState("SG8-" + uuid.uuid4().hex, scenario)
        trace = []
        start = time.perf_counter()

        def record(role, event, **detail):
            entry = dict(sequence=len(trace)+1, timestamp_utc=now(), agent=role, event=event, **detail)
            trace.append(entry)
            with (output / "decision_trace.jsonl").open("a", encoding="utf8") as stream:
                stream.write(json.dumps(safe(entry), allow_nan=False) + "\n")

        record("orchestrator", "STARTED", scenario=scenario.as_dict(), snapshot=self.tools.snapshot,
               source_manifest_sha256=digest(self.tools.before), assumptions_supplied_by="operator",
               downstream_scope="human-reviewed what-if", execution_authorized=False)
        try:
            for agent_type in AGENTS:
                agent = agent_type(self.tools)
                record(agent.role, "STARTED", input_sha256=digest({"scenario": scenario.as_dict(),
                       "handoffs": {k: digest(v) for k, v in state.messages.items()}}))
                before = time.perf_counter()
                try:
                    message = agent.run(state)
                    state.add(agent.role, message)
                except Exception as error:
                    record(agent.role, "FAILED", error_type=type(error).__name__, error=str(error),
                           duration_seconds=time.perf_counter()-before)
                    raise
                record(agent.role, "SUCCEEDED", output_sha256=digest(message),
                       duration_seconds=time.perf_counter()-before, evidence=message["evidence"])
                write_json(output / (agent.role + ".json"), message)
                if agent.role == "risk":
                    risk = message["data"]
                    record("orchestrator", "RISK_GATE", risk_level=risk["risk_level"],
                           probability=risk["disruption_probability"], threshold=risk["threshold"],
                           forecast_origin=risk["date"], operational_snapshot=self.tools.snapshot,
                           snapshot_what_if=scenario.snapshot_what_if,
                           low_risk_review_reason=scenario.analyze_low_risk_reason)
                    if not review_gate(risk, scenario, self.tools.snapshot):
                        state.status = "SKIPPED_LOW_RISK"
                        break
            else:
                state.status = "RECOMMENDATION_READY"
        except Exception as error:
            state.status = "FAILED"
            record("orchestrator", "FAILED", error_type=type(error).__name__, error=str(error))
            raise
        finally:
            try:
                self.tools.assert_unchanged()
                record("orchestrator", "SOURCE_IMMUTABILITY_PASSED")
            except Exception as error:
                state.status = "FAILED"
                record("orchestrator", "SOURCE_IMMUTABILITY_FAILED", error=str(error))
                raise
            finally:
                record("orchestrator", "FINISHED", status=state.status,
                       elapsed_seconds=time.perf_counter()-start, actions_executed=False)
                write_json(output / "case_state.json", state.serialized())
                write_json(output / "source_manifest.json", self.tools.before)
        return state.serialized()
