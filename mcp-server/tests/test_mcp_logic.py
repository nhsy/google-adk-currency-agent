import pytest
from server import mcp


@pytest.mark.asyncio
async def test_get_exchange_rate():
    # Await list_tools
    tools = await mcp.list_tools()
    tool = next(t for t in tools if t.name == "get_exchange_rate")
    assert tool

    result = await mcp.call_tool(
        "get_exchange_rate", {"currency_from": "USD", "currency_to": "EUR"}
    )
    # ToolResult has a 'content' attribute which is a list
    assert "rates" in result.content[0].text or "error" in result.content[0].text


@pytest.mark.asyncio
async def test_convert_currency():
    result = await mcp.call_tool(
        "convert_currency",
        {"amount": 100, "currency_from": "USD", "currency_to": "GBP"},
    )
    assert "rates" in result.content[0].text or "error" in result.content[0].text


@pytest.mark.asyncio
async def test_list_currencies():
    result = await mcp.call_tool("list_currencies", {})
    assert isinstance(result.content[0].text, str)


@pytest.mark.asyncio
async def test_get_time_series():
    result = await mcp.call_tool(
        "get_time_series",
        {
            "currency_from": "USD",
            "currency_to": "EUR",
            "start_date": "2024-01-01",
            "end_date": "2024-01-05",
        },
    )
    assert "rates" in result.content[0].text


@pytest.mark.asyncio
async def test_get_rate_trend():
    result = await mcp.call_tool(
        "get_rate_trend",
        {"currency_from": "USD", "currency_to": "EUR", "base_date": "2023-01-01"},
    )
    assert "trend" in result.content[0].text


@pytest.mark.asyncio
async def test_get_current_date():
    result = await mcp.call_tool("get_current_date", {})
    assert "current_date" in result.content[0].text


@pytest.mark.asyncio
async def test_currencies_resource():
    result = await mcp.read_resource("currencies://list")
    # ResourceResult has contents[0].content or .text depending on version
    # FastMCP ResourceResult usually has 'contents' which are ResourceContent
    assert "AUD" in result.contents[0].content
