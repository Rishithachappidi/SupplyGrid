from agents.base import Agent

class RiskAgent(Agent):
    role, module = "risk", "risk_core"
    def process(self, state):
        return self.tools.risk_prediction(state.scenario.supplier_id)
