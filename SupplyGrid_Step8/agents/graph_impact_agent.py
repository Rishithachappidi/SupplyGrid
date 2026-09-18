from agents.base import Agent

class GraphImpactAgent(Agent):
    role, module = "impact", "propagate_disruption"
    def process(self, state):
        return self.tools.graph_impact(state.scenario)
