import os


class Config:
    # Database
    DATABASE_URL = os.getenv(
        "DATABASE_URL",
        "postgresql://datatovisual:datatovisual123@localhost:5432/datatovisual"
    )
    DATABASE_TYPE = os.getenv("DATABASE_TYPE", "PostgreSQL")

    # AI Provider: "gemini", "claude", or "openai"
    AI_PROVIDER = os.getenv("AI_PROVIDER", "gemini")

    # Gemini
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    # MCP Server URL (HTTP/SSE transport)
    MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:3001")
