"""
MCP Server runner for stdio transport.
Used when running as subprocess (internal to backend).
"""
import asyncio
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from mcp.server.stdio import stdio_server

# Import the server instance and handlers from main server module
from app.mcp.server import server


async def main():
    """Run MCP server with stdio transport."""
    async with stdio_server() as (read, write):
        await server.run(
            read,
            write,
            server.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
