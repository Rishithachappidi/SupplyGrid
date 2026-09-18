import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import validate_message, safe, digest
from state.case_state import Scenario, CaseState
from orchestrator.orchestrator import review_gate, Orchestrator


def risk_message(case="test"):
    return {"case_id": case, "supplier_id": "S037", "agent": "risk", "status": "SUCCEEDED",
            "actions_executed": False, "evidence": [{"tool": "risk_core", "path": "trusted/risk_core.py", "sha256": "a"*64}],
            "data": {"supplier_id": "S037", "date": "2028-12-30", "disruption_probability": .12,
                     "threshold": .15, "risk_rank": 3, "risk_level": "LOW", "horizon_days": 7,
                     "confirmed_disruption": False, "explanations": []}}


class TestStep8(unittest.TestCase):
    def test_scenario_valid(self):
        self.assertEqual(Scenario("S037",80,10,10).duration_days,10)

    def test_bad_scenarios(self):
        for args in [("S9999",80,10,10),("S037",float("nan"),10,10),
                     ("S037",101,10,10),("S037",80,True,10),("S037",80,10,0)]:
            with self.assertRaises(ValueError): Scenario(*args)

    def test_invalid_cost(self):
        with self.assertRaises(ValueError): Scenario("S037",80,10,10,uncovered_unit_cost_cents=-1)

    def test_short_review(self):
        with self.assertRaises(ValueError): Scenario("S037",80,10,10,analyze_low_risk_reason="x")

    def test_valid_schema(self):
        self.assertEqual(validate_message("risk",risk_message(),"test","S037")["data"]["risk_level"],"LOW")

    def test_cross_case(self):
        with self.assertRaises(ValueError): validate_message("risk",risk_message(),"other","S037")

    def test_wrong_supplier(self):
        m=risk_message();m["data"]["supplier_id"]="S015"
        with self.assertRaises(ValueError): validate_message("risk",m,"test","S037")

    def test_probability_rejection(self):
        for value in [-1,1.1,float("inf"),float("nan")]:
            m=risk_message();m["data"]["disruption_probability"]=value
            with self.assertRaises(Exception): validate_message("risk",m,"test","S037")

    def test_no_execution_claim(self):
        m=risk_message();m["actions_executed"]=True
        with self.assertRaises(Exception): validate_message("risk",m,"test","S037")

    def test_no_confirmation_claim(self):
        m=risk_message();m["data"]["confirmed_disruption"]=True
        with self.assertRaises(Exception): validate_message("risk",m,"test","S037")

    def test_threshold_consistency(self):
        m=risk_message();m["data"]["risk_level"]="HIGH"
        with self.assertRaises(ValueError): validate_message("risk",m,"test","S037")

    def test_temporal_block(self):
        with self.assertRaises(ValueError): review_gate(risk_message()["data"],Scenario("S037",80,10,10),"2027-01-01")

    def test_low_risk_skip(self):
        self.assertFalse(review_gate(risk_message()["data"],Scenario("S037",80,10,10,snapshot_what_if=True),"2027-01-01"))

    def test_explicit_override_preserves_low(self):
        r=risk_message()["data"]
        self.assertTrue(review_gate(r,Scenario("S037",80,10,10,snapshot_what_if=True,analyze_low_risk_reason="Academic manual review"),"2027-01-01"))
        self.assertEqual(r["risk_level"],"LOW")

    def test_high_risk_gate(self):
        r=risk_message()["data"];r["risk_level"]="HIGH";r["disruption_probability"]=.2
        self.assertTrue(review_gate(r,Scenario("S037",80,10,10,snapshot_what_if=True),"2027-01-01"))

    def test_dependency_order(self):
        state=CaseState("test",Scenario("S037",80,10,10))
        with self.assertRaises(ValueError): state.add("impact",{})

    def test_duplicate_stage(self):
        state=CaseState("test",Scenario("S037",80,10,10));state.add("risk",risk_message())
        with self.assertRaises(ValueError): state.add("risk",risk_message())

    def test_stable_wire_hash(self):
        from decimal import Decimal
        self.assertEqual(safe(Decimal("1.20")),"1.20")
        self.assertEqual(digest({"a":1,"b":2}),digest({"b":2,"a":1}))

    def test_missing_input_rejected(self):
        m=risk_message();del m["data"]["date"]
        with self.assertRaises(Exception): validate_message("risk",m,"test","S037")

    def test_failure_state_persisted(self):
        class BrokenTools:
            def __init__(self, root):
                self.project=root;self.data=root/"data";self.extensions=root/"ext";self.risk=root/"risk";self.v2=root/"v2"
                self.snapshot="2027-01-01";self.before={}
            def risk_prediction(self,supplier): raise RuntimeError("Model unavailable")
            def assert_unchanged(self): pass
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);out=root/"cases"/"one"
            with self.assertRaises(RuntimeError): Orchestrator(BrokenTools(root)).run(Scenario("S037",80,10,10),out)
            saved=json.loads((out/"case_state.json").read_text())
            self.assertEqual(saved["status"],"FAILED")
            self.assertFalse(saved["actions_executed"])

    def test_recorded_real_outputs_validate(self):
        from decimal import Decimal
        root=Path(__file__).resolve().parents[1]/"results/s037_demo"
        state=json.loads((root/"case_state.json").read_text())
        for role, message in state["messages"].items():
            validate_message(role,message,state["case_id"],state["scenario"]["supplier_id"])
        result=state["messages"]["optimization"]["data"]
        self.assertEqual(result["audit"]["orders_protected"],36)
        self.assertEqual(len(result["audit"]["unresolved_order_ids"]),80)
        self.assertEqual(Decimal(result["objective_value"]),Decimal("12627.78"))
        self.assertEqual(result["audit"]["status"],"PASSED")

    def test_in_memory_mutation_guard(self):
        import pandas as pd
        import networkx as nx
        from adapters import Tools
        t=Tools.__new__(Tools)
        t.tables={"sample":pd.DataFrame({"quantity":[1,2]})}
        t.ext={"sample":pd.DataFrame({"capacity":[10]})}
        t.graph=nx.MultiDiGraph();t.graph.add_edge("S037","C037",quantity=3)
        first=t.memory_hashes()
        # Queries are harmless; values and topology are not.
        list(t.graph.out_edges("S037"));t.tables["sample"].set_index("quantity")
        self.assertEqual(first,t.memory_hashes())
        t.tables["sample"].loc[0,"quantity"]=9
        self.assertNotEqual(first["tables"],t.memory_hashes()["tables"])
        t.graph["S037"]["C037"][0]["quantity"]=99
        self.assertNotEqual(first["graph"],t.memory_hashes()["graph"])

    def test_reported_objective_tampering_rejected(self):
        path=Path(__file__).resolve().parents[1]/"results/s037_demo/optimization.json"
        m=json.loads(path.read_text());m["data"]["objective_value"]="0"
        with self.assertRaises(ValueError): validate_message("optimization",m,m["case_id"],"S037")

    def test_candidate_duplicate_rejected(self):
        path=Path(__file__).resolve().parents[1]/"results/s037_demo/mitigation.json"
        m=json.loads(path.read_text());m["data"]["candidates"].append(copy.deepcopy(m["data"]["candidates"][0]))
        with self.assertRaises(ValueError): validate_message("mitigation",m,m["case_id"],"S037")

    def test_trace_stage_completeness(self):
        path=Path(__file__).resolve().parents[1]/"results/s037_demo/decision_trace.jsonl"
        events=[json.loads(line) for line in path.read_text().splitlines()]
        self.assertEqual([v["sequence"] for v in events],list(range(1,len(events)+1)))
        complete={v["agent"] for v in events if v["event"]=="SUCCEEDED"}
        self.assertEqual(complete,{"risk","impact","financial","mitigation","optimization"})
        self.assertTrue(any(v["event"]=="SOURCE_IMMUTABILITY_PASSED" for v in events))


if __name__ == "__main__": unittest.main()
