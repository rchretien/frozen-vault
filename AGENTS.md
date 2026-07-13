# AGENTS.md

> **Agent-Oriented Documentation**: This file provides AI agents with the context and guidelines needed to effectively understand, navigate, and contribute to this codebase.

---

## 📋 Project Overview

**Project Name**: FrozenVault
**Type**: Multi-app workspace  
**Primary Language**: Python 3.13+  
**Framework**: FastAPI  
**Database**: SQLAlchemy ORM (SQLite in-memory for dev, configurable for production)  
**Purpose**: Fridge inventory application with a FastAPI backend and server-rendered frontend

### What This Application Does
This is a CRUD (Create, Read, Update, Delete) REST API that manages a fridge inventory. Users can:
- Add products to their fridge with details (name, type, location, expiry date, etc.)
- List products with pagination and sorting
- Update product information
- Search products by name prefix
- Delete products

---

## 🏗️ Architecture Overview

### Project Structure
```
frozen-vault/
├── apps/
│   └── api/
│       ├── src/frozen_vault_backend/   # Main backend package
│       │   ├── api/                  # API layer
│       │   │   ├── routes/           # API endpoint definitions
│       │   │   └── dependencies/     # FastAPI dependencies
│       │   ├── orm/                  # Database layer
│       │   │   ├── crud/             # CRUD operations
│       │   │   ├── models/           # SQLAlchemy models
│       │   │   ├── schemas/          # Pydantic schemas
│       │   │   ├── enums/            # Enumeration types
│       │   │   └── database.py       # Database engine & session management
│       │   ├── config.py             # Configuration management
│       │   └── exceptions.py         # Custom exceptions
│       ├── tests/                    # Test suite
│       ├── pyproject.toml            # Backend dependencies & config
│       ├── Dockerfile                # Backend container image
│       └── mkdocs.yml                # Backend documentation config
├── docker-compose.yml                # Workspace orchestration
└── AGENTS.md
```

### Key Design Patterns
1. **Generic CRUD Pattern**: `CRUDBase` provides reusable CRUD operations that can be inherited and customized
2. **Repository Pattern**: CRUD classes encapsulate database operations
3. **Dependency Injection**: FastAPI dependencies for database sessions and validation
4. **Schema Separation**: Pydantic schemas for API layer, SQLAlchemy models for database layer

---

## 🔧 Technology Stack

### Core Dependencies
- **FastAPI**: Modern, high-performance web framework for building APIs
- **SQLAlchemy 2.0**: SQL toolkit and ORM
- **Pydantic v2**: Data validation using Python type hints
- **Uvicorn**: ASGI server for development
- **Gunicorn**: Production-grade WSGI HTTP server

### Development Tools
- **Ruff**: Fast Python linter and formatter
- **MyPy**: Static type checker
- **Pytest**: Testing framework
- **Pre-commit**: Git hook automation
- **Poethepoet**: Task runner
- **Docker**: Containerization

---

## 🗄️ Database Architecture

### Models
1. **Product**: Main entity representing food items in the fridge
   - Fields: name, description, quantity, unit, creation_date, expiry_date, image_location
   - Relationships: belongs to ProductType and ProductLocation

2. **ProductType**: Categories (e.g., poultry, meat, fish, vegetables, fruit, dairy, etc.)
   - Pre-populated with emoji-decorated types

3. **ProductLocation**: Storage locations (refrigerator, big freezer, small freezer)
   - Pre-populated on database initialization

### Important Database Considerations
- **Centralized Engine Creation**: All database engine/pool construction is handled by `create_database_engine()` in `config.py`
- **In-Memory Mode**: Uses `StaticPool` to ensure all connections share the same database instance
- **SQLite File Mode**: Uses `NullPool` for file-based databases
- **PostgreSQL Production**: Uses connection pooling (pool_size=20, max_overflow=10) only in production environments
- **PostgreSQL Non-Production**: Uses `NullPool` for simpler connection management
- **Relationship Constraints**: Products have `single_parent=True` and `cascade="all, delete-orphan"` on relationships

---

## 🛠️ Common Development Tasks

### Running the Application
```bash
# Development mode (with hot reload)
uv run --directory apps/api poe api --dev

# Production mode
uv run --directory apps/api poe api

# Custom host/port
uv run --directory apps/api poe api --host 0.0.0.0 --port 8080 --dev
```

### Testing
```bash
uv run --directory apps/api poe test        # Run tests with coverage
uv run --directory apps/api poe lint        # Run linters and formatters
```

### Key Poe Tasks (defined in pyproject.toml)
- `uv run --directory apps/api poe api`: Start the API server
- `uv run --directory apps/api poe test`: Run test suite with coverage
- `uv run --directory apps/api poe lint`: Run pre-commit hooks
- `uv run --directory apps/api poe docs`: Build/serve documentation with MkDocs

---

## 🎯 API Endpoints

### Inventory Management
- **POST /inventory/create**: Create a new product
- **GET /inventory/list**: List products (with pagination, sorting)
- **GET /inventory/startswith**: Search products by name prefix
- **PATCH /inventory/update**: Update a product
- **DELETE /inventory/delete**: Delete a product (currently returns 204 but not implemented)

### Schema Mapping (Important!)
API schemas use `product_name`, but database models use `name`. The CRUD layer handles this mapping:
- `ProductBase.product_name` → `Product.name`
- `ProductBase.product_type` (enum) → `Product.product_type_id` (FK)
- `ProductBase.product_location` (enum) → `Product.product_location_id` (FK)

---

## 🚨 Known Issues & Gotchas

### 1. Database Connection Pooling
- **Centralized Configuration**: All engine creation logic is in `config.create_database_engine()`
- **In-memory databases**: MUST use `StaticPool` to share state across connections
- **File-based databases**: Use `NullPool` to avoid locking issues
- **PostgreSQL**: Uses connection pooling in production, `NullPool` in dev/test/local
- Never hardcode engine creation—always use `create_database_engine()` helper
- Adding new database types (e.g., Postgres) is a local change to `create_database_engine()` only

### 2. Product Update Operation
The update operation had multiple issues (recently fixed):
- **Field Name Mismatch**: API uses `product_name`, DB uses `name`
- **Relationship Conflicts**: Cannot set relationship objects on existing instances with `single_parent=True`
- **Solution**: `encode_update_model` returns a `SimpleNamespace` with only scalar values and FK IDs

### 3. Configuration System
- Uses Pydantic Settings with environment-specific `.env` files
- Environment is determined by `ENVIRONMENT` env var (defaults to "local")
- Config is cached with `@lru_cache` for performance
- Access via `from frozen_vault_backend.config import config`
- **Engine Creation**: Use `create_database_engine()` from `config.py` for all database engine construction

### 4. Timezone Handling
- All timestamps use Brussels timezone (`Europe/Brussels`)
- Set via `config.brussels_tz`

---

## 📝 Coding Conventions

### Code Style
- **Line Length**: 100 characters max
- **Formatter**: Ruff (automatic via pre-commit)
- **Type Hints**: Required for all function signatures
- **Docstrings**: NumPy style

### Naming Conventions
- **Files**: `snake_case.py`
- **Classes**: `PascalCase`
- **Functions/Variables**: `snake_case`
- **Constants**: `UPPER_SNAKE_CASE`
- **Private Members**: Prefix with `_`

### Import Organization (via Ruff)
1. Standard library imports
2. Third-party imports (FastAPI, SQLAlchemy, etc.)
3. Local application imports

### Error Handling
- Use custom exceptions from `exceptions.py`
- FastAPI automatically converts exceptions to HTTP responses
- Use HTTPException for API-level errors
- Use SQLAlchemy exceptions for database errors

---

## 🧪 Testing Guidelines

### Current Test Coverage
- Basic smoke tests exist in `tests/test_api.py`
- **TODO**: Need comprehensive CRUD operation tests
- **TODO**: Need validation tests for schemas
- **TODO**: Need edge case tests (expired products, invalid data, etc.)

### Writing Tests
```python
from fastapi.testclient import TestClient
from frozen_vault_backend.api.app import app

client = TestClient(app)

def test_example():
    response = client.get("/endpoint")
    assert response.status_code == 200
```

---

## 🐛 Debugging Tips

### Enable SQLAlchemy Query Logging
In `src/frozen_vault_backend/api/app.py`, change:
```python
logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)  # or DEBUG
```

### Database Inspection
For in-memory database, it's destroyed on shutdown. To persist during development:
1. Change `config.db_type` to `"sqlite"`
2. Database will be created as `database.db` in project root
3. Use DB Browser for SQLite or similar tools

### Common Debugging Scenarios
- **"No such table" errors**: Database not initialized—check `initialise_db()` is called
- **Relationship errors**: Check for `single_parent` violations—use FK IDs instead of objects
- **Field name errors**: Check schema → model field name mapping in CRUD layer
- **Connection pool errors**: Verify correct `poolclass` for database type

---

## 🔐 Security Considerations

The implemented code should follow security best practices, including
preventing OWASP top 10 threats.

---

## 🚀 Deployment

### Containerized Deployment
```bash
docker compose up app
```

### Environment Variables
- `ENVIRONMENT`: Deployment environment (local, dev, prod)
- `DB_TYPE`: Database type (in_memory, sqlite, postgres)
- `COMMIT`: Git commit SHA (injected by CI/CD)
- `BRANCH`: Git branch name (injected by CI/CD)

For Postgres:
- `DB_USER`, `DB_PASSWORD`, `DB_NAME`, `DB_HOST`, `DB_PORT`

---

## 📚 Additional Resources

### Documentation
- **FastAPI Docs**: https://fastapi.tiangolo.com/
- **SQLAlchemy 2.0**: https://docs.sqlalchemy.org/en/20/
- **Pydantic V2**: https://docs.pydantic.dev/latest/

### Project-Specific Docs
- API documentation available at `/docs` (Swagger UI)
- OpenAPI spec at `/openapi.json`
- MkDocs site (run `poe docs --serve`)

---

## 🤝 Contributing Guidelines for Agents

### When Fixing Bugs
1. Read the error message carefully—SQLAlchemy errors often include helpful links
2. Check if the issue is related to schema-model field name mapping
3. For relationship errors, prefer using FK IDs over relationship objects
4. Always test changes with both create and update operations

### When Adding Features
1. Follow the existing CRUD pattern in `base_crud.py`
2. Add Pydantic schemas for request/response in `schemas/`
3. Implement CRUD methods in `crud/`
4. Create API endpoints in `routes/`
5. Update this AGENTS.md if you introduce new patterns

### When Refactoring
1. Maintain backward compatibility with existing API endpoints
2. Update tests to cover refactored code
3. Run `uv run poe lint` and `uv run poe test` before committing
4. Update docstrings and type hints

### Code Review Checklist
- [ ] Type hints on all function signatures
- [ ] Docstrings in NumPy style
- [ ] No hardcoded values—use config
- [ ] Proper error handling
- [ ] Tests pass (`uv run poe test`)
- [ ] Linting passes (`uv run poe lint`)
- [ ] No SQLAlchemy relationship violations

---
