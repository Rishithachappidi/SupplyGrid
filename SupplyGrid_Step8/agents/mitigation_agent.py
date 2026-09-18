from agents.base import Agent

class MitigationAgent(Agent):
    role, module = "mitigation", "generate_mitigation_strategies"
    def process(self, state):
        return self.tools.mitigation(state.messages["impact"]["data"], state.scenario)
