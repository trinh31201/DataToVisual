# DataToVisual

A data-to-visualization system where users can ask business questions in plain English and instantly see the answer as a chart.

## Architecture

Built with **MCP (Model Context Protocol)** for AI-database interaction:

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

## Tech Stack

- **Backend**: Python + FastAPI
- **MCP Server**: Model Context Protocol with SSE transport
- **Database**: PostgreSQL, MySQL, or SQLite (via SQLAlchemy)
- **LLM**: Google Gemini API (Claude/OpenAI ready)
- **Frontend**: HTML/CSS/JS + Chart.js
- **Containerization**: Docker

## Setup

### Prerequisites

- Docker & Docker Compose
- Gemini API key ([Get one free](https://aistudio.google.com/))

### 1. Clone and configure

```bash
git clone <repo-url>
cd DataToVisual

# Create .env file
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY
```

### 2. Start the services

```bash
docker-compose up -d
```

This starts 3 services:
- `postgres` - Database (port 5432)
- `mcp-server` - MCP Server (port 3001)
- `backend` - FastAPI (port 8000)

### 3. Seed the database

```bash
docker exec datatovisual_backend python -m app.db.seed
```

### 4. Open the frontend

```bash
cd frontend
python -m http.server 5500
```

Open **http://localhost:5500**

### API Documentation

Swagger UI available at **http://localhost:8000/docs**

## Example Queries

| Question | Chart Type |
|----------|------------|
| "Compare total sales in 2026 vs 2022" | Bar |
| "How are our sales trending over the last 5 years?" | Line |
| "What are our top 5 selling products?" | Bar |
| "Show sales by product category" | Pie |
| "Monthly sales for 2025" | Line |

## API Endpoints

Base URL: `http://localhost:8000/api/v1`

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
    { "label": "Home", "value": 3001309.34 },
    { "label": "Clothing", "value": 1214876.23 },
    { "label": "Food", "value": 241178.16 }
  ]
}
```

## Switching Databases

Supports PostgreSQL, MySQL, and SQLite via SQLAlchemy.

| Database | DATABASE_TYPE | DATABASE_URL | Driver |
|----------|---------------|--------------|--------|
| PostgreSQL | `postgresql` | `postgresql://user:pass@host/db` | `asyncpg` |
| MySQL | `mysql` | `mysql://user:pass@host/db` | `aiomysql` |
| SQLite | `sqlite` | `sqlite:///path/to/file.db` | `aiosqlite` |

To switch, update `.env`:
```bash
DATABASE_TYPE=mysql
DATABASE_URL=mysql://user:pass@localhost/mydb
```

And install the driver:
```bash
pip install aiomysql  # for MySQL
```

## Project Structure

```
DataToVisual/
├── docker-compose.yml
├── .env.example
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI entry point
│   │   ├── config.py            # Environment config
│   │   ├── routers/
│   │   │   └── query.py         # API endpoints
│   │   ├── mcp/
│   │   │   ├── server.py        # MCP Server (tools, resources, prompts)
│   │   │   └── clients/
│   │   │       ├── base.py      # Base MCP client (SSE transport)
│   │   │       └── gemini.py    # Gemini AI integration
│   │   └── db/
│   │       ├── database.py      # SQLAlchemy (multi-DB support)
│   │       └── seed.py          # Sample data
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── app.js
└── docs/
```

## Database Schema

![Database Schema](docs/database-schema.png)

- **products**: id, name, category, price, created_at
- **features**: id, product_id, name, description (FK → products)
- **sales**: id, product_id, quantity, total_amount, sale_date (FK → products)

Sales data spans 2022-2026 with realistic growth trends.
