import json
import asyncio
from typing import Optional, AsyncGenerator, Callable
from ..core.llm_providers import get_llm_client, LLMProvider
from ..tools import TavilySearchTool, DeepSearchTool, WebScraperTool, BaseTool


class SearchAgent:
    """
    An AI agent with search capabilities and real-time progress updates.

    This agent can:
    - Use Tavily for web search
    - Perform deep research on complex topics
    - Scrape web pages for detailed content
    - Stream progress updates in real-time
    """

    DEFAULT_SYSTEM_PROMPT = """You are an expert research assistant that produces comprehensive, well-sourced research reports. Your responses should read like Wikipedia articles or academic research summaries.

## Available Tools
1. **tavily_search**: Quick web search for current information, news, and facts.
2. **deep_search**: Comprehensive research that searches multiple queries, reads full page content, and synthesizes information. Use this for complex topics.
3. **web_scraper**: Read the full content of a specific webpage URL.

## Response Guidelines

### Writing Style
- Write in a formal, encyclopedic tone similar to Wikipedia
- Use complete paragraphs with flowing prose, not bullet points
- Provide comprehensive coverage of the topic with depth and nuance
- Include relevant context, background, and implications
- Maintain objectivity and present multiple perspectives when applicable

### Citations (CRITICAL)
- Every factual claim MUST have a citation
- Use superscript numbers for citations: <sup>[[1]](URL)</sup>
- Place citations immediately after the relevant sentence or claim
- Number citations sequentially starting from 1
- At the end, include a "## References" section listing all sources

### Citation Format Example
"Artificial intelligence has seen rapid advancement in recent years, with large language models demonstrating unprecedented capabilities in natural language understanding.<sup>[[1]](https://example.com/article1)</sup> These developments have sparked both excitement and concern among researchers and policymakers.<sup>[[2]](https://example.com/article2)</sup>"

### Structure
- Start with an introductory paragraph summarizing the topic
- Use ## headers to organize major sections
- Provide detailed paragraphs under each section
- End with a "## References" section listing all cited sources

### Important Rules
- ALWAYS search for information before answering - never make up facts
- If search results are insufficient, acknowledge limitations
- Cross-reference multiple sources when possible
- Include dates and specific details when available
- Every paragraph should have at least one citation"""

    def __init__(
        self,
        provider: Optional[LLMProvider] = None,
        model: Optional[str] = None,
        tavily_api_key: Optional[str] = None,
        progress_callback: Optional[Callable[[dict], None]] = None,
        system_prompt: Optional[str] = None,
    ):
        self.provider = provider
        self.model = model
        self.tavily_api_key = tavily_api_key
        self.progress_callback = progress_callback
        self.system_prompt = system_prompt or self.DEFAULT_SYSTEM_PROMPT

        # Initialize tools
        self.tools: dict[str, BaseTool] = {}
        self._init_tools()

        # Conversation history
        self.messages: list[dict] = []

    def _emit_progress(self, event_type: str, data: dict):
        """Emit a progress event."""
        if self.progress_callback:
            self.progress_callback({"type": event_type, **data})

    def _init_tools(self):
        """Initialize available tools."""
        try:
            self.tools["tavily_search"] = TavilySearchTool(api_key=self.tavily_api_key)
            self.tools["deep_search"] = DeepSearchTool(
                tavily_api_key=self.tavily_api_key,
                llm_provider=self.provider,
                llm_model=self.model,
                progress_callback=self.progress_callback,
            )
            self.tools["web_scraper"] = WebScraperTool()
        except ValueError as e:
            # Tools may fail to initialize if API keys are missing
            print(f"Warning: Some tools not initialized: {e}")

    def get_tools_schema(self) -> list[dict]:
        """Get OpenAI-compatible tool schemas."""
        return [tool.to_openai_tool() for tool in self.tools.values()]

    async def _execute_tool(self, tool_name: str, arguments: dict) -> str:
        """Execute a tool and return the result as a string."""
        if tool_name not in self.tools:
            return json.dumps({"error": f"Unknown tool: {tool_name}"})

        self._emit_progress(
            "tool_start",
            {
                "tool": tool_name,
                "arguments": arguments,
            },
        )

        tool = self.tools[tool_name]
        result = await tool.execute(**arguments)

        self._emit_progress(
            "tool_end",
            {
                "tool": tool_name,
                "success": result.success,
            },
        )

        if result.success:
            return json.dumps(result.data, indent=2)
        else:
            return json.dumps({"error": result.error})

    def reset(self):
        """Reset conversation history."""
        self.messages = []

    async def chat_stream(
        self,
        message: str,
    ) -> AsyncGenerator[dict, None]:
        """
        Send a message and stream progress updates and response.

        Yields dicts with:
        - {"type": "progress", "step": "...", "status": "...", "detail": "...", "progress": int}
        - {"type": "tool_start", "tool": "...", "arguments": {...}}
        - {"type": "tool_end", "tool": "...", "success": bool}
        - {"type": "thinking", "content": "..."}
        - {"type": "response", "content": "..."}
        - {"type": "done"}
        """
        events = []

        def capture_event(event: dict):
            events.append(event)

        # Set up progress callback
        old_callback = self.progress_callback
        self.progress_callback = capture_event

        # Update deep_search tool with new callback
        if "deep_search" in self.tools:
            self.tools["deep_search"].progress_callback = capture_event

        try:
            # Add user message to history
            self.messages.append({"role": "user", "content": message})

            # Get LLM client
            llm = get_llm_client(provider=self.provider, model=self.model)

            # Prepare messages with system prompt
            full_messages = [
                {"role": "system", "content": self.system_prompt},
                *self.messages,
            ]

            # Get available tools
            tools = self.get_tools_schema() if self.tools else None

            # Main agent loop
            max_iterations = 10
            iteration = 0

            while iteration < max_iterations:
                iteration += 1

                # Yield any pending events
                while events:
                    yield events.pop(0)

                yield {
                    "type": "thinking",
                    "content": "Analyzing your request..."
                    if iteration == 1
                    else "Processing results...",
                }

                response = await llm.chat(
                    messages=full_messages,
                    tools=tools,
                    stream=False,
                )

                # Check if this is a tool call response
                if isinstance(response, dict) and "tool_calls" in response:
                    tool_calls = response["tool_calls"]
                    assistant_content = response.get("content", "")

                    # Emit tool call info
                    for tc in tool_calls:
                        args = tc["arguments"]
                        if isinstance(args, str):
                            args = json.loads(args)

                        yield {
                            "type": "tool_call",
                            "tool": tc["name"],
                            "arguments": args,
                        }

                    # Add assistant message with tool calls
                    if self.provider == LLMProvider.ANTHROPIC:
                        content_blocks = []
                        if assistant_content:
                            content_blocks.append(
                                {"type": "text", "text": assistant_content}
                            )
                        for tc in tool_calls:
                            content_blocks.append(
                                {
                                    "type": "tool_use",
                                    "id": tc["id"],
                                    "name": tc["name"],
                                    "input": tc["arguments"]
                                    if isinstance(tc["arguments"], dict)
                                    else json.loads(tc["arguments"]),
                                }
                            )
                        full_messages.append(
                            {"role": "assistant", "content": content_blocks}
                        )
                    else:
                        full_messages.append(
                            {
                                "role": "assistant",
                                "content": assistant_content,
                                "tool_calls": [
                                    {
                                        "id": tc["id"],
                                        "type": "function",
                                        "function": {
                                            "name": tc["name"],
                                            "arguments": tc["arguments"]
                                            if isinstance(tc["arguments"], str)
                                            else json.dumps(tc["arguments"]),
                                        },
                                    }
                                    for tc in tool_calls
                                ],
                            }
                        )

                    # Execute tools and add results
                    for tc in tool_calls:
                        args = tc["arguments"]
                        if isinstance(args, str):
                            args = json.loads(args)

                        # Yield progress events during tool execution
                        result = await self._execute_tool(tc["name"], args)

                        # Yield any events that occurred during tool execution
                        while events:
                            yield events.pop(0)

                        if self.provider == LLMProvider.ANTHROPIC:
                            full_messages.append(
                                {
                                    "role": "user",
                                    "content": [
                                        {
                                            "type": "tool_result",
                                            "tool_use_id": tc["id"],
                                            "content": result,
                                        }
                                    ],
                                }
                            )
                        else:
                            full_messages.append(
                                {
                                    "role": "tool",
                                    "tool_call_id": tc["id"],
                                    "content": result,
                                }
                            )
                else:
                    # Final response
                    final_response = (
                        response if isinstance(response, str) else str(response)
                    )
                    self.messages.append(
                        {"role": "assistant", "content": final_response}
                    )

                    yield {"type": "response", "content": final_response}
                    yield {"type": "done"}
                    return

            # Max iterations
            error_msg = "I apologize, but I was unable to complete the request after multiple attempts."
            self.messages.append({"role": "assistant", "content": error_msg})
            yield {"type": "response", "content": error_msg}
            yield {"type": "done"}

        finally:
            # Restore original callback
            self.progress_callback = old_callback
            if "deep_search" in self.tools:
                self.tools["deep_search"].progress_callback = old_callback

    async def chat(
        self,
        message: str,
        stream: bool = False,
    ) -> AsyncGenerator[str, None] | str:
        """
        Send a message to the agent and get a response.
        For streaming with progress, use chat_stream() instead.
        """
        # For non-streaming, collect the final response
        final_content = ""
        async for event in self.chat_stream(message):
            if event["type"] == "response":
                final_content = event["content"]

        if stream:

            async def gen():
                yield final_content

            return gen()

        return final_content
