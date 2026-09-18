from agents.base import Agent

class OptimizationAgent(Agent):
    role, module = "optimization", "optimize_mitigation_v2"
    def process(self, state):
        return self.tools.optimize(state.messages["impact"]["data"], state.messages["financial"]["data"],
                                   state.messages["mitigation"]["data"], state.scenario)
