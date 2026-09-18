from agents.base import Agent

class FinancialAgent(Agent):
    role, module = "financial", "financial_blast_radius"
    def process(self, state):
        return self.tools.financial(state.messages["impact"]["data"], state.scenario)
