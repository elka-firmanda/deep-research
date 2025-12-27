from typing import Optional
import httpx
from .base import BaseTool, ToolResult


class ApifyScraperTool(BaseTool):
    """Apify web scraper tool for advanced web scraping using Apify platform."""

    name = "apify_scraper"
    description = "Advanced web scraping using Apify platform. Handles JavaScript-rendered content, anti-bot protections, and complex page interactions. Use this for sites that don't work with basic scraping."

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Apify scraper tool.

        Args:
            api_key: Apify API key (required)
        """
        self.api_key = api_key
        if not self.api_key:
            raise ValueError("Apify API key not configured")
        self.base_url = "https://api.apify.com/v2"

    async def execute(
        self,
        url: str,
        max_length: int = 8000,
        wait_for: Optional[str] = None,
        screenshot: bool = False,
    ) -> ToolResult:
        """
        Scrape a webpage using Apify's Web Scraper actor.

        Args:
            url: The URL to scrape
            max_length: Maximum content length to return (default 8000 chars)
            wait_for: CSS selector to wait for before scraping (optional)
            screenshot: Whether to take a screenshot (default False)
        """
        try:
            # Use Apify's Website Content Crawler actor
            # This is a general-purpose web scraper
            actor_id = "apify/website-content-crawler"

            # Prepare the input for the actor
            run_input = {
                "startUrls": [{"url": url}],
                "maxCrawlPages": 1,
                "crawlerType": "playwright:firefox",  # Use browser for JavaScript rendering
                "includeUrlGlobs": [],
                "excludeUrlGlobs": [],
                "maxCrawlDepth": 0,
                "maxSessionRotations": 3,
                "maxRequestRetries": 3,
            }

            if wait_for:
                run_input["waitForSelector"] = wait_for

            if screenshot:
                run_input["saveScreenshots"] = True

            # Start the actor run
            async with httpx.AsyncClient(timeout=120.0) as client:
                # Run the actor
                run_response = await client.post(
                    f"{self.base_url}/acts/{actor_id}/runs",
                    params={"token": self.api_key},
                    json=run_input,
                )
                run_response.raise_for_status()
                run_data = run_response.json()
                run_id = run_data["data"]["id"]

                # Wait for the run to complete (with timeout)
                max_wait_time = 60  # seconds
                check_interval = 2  # seconds
                elapsed_time = 0

                while elapsed_time < max_wait_time:
                    # Check run status
                    status_response = await client.get(
                        f"{self.base_url}/actor-runs/{run_id}",
                        params={"token": self.api_key},
                    )
                    status_response.raise_for_status()
                    status_data = status_response.json()

                    status = status_data["data"]["status"]

                    if status == "SUCCEEDED":
                        break
                    elif status in ["FAILED", "ABORTED", "TIMED-OUT"]:
                        return ToolResult(
                            success=False,
                            data=None,
                            error=f"Apify run {status.lower()}: {status_data['data'].get('statusMessage', 'Unknown error')}",
                        )

                    # Wait before checking again
                    import asyncio
                    await asyncio.sleep(check_interval)
                    elapsed_time += check_interval

                if elapsed_time >= max_wait_time:
                    return ToolResult(
                        success=False,
                        data=None,
                        error="Apify scraping timed out after 60 seconds",
                    )

                # Get the dataset items (results)
                default_dataset_id = status_data["data"]["defaultDatasetId"]
                dataset_response = await client.get(
                    f"{self.base_url}/datasets/{default_dataset_id}/items",
                    params={"token": self.api_key, "format": "json"},
                )
                dataset_response.raise_for_status()
                items = dataset_response.json()

                if not items:
                    return ToolResult(
                        success=False,
                        data=None,
                        error="No content extracted from the page",
                    )

                # Extract the first item (since we only scraped one page)
                item = items[0]

                # Get the text content
                text = item.get("text", "")
                title = item.get("metadata", {}).get("title", "")
                description = item.get("metadata", {}).get("description", "")

                # Truncate if needed
                if len(text) > max_length:
                    text = text[:max_length] + "...[truncated]"

                result_data = {
                    "url": item.get("url", url),
                    "title": title,
                    "description": description,
                    "content": text,
                    "content_length": len(text),
                }

                # Add screenshot URL if available
                if screenshot and "screenshotUrl" in item:
                    result_data["screenshot_url"] = item["screenshotUrl"]

                return ToolResult(success=True, data=result_data)

        except httpx.HTTPStatusError as e:
            error_msg = f"Apify HTTP error: {e.response.status_code}"
            if e.response.status_code == 401:
                error_msg = "Invalid Apify API key"
            elif e.response.status_code == 429:
                error_msg = "Apify rate limit exceeded"
            return ToolResult(success=False, data=None, error=error_msg)
        except Exception as e:
            return ToolResult(success=False, data=None, error=f"Apify scraping error: {str(e)}")

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
                    "wait_for": {
                        "type": "string",
                        "description": "CSS selector to wait for before scraping (optional, for dynamic content)",
                    },
                    "screenshot": {
                        "type": "boolean",
                        "description": "Whether to take a screenshot of the page",
                        "default": False,
                    },
                },
                "required": ["url"],
            },
        }
