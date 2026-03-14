import asyncio
import os
import time
import structlog
import logging

import httpx
from fastmcp import FastMCP

...
# Configure structlog
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer()
        if not os.getenv("LOG_JSON")
        else structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)


logger = structlog.get_logger(__name__)

mcp = FastMCP("Currency MCP Server 💵")

# Rate limiting state
rate_limit_lock = asyncio.Lock()
last_request_time = 0.0
RATE_LIMIT_INTERVAL = 3.0  # 3 seconds per request


async def _rate_limited_request(url: str, params: dict | None = None) -> httpx.Response:
    """Helper to perform a rate-limited HTTP GET request."""
    global last_request_time

    async with rate_limit_lock:
        now = time.time()
        elapsed = now - last_request_time
        if elapsed < RATE_LIMIT_INTERVAL:
            wait_time = RATE_LIMIT_INTERVAL - elapsed
            logger.info("rate_limiting", wait_time=f"{wait_time:.2f}s")
            await asyncio.sleep(wait_time)

        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)
            last_request_time = time.time()
            return response


@mcp.tool()
async def get_exchange_rate(
    currency_from: str = "USD",
    currency_to: str | None = None,
    currency_date: str = "latest",
):
    """Use this to get the exchange rate for a specific date or the latest one.

    Args:
        currency_from: The currency to convert from (e.g., "USD").
        currency_to: The currency to convert to (e.g., "EUR"). Can be a single code or a comma-separated list. Defaults to None (returns all available rates).
        currency_date: The date for the exchange rate in YYYY-MM-DD format or "latest". Defaults to "latest".

    Returns:
        A dictionary containing the exchange rate data, or an error message if the request fails.
    """
    logger.info(
        "tool_call",
        tool="get_exchange_rate",
        currency_from=currency_from,
        currency_to=currency_to,
        currency_date=currency_date,
    )
    try:
        url = f"https://api.frankfurter.app/{currency_date}"
        params = {"from": currency_from}
        if currency_to:
            params["to"] = currency_to

        response = await _rate_limited_request(url, params=params)
        response.raise_for_status()

        data = response.json()
        if "rates" not in data:
            logger.error("invalid_api_response", data=data)
            return {"error": "Invalid API response format."}
        logger.info("api_response", data=data)
        return data
    except httpx.HTTPError as e:
        logger.error("api_request_failed", error=str(e))
        return {"error": f"API request failed: {e}"}
    except ValueError:
        logger.error("invalid_json_response")
        return {"error": "Invalid JSON response from API."}


@mcp.tool()
async def convert_currency(
    amount: float,
    currency_from: str = "USD",
    currency_to: str = "EUR",
    currency_date: str = "latest",
):
    """Directly converts a specific amount from one currency to another.

    Args:
        amount: The amount of currency to convert.
        currency_from: The base currency code (e.g., "USD").
        currency_to: The target currency code (e.g., "EUR").
        currency_date: The date for the exchange rate in YYYY-MM-DD format or "latest". Defaults to "latest".
    """
    logger.info(
        "tool_call",
        tool="convert_currency",
        amount=amount,
        currency_from=currency_from,
        currency_to=currency_to,
        currency_date=currency_date,
    )
    try:
        url = f"https://api.frankfurter.app/{currency_date}"
        params = {"amount": amount, "from": currency_from, "to": currency_to}
        response = await _rate_limited_request(url, params=params)
        response.raise_for_status()
        data = response.json()
        logger.info("api_response", data=data)
        return data
    except httpx.HTTPError as e:
        logger.error("api_request_failed", error=str(e))
        return {"error": f"API request failed: {e}"}


@mcp.tool()
async def get_time_series(
    currency_from: str = "USD",
    currency_to: str = "EUR",
    start_date: str = "2024-01-01",
    end_date: str = "latest",
):
    """Fetches exchange rates over a period of time.

    Args:
        currency_from: The base currency code.
        currency_to: The target currency code (or comma-separated list).
        start_date: Start date in YYYY-MM-DD format.
        end_date: End date in YYYY-MM-DD format (or 'latest').
    """
    if end_date == "latest":
        from datetime import datetime

        end_date = datetime.now().strftime("%Y-%m-%d")

    logger.info(
        "tool_call",
        tool="get_time_series",
        currency_from=currency_from,
        currency_to=currency_to,
        start_date=start_date,
        end_date=end_date,
    )
    try:
        url = f"https://api.frankfurter.app/{start_date}..{end_date}"
        params = {"from": currency_from, "to": currency_to}
        response = await _rate_limited_request(url, params=params)
        response.raise_for_status()
        data = response.json()
        logger.info("api_response", data_summary=str(data)[:200] + "...")
        return data
    except httpx.HTTPError as e:
        logger.error("api_request_failed", error=str(e))
        return {"error": f"API request failed: {e}"}


@mcp.tool()
async def get_rate_trend(
    currency_from: str = "USD",
    currency_to: str = "EUR",
    base_date: str = "2023-01-01",
    comparison_date: str = "latest",
):
    """Calculates the percentage change in exchange rate between two dates.

    Args:
        currency_from: The base currency.
        currency_to: The target currency to check the trend for.
        base_date: The older date for comparison.
        comparison_date: The more recent date for comparison (or 'latest').
    """
    logger.info(
        "tool_call",
        tool="get_rate_trend",
        currency_from=currency_from,
        currency_to=currency_to,
        base_date=base_date,
        comparison_date=comparison_date,
    )
    try:
        # Get rates for both dates
        rate_old = await get_exchange_rate(currency_from, currency_to, base_date)
        rate_new = await get_exchange_rate(currency_from, currency_to, comparison_date)

        if "error" in rate_old or "error" in rate_new:
            logger.error("trend_calculation_failed", reason="could_not_fetch_rates")
            return {"error": "Could not fetch rates for both dates."}

        val_old = rate_old["rates"][currency_to]
        val_new = rate_new["rates"][currency_to]

        change_pct = ((val_new - val_old) / val_old) * 100
        trend = "up" if change_pct > 0 else "down"

        return {
            "currency_pair": f"{currency_from}/{currency_to}",
            "base_date": rate_old["date"],
            "base_rate": val_old,
            "comparison_date": rate_new["date"],
            "comparison_rate": val_new,
            "change_percentage": round(change_pct, 4),
            "trend": trend,
        }
    except Exception as e:
        logger.error("trend_calculation_failed", error=str(e))
        return {"error": f"Failed to calculate trend: {e}"}


@mcp.resource("currencies://list")
async def list_currencies_resource() -> str:
    """Provides a map of all supported currency codes and their full names."""
    logger.info("resource_access", resource="currencies://list")
    data = await list_currencies()
    import json

    return json.dumps(data, indent=2)


@mcp.tool()
async def list_currencies():
    """Use this to list all available currency codes and names.

    Returns:
        A dictionary containing the list of available currencies.
    """
    logger.info("tool_call", tool="list_currencies")
    try:
        url = "https://api.frankfurter.app/currencies"
        response = await _rate_limited_request(url)
        response.raise_for_status()
        data = response.json()
        logger.info("api_response", data=data)
        return data
    except httpx.HTTPError as e:
        logger.error("api_request_failed", error=str(e))
        return {"error": f"API request failed: {e}"}
    except ValueError:
        logger.error("invalid_json_response")
        return {"error": "Invalid JSON response from API."}


@mcp.tool()
def get_current_date():
    """Use this to get the current date.
    Useful for calculating relative dates like 'last year', 'yesterday', etc.

    Returns:
        A dictionary containing the current date in YYYY-MM-DD format.
    """
    from datetime import datetime

    now = datetime.now().strftime("%Y-%m-%d")
    logger.info("tool_call", tool="get_current_date", current_date=now)
    return {"current_date": now}


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    logger.info("server_started", port=port)
    # Could also use 'sse' transport, host="0.0.0.0" required for Cloud Run.
    try:
        asyncio.run(
            mcp.run_async(
                transport="http",
                host="0.0.0.0",
                port=port,
            )
        )
    except KeyboardInterrupt:
        logger.info("server_stopped", reason="user_interrupted")
