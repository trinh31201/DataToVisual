"""MCP Clients - swap AI provider here."""
from app.config import Config
from app.mcp.clients.base import BaseMCPClient

_mcp_client = None


def get_mcp_client() -> BaseMCPClient:
    """Get or create MCP client (lazy initialization)."""
    global _mcp_client
    if _mcp_client is None:
        if Config.AI_PROVIDER == "gemini":
            from app.mcp.clients.gemini import GeminiMCPClient
            _mcp_client = GeminiMCPClient()
        # Add more providers here:
        # elif Config.AI_PROVIDER == "claude":
        #     from app.mcp.clients.claude import ClaudeMCPClient
        #     _mcp_client = ClaudeMCPClient()
        else:
            # Default to Gemini
            from app.mcp.clients.gemini import GeminiMCPClient
            _mcp_client = GeminiMCPClient()
    return _mcp_client


# For backward compatibility - lazy property
class _LazyClient:
    def __getattr__(self, name):
        return getattr(get_mcp_client(), name)


mcp_client = _LazyClient()
