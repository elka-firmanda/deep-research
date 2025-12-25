import httpx
from bs4 import BeautifulSoup
from typing import Optional
from .base import BaseTool, ToolResult
import re


class WebScraperTool(BaseTool):
    """Web scraper tool to fetch and extract content from URLs."""

    name = "web_scraper"
    description = "Fetch and extract the main content from a webpage URL. Use this to read the full content of a page when you need more details than the search snippet provides."

    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }

    async def execute(
        self,
        url: str,
        max_length: int = 8000,
    ) -> ToolResult:
        """
        Fetch and extract content from a URL.

        Args:
            url: The URL to scrape
            max_length: Maximum content length to return (default 8000 chars)
        """
        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
                response = await client.get(url, headers=self.headers)

                if response.status_code != 200:
                    return ToolResult(
                        success=False,
                        data=None,
                        error=f"HTTP {response.status_code}: Failed to fetch URL",
                    )

                content_type = response.headers.get("content-type", "")
                if (
                    "text/html" not in content_type
                    and "application/xhtml" not in content_type
                ):
                    return ToolResult(
                        success=False,
                        data=None,
                        error=f"Unsupported content type: {content_type}",
                    )

                # Parse HTML
                soup = BeautifulSoup(response.text, "html.parser")

                # Remove unwanted elements
                for element in soup(
                    [
                        "script",
                        "style",
                        "nav",
                        "header",
                        "footer",
                        "aside",
                        "form",
                        "button",
                        "iframe",
                        "noscript",
                        "svg",
                        "img",
                        "video",
                        "audio",
                    ]
                ):
                    element.decompose()

                # Try to find main content
                main_content = None

                # Look for common main content containers
                for selector in [
                    "main",
                    "article",
                    "[role='main']",
                    ".main-content",
                    "#main-content",
                    ".post-content",
                    ".article-content",
                    ".entry-content",
                    ".content",
                    "#content",
                ]:
                    main_content = soup.select_one(selector)
                    if main_content:
                        break

                if not main_content:
                    main_content = soup.body if soup.body else soup

                # Extract text
                text = main_content.get_text(separator="\n", strip=True)

                # Clean up whitespace
                text = re.sub(r"\n\s*\n", "\n\n", text)
                text = re.sub(r" +", " ", text)

                # Get title
                title = ""
                if soup.title:
                    title = soup.title.get_text(strip=True)

                # Get meta description
                meta_desc = ""
                meta_tag = soup.find("meta", {"name": "description"})
                if meta_tag and meta_tag.get("content"):
                    meta_desc = meta_tag["content"]

                # Truncate if needed
                if len(text) > max_length:
                    text = text[:max_length] + "...[truncated]"

                return ToolResult(
                    success=True,
                    data={
                        "url": str(response.url),
                        "title": title,
                        "description": meta_desc,
                        "content": text,
                        "content_length": len(text),
                    },
                )

        except httpx.TimeoutException:
            return ToolResult(success=False, data=None, error="Request timed out")
        except Exception as e:
            return ToolResult(success=False, data=None, error=str(e))

    def get_schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The URL of the webpage to scrape",
                    },
                    "max_length": {
                        "type": "integer",
                        "description": "Maximum content length to return",
                        "default": 8000,
                    },
                },
                "required": ["url"],
            },
        }
