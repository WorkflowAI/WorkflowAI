# A script that simulates a conversation with a model using OpenAI streaming and Rich UI

import json
import os
from typing import Any, Dict

import typer
from dotenv import load_dotenv
from openai import OpenAI
from openai.types.chat import ChatCompletionAssistantMessageParam, ChatCompletionMessageParam
from openai.types.chat.chat_completion_chunk import ChoiceDelta
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from rich.spinner import Spinner


def _get_weather(location: str) -> str:
    """Get weather information for a given location."""
    weather_data = {
        "London": "It is currently sunny in London.",
        "Paris": "It is currently raining in Paris.",
        "New York": "It is currently cloudy in New York.",
        "Tokyo": "It is currently sunny in Tokyo.",
        "Sydney": "It is currently sunny in Sydney.",
    }
    return weather_data.get(location, f"I don't know the weather for {location}.")


def _execute_tool_call(tool_call: Dict[str, Any]) -> str:
    """Execute a tool call and return the result."""
    if tool_call["function"]["name"] == "get_weather":
        try:
            args = json.loads(tool_call["function"]["arguments"])
            return _get_weather(args.get("location", ""))
        except json.JSONDecodeError:
            return "Error: Invalid arguments for weather function"
    return f"Unknown function: {tool_call['function']['name']}"


class Aggregator:
    def __init__(self):
        self.content = ""
        self.tool_calls: dict[str, dict[str, Any]] = {}

    def add(self, choice_delta: ChoiceDelta):
        # print(choice_delta)
        if choice_delta.content:
            self.content += choice_delta.content
        # Handle tool call streaming - aggregate by tool call ID

        if choice_delta.tool_calls:
            for tool_call_chunk in choice_delta.tool_calls:
                tool_call_id = tool_call_chunk.id or "unique"

                if tool_call_id not in self.tool_calls:
                    # Initialize new tool call
                    self.tool_calls[tool_call_id] = {
                        "id": tool_call_id,
                        "type": "function",
                        "function": {
                            "name": tool_call_chunk.function.name
                            if tool_call_chunk.function and tool_call_chunk.function.name
                            else "",
                            "arguments": tool_call_chunk.function.arguments
                            if tool_call_chunk.function and tool_call_chunk.function.arguments
                            else "",
                        },
                    }
                else:
                    # Aggregate function name and arguments
                    if tool_call_chunk.function and tool_call_chunk.function.name:
                        self.tool_calls[tool_call_id]["function"]["name"] += tool_call_chunk.function.name
                    if tool_call_chunk.function and tool_call_chunk.function.arguments:
                        self.tool_calls[tool_call_id]["function"]["arguments"] += tool_call_chunk.function.arguments

    def message(self) -> ChatCompletionAssistantMessageParam:
        return {
            "role": "assistant",
            "content": self.content,
            "tool_calls": list(self.tool_calls.values()),  # type: ignore
        }


def _chat(model: str = "gpt-4o"):  # noqa: C901
    console = Console()
    client = OpenAI(api_key=os.getenv("WORKFLOWAI_API_KEY"), base_url=f"{os.getenv('WORKFLOWAI_API_URL')}/v1")

    messages: list[ChatCompletionMessageParam] = [
        {"role": "system", "content": "You are a helpful assistant with access to weather information."},
    ]

    console.print(
        Panel.fit(
            "[bold blue]Welcome to the AI Chatbot with Tool Support![/bold blue]\n"
            "Ask me about the weather in London, Paris, New York, Tokyo, or Sydney!\n"
            "Type your message and press Enter. Type 'exit' to quit.",
            title="🤖 AI Assistant",
            border_style="blue",
        ),
    )

    while True:
        # Get user input
        try:
            user_input = Prompt.ask("\n[bold green]You[/bold green]")
        except KeyboardInterrupt:
            console.print("\n[yellow]Goodbye![/yellow]")
            break

        if user_input.lower() in ["exit", "quit", "bye"]:
            console.print("[yellow]Goodbye![/yellow]")
            break

        # Add user message to conversation
        messages.append({"role": "user", "content": user_input})

        # Display AI response with streaming
        console.print("\n[bold blue]Assistant[/bold blue]:")

        agg = Aggregator()
        # Use Live to update the display in real-time
        with Live(console=console, refresh_per_second=10) as live:
            # Show thinking spinner initially
            live.update(Spinner("dots", text="Thinking..."))

            stream = client.chat.completions.create(
                model=f"conversation-test/{model}",
                messages=messages,
                stream=True,
                tools=[
                    {
                        "type": "function",
                        "function": {
                            "name": "get_weather",
                            "description": "Get the weather for a given location",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "location": {
                                        "type": "string",
                                        "description": "The location to get the weather for",
                                    },
                                },
                                "required": ["location"],
                            },
                        },
                    },
                ],
            )

            # Stream the response and collect chunks
            for chunk in stream:
                agg.add(chunk.choices[0].delta)
                live.update(Markdown(agg.content))

        # Add assistant message with tool calls to conversation
        messages.append(agg.message())

        # Execute tool calls if any
        if agg.tool_calls:
            console.print("\n[dim]Executing tool calls...[/dim]")

            for tool_call in agg.tool_calls.values():  # type: ignore
                # Execute the tool call
                result = _execute_tool_call(tool_call)  # type: ignore

                # Add tool result to conversation
                tool_message: Dict[str, Any] = {
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "content": result,
                }
                messages.append(tool_message)  # type: ignore

            # Get final response after tool execution
            console.print("\n[bold blue]Assistant[/bold blue] (after tool execution):")

            final_response = ""
            with Live(console=console, refresh_per_second=10) as live:
                live.update(Spinner("dots", text="Processing results..."))

                final_stream = client.chat.completions.create(
                    model=f"conversation-test/{model}",
                    messages=messages,
                    stream=True,
                )

                for chunk in final_stream:
                    if chunk.choices[0].delta.content:
                        final_response += chunk.choices[0].delta.content
                        live.update(Markdown(final_response))

            # Add final assistant response
            messages.append({"role": "assistant", "content": final_response})

        console.print()  # Add some spacing


if __name__ == "__main__":
    load_dotenv(override=True)
    typer.run(_chat)
