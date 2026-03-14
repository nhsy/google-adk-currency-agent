import os
import warnings
import structlog
import logging

from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.a2a.utils.agent_to_a2a import to_a2a
from google.adk.tools.mcp_tool import McpToolset, StreamableHTTPConnectionParams

# Suppress warnings about experimental features
warnings.filterwarnings("ignore", message=r".*\[EXPERIMENTAL\].*")

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

load_dotenv()

SYSTEM_INSTRUCTION = (
    "You are a specialized Currency Conversion Assistant. "
    "Your goal is to provide accurate current and historical exchange rates, conversions, and trends using the provided tools.\n\n"
    "TOOLS:\n"
    "1. 'get_exchange_rate': Fetches rates for a specific 'currency_date' (YYYY-MM-DD) or 'latest'. 'currency_to' can be a single code or comma-separated list. If omitted, returns all rates.\n"
    "2. 'convert_currency': Directly converts a specific 'amount' from 'currency_from' to 'currency_to'.\n"
    "3. 'get_time_series': Fetches rates over a period ('start_date' to 'end_date'). Useful for historical tracking.\n"
    "4. 'get_rate_trend': Calculates the percentage change and trend (up/down) between 'base_date' and 'comparison_date'.\n"
    "5. 'list_currencies': Provides a map of all supported currency codes (e.g., GBP, INR).\n"
    "6. 'get_current_date': Returns today's date in YYYY-MM-DD format.\n\n"
    "RESOURCES:\n"
    "- 'currencies://list': A JSON resource containing all supported currency codes and names.\n\n"
    "GUIDELINES:\n"
    "- RELATIVE DATES: If the user uses relative terms like 'last year' or 'yesterday', you MUST:\n"
    "  a) Call 'get_current_date' to get today's date.\n"
    "  b) Calculate the exact target date(s) (YYYY-MM-DD).\n"
    "  c) Use the appropriate tool (e.g., 'get_exchange_rate' or 'get_rate_trend').\n"
    "- TREND ANALYSIS: When asked about how a currency has performed or changed, use 'get_rate_trend'.\n"
    "- CONVERSIONS: Use 'convert_currency' when a specific amount is provided.\n"
    "- AMBIGUOUS CURRENCIES: Map informal terms (e.g., 'bucks') to ISO codes using 'list_currencies' or the 'currencies://list' resource.\n"
    "- SCOPE: Only assist with currency-related queries. Politely decline all other topics."
)

logger.info("--- 🔧 Loading MCP tools from MCP Server... ---")
logger.info("--- 🤖 Creating ADK Currency Agent... ---")

root_agent = LlmAgent(
    model="gemini-2.5-flash",
    name="currency_agent",
    description="An agent that can help with currency conversions",
    instruction=SYSTEM_INSTRUCTION,
    tools=[
        McpToolset(
            connection_params=StreamableHTTPConnectionParams(
                url=os.getenv("MCP_SERVER_URL", "http://localhost:8080/mcp")
            )
        )
    ],
)

# Make the agent A2A-compatible
a2a_app = to_a2a(root_agent, port=10000)
