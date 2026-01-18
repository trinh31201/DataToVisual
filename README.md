# DataToVisual

A data-to-visualization system where users ask business questions in plain English and instantly see the answer as a chart.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Setup](#setup)
- [Usage](#usage)
- [API Reference](#api-reference)
- [MCP Tools](#mcp-tools)
- [Database](#database)
- [Design Decisions](#design-decisions)
- [AI Reliability](#ai-reliability)
- [Project Structure](#project-structure)
- [Future Improvements](#future-improvements)

---

## Overview

Users ask questions like "Show total sales by category" and get an instant chart visualization. The system uses:

- **MCP (Model Context Protocol)** for AI-tool interaction
- **Gemini AI** for natural language understanding
- **Chart.js** for visualization

---

## Architecture

![Architecture](docs/architecture.png)

### Sequence Diagram

![Sequence Diagram Part 1](docs/sequence-1.png)
![Sequence Diagram Part 2](docs/sequence-2.png)

### Why MCP?

- Standardized AI-tool interface
- Separation of concerns (AI logic vs execution)
- Extensible and interoperable

### Why HTTP/SSE?

- Docker-friendly (each service in own container)
- Scalable and debuggable
- Production-ready

---

## Tech Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| Backend | FastAPI | Async API server |
| MCP Server | Starlette + SSE | Tool execution |
| Database | SQLAlchemy | Multi-DB support |
| AI | Gemini API | Natural language processing |
| Frontend | Chart.js | Chart rendering |
| Container | Docker Compose | Deployment |

---

## Setup

### Prerequisites

- Docker & Docker Compose
- Gemini API key ([Get free](https://aistudio.google.com/))

### Quick Start

```bash
# 1. Clone
git clone <repo-url>
cd DataToVisual

# 2. Configure
cp .env.example .env
# Edit .env and add GEMINI_API_KEY

# 3. Start all services
make up

# 4. Seed database
make seed

# 5. Open frontend
open http://localhost:5500
```

### Run Each Service

#### Database (PostgreSQL)

```bash
# Start database only
docker compose up -d postgres

# Check database is ready
docker compose exec postgres pg_isready

# Connect to database
docker compose exec postgres psql -U postgres -d datatovisual
```

#### Backend (FastAPI)

```bash
# Start backend (requires database)
docker compose up -d postgres backend

# View backend logs
make logs s=backend

# Run tests
make test
```

#### MCP Server

```bash
# Start MCP server (requires database)
docker compose up -d postgres mcp-server

# View MCP server logs
make logs s=mcp-server
```

#### Frontend (Chart.js)

```bash
# Start frontend
docker compose up -d frontend

# Or run locally without Docker
cd frontend && python -m http.server 5500
```

### URLs

| Service | URL |
|---------|-----|
| Frontend | http://localhost:5500 |
| API | http://localhost:8000 |
| API Docs | http://localhost:8000/docs |
| MCP Server | http://localhost:3001 |

### MCP Inspector

Debug and test MCP server tools, resources, and prompts:

```bash
# Install MCP Inspector
npx @anthropic/mcp-inspector

# Connect to MCP server
# URL: http://localhost:3001/sse
```

Features:
- List and test tools (`simple_query`, `advanced_query`)
- Read resources (`schema://database`)
- Get prompts (`data_analyst`)
- View request/response payloads

### Make Commands

| Command | Description |
|---------|-------------|
| `make up` | Start all services |
| `make down` | Stop all services |
| `make rebuild` | Rebuild and restart |
| `make test` | Run all tests |
| `make test-unit` | Run unit tests only |
| `make test-int` | Run integration tests only |
| `make seed` | Seed the database |
| `make logs s=backend` | Show logs for a service |
| `make status` | Show service status |
| `make clean` | Remove containers and volumes |

---

## Usage

### Example Questions

| Question | Chart Type |
|----------|------------|
| Show total sales by category | Bar |
| Top 5 products by quantity | Bar |
| Monthly sales trend for 2024 | Line |
| Count products per category | Pie |
| Compare total sales in 2026 vs 2022 | Bar |
| Average order value by category | Bar |
| Sales distribution as pie chart | Pie |
| Products with price above 500 | Bar |

---

## API Reference

### POST /api/v1/query

**Request:**
```json
{
  "question": "Show total sales by category"
}
```

**Response:**
```json
{
  "question": "Show total sales by category",
  "chart_type": "bar",
  "rows": [
    { "label": "Electronics", "value": 17059236.4 },
    { "label": "Home", "value": 3001309.34 }
  ]
}
```

---

## MCP Tools

### simple_query

Structured query for single-table operations. SQL is built from validated parameters.

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

Raw SQL for complex queries (JOINs, subqueries). Includes SQL sanitization.

```json
{
  "sql": "SELECT p.category AS label, SUM(s.total_amount) AS value FROM sales s JOIN products p ON s.product_id = p.id GROUP BY p.category",
  "chart_type": "bar"
}
```

---

## Database

### Schema

```
products (id, name, category, price, created_at)
    │
    ├── features (id, product_id, name, description)
    │
    └── sales (id, product_id, quantity, total_amount, sale_date)
```

### Multi-Database Support

| Database | DATABASE_TYPE | DATABASE_URL |
|----------|---------------|--------------|
| PostgreSQL | `postgresql` | `postgresql://user:pass@host/db` |
| MySQL | `mysql` | `mysql://user:pass@host/db` |
| SQLite | `sqlite` | `sqlite:///path/to/file.db` |

---

## Design Decisions

### 1. Two-Tool Design (simple_query + advanced_query)

| Tool | Use Case | Safety |
|------|----------|--------|
| `simple_query` | Single-table aggregations | SQL built from validated structure |
| `advanced_query` | JOINs, complex queries | Raw SQL with sanitization |

**Why only 2 tools?**

| Approach | Pros | Cons |
|----------|------|------|
| **1 tool (raw SQL only)** | Maximum flexibility | High security risk, AI errors in SQL syntax |
| **2 tools (our choice)** | Balance of safety + flexibility | AI must choose correctly |
| **Many tools (per operation)** | Very safe, predictable | Limited queries, complex tool selection |

**Trade-offs of 2-tool approach:**

| Trade-off | Our Choice | Alternative |
|-----------|------------|-------------|
| Safety vs Flexibility | 80% safe (simple), 20% flexible (advanced) | All raw SQL = 100% flexible but risky |
| AI Complexity | AI chooses between 2 tools | Many tools = harder for AI to choose |
| Query Coverage | Covers most business questions | Single tool = limited or unsafe |
| Maintenance | 2 tools to maintain | Many tools = more code to maintain |

**When AI chooses which tool:**

| Question Type | Tool | Why |
|---------------|------|-----|
| "Count products per category" | `simple_query` | Single table, basic aggregation |
| "Total sales by category" | `advanced_query` | Needs JOIN (sales + products) |
| "Top 5 products by revenue" | `advanced_query` | Needs JOIN + ORDER BY + LIMIT |
| "Average price per category" | `simple_query` | Single table (products) |

### 2. SQL Safety Layers

| Layer | Protection |
|-------|------------|
| Keyword blocking | DROP, DELETE, UPDATE, INSERT, ALTER, TRUNCATE |
| Pattern blocking | `;` (multi-statement), `--` (comments), `UNION` |
| Row limit | Auto-adds `LIMIT 1000` |
| Timeout | 30-second query timeout |
| Table whitelist | Only allowed tables in `simple_query` |

### 3. Dynamic Schema Discovery

Schema is fetched from database at runtime via MCP Resource, not hardcoded.

---

## AI Reliability

### Validation

AI responses are validated against MCP tool schemas dynamically:

| Check | Description |
|-------|-------------|
| Tool name | Must exist in MCP server's tool list |
| Required fields | All required fields from inputSchema |
| Enum values | Must match allowed values from schema |

### Retry with Fallback

```
simple_query fails → AI generates raw SQL → Execute advanced_query
```

Implementation: `backend/app/mcp/clients/base.py`

---

## Project Structure

```
DataToVisual/
├── docker-compose.yml
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app
│   │   ├── config.py            # Environment config
│   │   ├── routers/query.py     # API endpoint
│   │   ├── mcp/
│   │   │   ├── server.py        # MCP Server
│   │   │   ├── sql_builder.py   # SQL building & validation
│   │   │   └── clients/
│   │   │       ├── base.py      # MCP client + reliability
│   │   │       └── gemini.py    # Gemini integration
│   │   └── db/
│   │       └── database.py      # SQLAlchemy
│   └── tests/
│       ├── unit/
│       └── integration/
└── frontend/
    ├── index.html
    ├── style.css
    └── app.js
```

---

## Future Improvements

- [ ] Add more AI providers (Claude, OpenAI)
- [ ] Caching for repeated queries
- [ ] User authentication
- [ ] Query history
