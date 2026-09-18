class Agent:
    role = None
    module = None

    def __init__(self, tools):
        self.tools = tools

    def run(self, state):
        return {"case_id": state.case_id, "supplier_id": state.scenario.supplier_id,
                "agent": self.role, "status": "SUCCEEDED", "data": self.process(state),
                "evidence": [self.tools.evidence(self.module)],
                "actions_executed": False}
