import os


class Config:
    # Database
    DATABASE_URL = os.getenv(
        "DATABASE_URL",
        "postgresql://datatovisual:datatovisual123@localhost:5432/datatovisual"
    )
    DATABASE_TYPE = os.getenv("DATABASE_TYPE", "PostgreSQL")

    # Gemini API
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
