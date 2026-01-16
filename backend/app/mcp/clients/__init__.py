"""MCP Clients - swap AI provider here."""
from app.config import Config

_mcp_client = None


def get_mcp_client():
    """Get or create MCP client (lazy initialization)."""
    global _mcp_client
    if _mcp_client is None:
        if Config.AI_PROVIDER == "gemini":
            from app.mcp.clients.gemini import GeminiMCPClient
            _mcp_client = GeminiMCPClient(Config.MCP_SERVER_URL)
        # Add more providers here:
        # elif Config.AI_PROVIDER == "claude":
        #     from app.mcp.clients.claude import ClaudeMCPClient
        #     _mcp_client = ClaudeMCPClient(Config.MCP_SERVER_URL)
        else:
            from app.mcp.clients.gemini import GeminiMCPClient
            _mcp_client = GeminiMCPClient(Config.MCP_SERVER_URL)
    return _mcp_client


# For backward compatibility - lazy property
class _LazyClient:
    def __getattr__(self, name):
        return getattr(get_mcp_client(), name)


mcp_client = _LazyClient()
