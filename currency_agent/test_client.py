from dataclasses import dataclass
import json
import os
import traceback
from typing import Any
from uuid import uuid4

import httpx

from a2a.client import A2ACardResolver, ClientConfig, ClientFactory, Client
from a2a.types import (
    SendMessageResponse,
    SendMessageSuccessResponse,
    Task,
    TaskState,
    TaskQueryParams,
    Message,
    Part,
    TextPart,
    Role,
)

AGENT_URL = os.getenv("AGENT_URL", "http://localhost:10000")


@dataclass
class TokenUsage:
    """Class to track token usage."""

    prompt: int = 0
    candidates: int = 0
    thoughts: int = 0
    total: int = 0

    def add(self, other: "TokenUsage") -> None:
        """Adds another TokenUsage object's counts to this one."""
        self.prompt += other.prompt
        self.candidates += other.candidates
        self.thoughts += other.thoughts
        self.total += other.total

    def __str__(self) -> str:
        return (
            f"Prompt: {self.prompt}, Candidates: {self.candidates}, "
            f"Thoughts: {self.thoughts}, Total: {self.total}"
        )


def get_task_usage(task: Task) -> TokenUsage:
    """Extracts token usage from a Task metadata."""
    usage_data = task.metadata.get("adk_usage_metadata", {})
    return TokenUsage(
        prompt=usage_data.get("promptTokenCount", 0),
        candidates=usage_data.get("candidatesTokenCount", 0),
        thoughts=usage_data.get("thoughtsTokenCount", 0),
        total=usage_data.get("totalTokenCount", 0),
    )


def create_message(
    text: str, task_id: str | None = None, context_id: str | None = None
) -> Message:
    """Helper function to create a message."""
    return Message(
        role=Role.user,
        parts=[Part(root=TextPart(text=text))],
        message_id=uuid4().hex,
        task_id=task_id,
        context_id=context_id,
    )


def print_json_response(response: Any, description: str) -> None:
    """Helper function to print the JSON representation of a response."""
    print(f"--- {description} ---")
    if hasattr(response, "root"):
        # response.root is likely a Pydantic model
        print(f"{response.root.model_dump_json(exclude_none=True, indent=2)}\n")
    else:
        # response is likely a Pydantic model
        data = response.model_dump(mode="json", exclude_none=True)
        print(f"{json.dumps(data, indent=2)}\n")


async def run_single_turn_test(client: Client) -> TokenUsage:
    """Runs a single-turn streaming test."""
    total_usage = TokenUsage()

    message = create_message(text="how much is 100 USD in CAD?")

    print("--- ✉️  Single Turn Request ---")
    # Send Message
    final_task: Task | None = None
    print("--- 📥 Streaming Response ---", flush=True)
    async for item in client.send_message(message):
        if isinstance(item, Message):
            # Non-streaming fallback or specific message event
            print(".", end="", flush=True)
            continue

        task, event = item
        final_task = task
        # Optional: Print event information to see streaming in action
        print(".", end="", flush=True)

    print("\n")

    if not final_task:
        print("--- ❌ Error: No task returned from streaming. ---")
        return total_usage

    # Construct a SendMessageSuccessResponse-like structure for the print function
    success_response = SendMessageResponse(
        root=SendMessageSuccessResponse(
            id=str(uuid4()), jsonrpc="2.0", result=final_task
        )
    )
    print_json_response(success_response, "📥 Single Turn Final Task Response")
    usage = get_task_usage(final_task)
    print(f"--- 📊 Token Usage: {usage} ---\n")
    total_usage.add(usage)

    task_id: str = final_task.id
    print("--- ❔ Query Task ---")
    # query the task
    params = TaskQueryParams(id=task_id)
    get_response: Task = await client.get_task(params)
    print_json_response(get_response, "📥 Query Task Response")
    return total_usage


async def run_multi_turn_test(client: Client, inputs: list[str]) -> TokenUsage:
    """Runs a multi-turn streaming test."""
    print(f"--- 📝 Multi-Turn Request with {len(inputs)} turns ---")
    total_usage = TokenUsage()

    task_id: str | None = None
    context_id: str | None = None

    for i, user_input in enumerate(inputs):
        print(f"--- 📝 Multi-Turn: Turn {i + 1} ('{user_input}') ---")
        message = create_message(
            text=user_input, task_id=task_id, context_id=context_id
        )

        final_task: Task | None = None
        print("--- 📥 Streaming Turn Response ---", flush=True)
        async for item in client.send_message(message):
            if isinstance(item, Message):
                print(".", end="", flush=True)
                continue

            task, event = item
            final_task = task
            print(".", end="", flush=True)

        print("\n")

        if not final_task:
            print(f"--- ❌ Error: No task returned for turn {i + 1}. ---")
            continue

        success_response = SendMessageResponse(
            root=SendMessageSuccessResponse(
                id=str(uuid4()), jsonrpc="2.0", result=final_task
            )
        )
        print_json_response(success_response, f"📥 Multi-Turn: Turn {i + 1} Response")
        usage = get_task_usage(final_task)
        print(f"--- 📊 Token Usage (Turn {i + 1}): {usage} ---\n")
        total_usage.add(usage)

        # Update IDs for next turn
        context_id = final_task.context_id
        if final_task.status.state == TaskState.input_required:
            task_id = final_task.id
        else:
            task_id = None

        if final_task.status.state != TaskState.input_required and i < len(inputs) - 1:
            print(f"--- 🚀 Turn {i + 1} completed, but continuing with next input. ---")
    return total_usage


async def main() -> None:
    """Main function to run the tests."""
    print(f"--- 🔄 Connecting to agent at {AGENT_URL}... ---")
    try:
        async with httpx.AsyncClient(timeout=30.0) as httpx_client:
            # Create a resolver to fetch the agent card
            resolver = A2ACardResolver(
                httpx_client=httpx_client,
                base_url=AGENT_URL,
            )
            agent_card = await resolver.get_agent_card()

            # Create a client to interact with the agent
            config = ClientConfig(httpx_client=httpx_client, streaming=True)
            factory = ClientFactory(config)
            client = factory.create(agent_card)

            print("--- ✅ Connection successful. ---")

            total_usage = TokenUsage()

            usage_single = await run_single_turn_test(client)
            total_usage.add(usage_single)

            usage_multi = await run_multi_turn_test(
                client,
                [
                    "how much is 100 USD?",
                    "in GBP",
                    "how much was 100 USD in EUR on 2020-01-01?",
                    "convert 100 bp to inr 3 months ago from today",
                    "What was the trend for USD to EUR last year?",
                    "Show me the exchange rate of USD to EUR for the first 5 days of 2024",
                ],
            )
            total_usage.add(usage_multi)

            print("\n" + "=" * 40)
            print("         🏁 TEST CLIENT SUMMARY 🏁")
            print("=" * 40)
            print("Total Token Usage across all tests:")
            print(f"  Prompt:     {total_usage.prompt}")
            print(f"  Candidates: {total_usage.candidates}")
            print(f"  Thoughts:   {total_usage.thoughts}")
            print(f"  Total:      {total_usage.total}")
            print("=" * 40 + "\n")

    except Exception as e:
        traceback.print_exc()
        print(f"--- ❌ An error occurred: {e} ---")
        print("Ensure the agent server is running.")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
