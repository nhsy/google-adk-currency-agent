from currency_agent.agent import root_agent


def test_agent_initialization():
    assert root_agent.name == "currency_agent"
    assert "specialized Currency Conversion Assistant" in root_agent.instruction
    assert len(root_agent.tools) == 1
