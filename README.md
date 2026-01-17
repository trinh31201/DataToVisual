# DataToVisual

A data-to-visualization system where users ask business questions in plain English and instantly see the answer as a chart.

## Architecture

```
┌──────────┐     ┌─────────┐     ┌────────────┐     ┌──────────┐
│ Frontend │────▶│ Backend │────▶│ MCP Server │────▶│ Database │
│ Chart.js │     │ FastAPI │ SSE │  (Tools)   │     │ SQL      │
└──────────┘     └─────────┘     └────────────┘     └──────────┘
                      │
                      ▼
                ┌───────────┐
                │ Gemini AI │
                └───────────┘
```

### Why MCP (Model Context Protocol)?

**Decision:** Use MCP instead of direct LLM API calls.

**Reasoning:**
- **Standardized interface** - MCP provides a standard way for AI to interact with tools, resources, and prompts
- **Separation of concerns** - AI logic (tool selection) is separate from execution (database queries)
- **Extensibility** - Easy to add new tools without changing AI integration code
- **Interoperability** - MCP server can be used by other AI clients (Claude Desktop, Cursor, etc.)

### Why HTTP/SSE Transport (not Stdio)?

**Decision:** Use HTTP/SSE transport instead of stdio.

**Reasoning:**
- **Docker-friendly** - Each service runs in its own container
- **Scalability** - MCP server can be scaled independently
- **Debugging** - Easier to inspect HTTP traffic than stdio pipes
- **Production-ready** - HTTP is standard for microservices

## Tech Stack

| Component | Technology | Why |
|-----------|------------|-----|
| Backend | FastAPI | Async, fast, auto-docs |
| MCP Server | Starlette + SSE | Lightweight, async |
| Database | SQLAlchemy | Multi-DB support |
| AI | Gemini API | Free tier, function calling |
| Frontend | Chart.js | Simple, no build step |
| Container | Docker Compose | Easy deployment |

## Design Decisions

### 1. Hybrid Query Tools (simple_query + advanced_query)

**Problem:** AI-generated raw SQL can have syntax errors or security issues.

**Solution:** Two-tool approach:

| Tool | Use Case | Safety |
|------|----------|--------|
| `simple_query` | Single-table aggregations | SQL built from validated structure |
| `advanced_query` | JOINs, complex queries | Raw SQL with sanitization |

**Why hybrid?**
- `simple_query` handles 80% of cases safely (no SQL injection possible)
- `advanced_query` provides flexibility for complex queries
- AI chooses the appropriate tool based on query complexity

### 2. Multi-Database Support via SQLAlchemy

**Problem:** Locked to PostgreSQL initially.

**Solution:** Use SQLAlchemy's `text()` for raw queries instead of database-specific drivers.

```python
# Works with any database
result = await conn.execute(text(sql))
```

**Trade-off:** Slight overhead, but gains database portability.

### 3. SQL Safety Layers

| Layer | Protection |
|-------|------------|
| Keyword blocking | DROP, DELETE, UPDATE, INSERT, ALTER, TRUNCATE |
| Pattern blocking | `;` (multi-statement), `--` (comments), `UNION` |
| Row limit | Auto-adds `LIMIT 1000` |
| Timeout | 30-second query timeout |
| Table whitelist | Only allowed tables in `simple_query` |

**Why not just trust the AI?**
- AI can be manipulated via prompt injection
- Defense in depth is essential for database access

### 4. Schema Discovery via MCP Resource

**Decision:** Fetch schema dynamically, not hardcoded.

```python
@server.read_resource()
async def read_resource(uri):
    if uri == "schema://database":
        # Query information_schema dynamically
```

**Why?**
- Schema changes don't require code updates
- Works with any database structure
- AI always has current schema

## Setup

### Prerequisites

- Docker & Docker Compose
- Gemini API key ([Get one free](https://aistudio.google.com/))

### Quick Start

```bash
# Clone
git clone <repo-url>
cd DataToVisual

# Configure
cp .env.example .env
# Add your GEMINI_API_KEY to .env

# Start
docker-compose up -d

# Seed database
docker exec datatovisual_backend python -m app.db.seed

# Open frontend
cd frontend && python -m http.server 5500
```

**URLs:**
- Frontend: http://localhost:5500
- API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- MCP Server: http://localhost:3001

## Example Queries

| Question | Tool Used | Chart |
|----------|-----------|-------|
| "Sales by category" | advanced_query (JOIN) | Bar |
| "Top 5 products by quantity" | advanced_query (JOIN) | Bar |
| "Monthly sales trend" | advanced_query (EXTRACT) | Line |
| "Count products per category" | simple_query | Pie |

## API

### POST /api/v1/query

```json
// Request
{ "question": "Show total sales by category" }

// Response
{
  "question": "Show total sales by category",
  "chart_type": "bar",
  "rows": [
    { "label": "Electronics", "value": 17059236.4 },
    { "label": "Home", "value": 3001309.34 }
  ]
}
```

## Switching Databases

| Database | DATABASE_TYPE | DATABASE_URL | Driver |
|----------|---------------|--------------|--------|
| PostgreSQL | `postgresql` | `postgresql://user:pass@host/db` | `asyncpg` |
| MySQL | `mysql` | `mysql://user:pass@host/db` | `aiomysql` |
| SQLite | `sqlite` | `sqlite:///path/to/file.db` | `aiosqlite` |

```bash
# .env
DATABASE_TYPE=mysql
DATABASE_URL=mysql://user:pass@localhost/mydb

# Install driver
pip install aiomysql
```

## Project Structure

```
DataToVisual/
├── docker-compose.yml          # 3 services: postgres, mcp-server, backend
├── backend/
│   ├── app/
│   │   ├── main.py             # FastAPI app
│   │   ├── config.py           # Environment config
│   │   ├── routers/query.py    # POST /api/v1/query
│   │   ├── mcp/
│   │   │   ├── server.py       # MCP Server (tools, resources, prompts)
│   │   │   └── clients/
│   │   │       ├── base.py     # MCP client (SSE transport)
│   │   │       └── gemini.py   # Gemini function calling
│   │   └── db/
│   │       └── database.py     # SQLAlchemy multi-DB
│   └── requirements.txt
└── frontend/
    ├── index.html
    ├── style.css
    └── app.js
```

## MCP Tools Reference

### simple_query

Structured query builder for single-table operations.

```json
{
  "table": "sales",
  "label_column": "product_id",
  "value_column": "total_amount",
  "aggregation": "SUM",
  "filters": [{"column": "sale_date", "operator": ">=", "value": "2024-01-01"}],
  "order_by": "value_desc",
  "limit": 10,
  "chart_type": "bar"
}
```

### advanced_query

Raw SQL for complex queries (JOINs, subqueries).

```json
{
  "sql": "SELECT p.category AS label, SUM(s.total_amount) AS value FROM sales s JOIN products p ON s.product_id = p.id GROUP BY p.category",
  "chart_type": "bar"
}
```

## Database Schema

```
products (id, name, category, price, created_at)
    │
    ├── features (id, product_id, name, description)
    │
    └── sales (id, product_id, quantity, total_amount, sale_date)
```

Sales data: 2022-2026 with realistic trends.

## Future Improvements

- [ ] Add more AI providers (Claude, OpenAI)
- [ ] Frontend in Docker
- [ ] Caching for repeated queries
- [ ] User authentication
- [ ] Query history
