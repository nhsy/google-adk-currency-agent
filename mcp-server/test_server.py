import asyncio
import time

from fastmcp import Client


async def test_server():
    # Test the MCP server using streamable-http transport.
    async with Client("http://localhost:8080/mcp") as client:
        # List available tools
        tools = await client.list_tools()
        for tool in tools:
            print(f"--- 🛠️  Tool found: {tool.name} ---")

        # 1. Standard Tool Call
        print("--- 🪛  Calling get_exchange_rate tool for USD to EUR ---")
        result = await client.call_tool(
            "get_exchange_rate", {"currency_from": "USD", "currency_to": "EUR"}
        )
        print(f"--- ✅  Success: {result.content[0].text} ---")

        # 2. Convert Currency
        print("\n--- 🪛  Calling convert_currency: 100 USD to GBP ---")
        result = await client.call_tool(
            "convert_currency",
            {"amount": 100, "currency_from": "USD", "currency_to": "GBP"},
        )
        print(f"--- ✅  Success: {result.content[0].text} ---")

        # 3. Time Series
        print("\n--- 🪛  Calling get_time_series: USD to EUR (Jan 2024) ---")
        result = await client.call_tool(
            "get_time_series",
            {
                "currency_from": "USD",
                "currency_to": "EUR",
                "start_date": "2024-01-01",
                "end_date": "2024-01-10",
            },
        )
        print(f"--- ✅  Success (truncated): {result.content[0].text[:100]}... ---")

        # 4. Rate Trend
        print("\n--- 🪛  Calling get_rate_trend: USD to EUR (2023 vs latest) ---")
        result = await client.call_tool(
            "get_rate_trend",
            {"currency_from": "USD", "currency_to": "EUR", "base_date": "2023-01-01"},
        )
        print(f"--- ✅  Success: {result.content[0].text} ---")

        # 5. Resources
        print("\n--- 📂 Listing Resources ---")
        resources = await client.list_resources()
        for resource in resources:
            print(f"--- 📂 Resource found: {resource.uri} ---")

        print("\n--- 📂 Reading Resource: currencies://list ---")
        resource_content = await client.read_resource("currencies://list")
        print(f"--- ✅  Resource Content (truncated): {resource_content[:100]}... ---")

        # 6. Rate Limiting Test
        print("\n--- ⚖️  Testing Rate Limits (3 sequential calls) ---")
        start_time = time.time()

        for i in range(3):
            turn_start = time.time()
            print(f"   Turn {i + 1} starting...")
            await client.call_tool(
                "get_exchange_rate", {"currency_from": "USD", "currency_to": "CAD"}
            )
            turn_end = time.time()
            print(f"   Turn {i + 1} finished in {turn_end - turn_start:.2f}s")

        total_duration = time.time() - start_time
        print(f"--- 🏁 Rate Limit Test Finished in {total_duration:.2f}s ---")

        if total_duration >= 6.0:
            print("--- ✅ SUCCESS: Rate limiting enforced (took > 6s for 3 calls) ---")
        else:
            print(
                "--- ❌ FAILURE: Rate limiting NOT enforced (took < 6s for 3 calls) ---"
            )


if __name__ == "__main__":
    asyncio.run(test_server())
