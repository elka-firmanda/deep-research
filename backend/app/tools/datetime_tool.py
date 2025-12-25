from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo
from .base import BaseTool, ToolResult


class DateTimeTool(BaseTool):
    """Tool to get current date/time information for temporal awareness."""

    name = "get_current_datetime"
    description = """Get the current date and time information. Use this tool when you need to:
- Know today's date for time-sensitive queries
- Calculate relative dates like "yesterday", "last week", "3 days ago"
- Understand the temporal context of user queries
- Format dates for search queries"""

    async def execute(self, **kwargs) -> ToolResult:
        """
        Get current date/time or calculate relative dates.

        Args:
            timezone: Timezone name (e.g., "UTC", "America/New_York", "Asia/Tokyo")
            format: Output format - "full", "date_only", "iso", "search_friendly"
            relative_days: If provided, calculate date N days from today (negative for past)
        """
        timezone = kwargs.get("timezone", "UTC")
        format_type = kwargs.get("format", "full")
        relative_days = kwargs.get("relative_days")

        try:
            # Get timezone
            try:
                tz = ZoneInfo(timezone)
            except Exception:
                tz = ZoneInfo("UTC")
                timezone = "UTC"

            # Get current time in timezone
            now = datetime.now(tz)

            # Apply relative days if provided
            target_date = now
            if relative_days is not None:
                target_date = now + timedelta(days=relative_days)

            # Format output based on requested format
            if format_type == "date_only":
                formatted = target_date.strftime("%Y-%m-%d")
            elif format_type == "iso":
                formatted = target_date.isoformat()
            elif format_type == "search_friendly":
                # Format optimized for search queries
                formatted = target_date.strftime("%B %d, %Y")
            else:  # full
                formatted = target_date.strftime("%A, %B %d, %Y at %I:%M %p %Z")

            # Calculate useful relative dates
            result = {
                "current_datetime": now.isoformat(),
                "formatted": formatted,
                "timezone": timezone,
                "date_components": {
                    "year": target_date.year,
                    "month": target_date.month,
                    "month_name": target_date.strftime("%B"),
                    "day": target_date.day,
                    "weekday": target_date.strftime("%A"),
                    "hour": target_date.hour,
                    "minute": target_date.minute,
                },
                "relative_dates": {
                    "yesterday": (now - timedelta(days=1)).strftime("%Y-%m-%d"),
                    "last_week": (now - timedelta(days=7)).strftime("%Y-%m-%d"),
                    "last_month": (now - timedelta(days=30)).strftime("%Y-%m-%d"),
                    "tomorrow": (now + timedelta(days=1)).strftime("%Y-%m-%d"),
                },
            }

            if relative_days is not None:
                result["calculated_date"] = target_date.strftime("%Y-%m-%d")
                result["days_offset"] = relative_days

            return ToolResult(success=True, data=result)

        except Exception as e:
            return ToolResult(
                success=False, data=None, error=f"Failed to get datetime: {str(e)}"
            )

    def get_schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "timezone": {
                        "type": "string",
                        "description": "Timezone name (e.g., 'UTC', 'America/New_York', 'Europe/London', 'Asia/Tokyo'). Defaults to UTC.",
                        "default": "UTC",
                    },
                    "format": {
                        "type": "string",
                        "enum": ["full", "date_only", "iso", "search_friendly"],
                        "description": "Output format. 'full' for complete datetime, 'date_only' for YYYY-MM-DD, 'iso' for ISO format, 'search_friendly' for natural date format.",
                        "default": "full",
                    },
                    "relative_days": {
                        "type": "integer",
                        "description": "Calculate a date relative to today. Use negative numbers for past dates (e.g., -1 for yesterday, -7 for last week).",
                    },
                },
                "required": [],
            },
        }
