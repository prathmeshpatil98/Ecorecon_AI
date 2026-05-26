---
name: fastapi-enterprise-backend
description: |
  Use this skill to implement the core FastAPI backend utilizing strict Clean Architecture principles, repository-service patterns, dependency injection, and deterministic validation.
---

# FastAPI Enterprise Backend Skill

## 1. Clean Architecture Segregation

The backend architecture is strictly decoupled. Operations are isolated into modular directories to maintain clear boundaries. **Route handlers must never perform math or access databases directly.**

```
   ┌───────────────────┐
   │    HTTP Clients   │
   └─────────┬─────────┘
             │ HTTP Request
             ▼
   ┌───────────────────┐
   │    API Routes     │ ◄─── Dependency Injection (FastAPI Depends)
   └─────────┬─────────┘
             │ Pydantic Validation / Schema Ingestion
             ▼
   ┌───────────────────┐
   │ Business Services │
   └─────────┬─────────┘
             │ Orchestration & Computation (Pure Python)
             ▼
   ┌───────────────────┐
   │    Repositories   │
   └─────────┬─────────┘
             │ SQLAlchemy ORM Session Handling
             ▼
   ┌───────────────────┐
   │ Database Storage  │ (SQLite / In-Memory Isolation)
   └───────────────────┘
```

---

## 2. Deterministic Validation with Pydantic v2

All incoming payloads are validated at the edge. The `/submit` endpoint utilizes strict validation constraints that execute *without* any LLM dependency.

### Concrete Schema Ingestion Pattern

Here is the exact schema implementation required for monthly declarations. It validates the month string format (`YYYY-MM`) and ensures no negative weight values are present:

```python
import re
from datetime import datetime
from typing import Dict
from pydantic import BaseModel, Field, field_validator, model_validator

class PlasticDeclarationCreate(BaseModel):
    """
    Validation schema for incoming plastic declarations.
    """
    producer_id: str = Field(..., min_length=3, description="Registered identifier of the producer.")
    month: str = Field(..., description="Reporting period in YYYY-MM format.")
    declared_quantities_kg: Dict[str, float] = Field(
        ...,
        description="Dictionary mapping plastic categories to quantities in kilograms."
    )

    @field_validator("month")
    @classmethod
    def validate_month_format(cls, v: str) -> str:
        """
        Verify that the month strictly conforms to the YYYY-MM format.
        """
        if not re.match(r"^\d{4}-(0[1-9]|1[0-2])$", v):
            raise ValueError("Month must be in YYYY-MM format (e.g., 2026-04)")
        
        # Verify it represents a realistic date (no year 9999 validation bypasses)
        try:
            year, month = map(int, v.split("-"))
            if not (2000 <= year <= 2100):
                raise ValueError("Year must be between 2000 and 2100")
        except Exception as e:
            raise ValueError(f"Invalid date representation in month: {e}")
        
        return v

    @field_validator("declared_quantities_kg")
    @classmethod
    def validate_quantities(cls, v: Dict[str, float]) -> Dict[str, float]:
        """
        Ensure all categories have valid non-negative weight counts.
        """
        valid_categories = {"rigid_plastic", "flexible_plastic", "multilayer_plastic"}
        
        if not v:
            raise ValueError("At least one plastic category must be declared.")
            
        for category, qty in v.items():
            if category not in valid_categories:
                raise ValueError(f"Unsupported plastic category: {category}. Must be one of {valid_categories}")
            if qty < 0:
                raise ValueError(f"Declared quantity for '{category}' cannot be negative (got {qty} kg).")
                
        return v
```

---

## 3. Database Isolation & Transaction Rules

SQLAlchemy ORM handles the database lifecycle. To support high-velocity test validation and production safety:
1.  **Scope Session Lifetime**: Use the dependency injection `yield` pattern to guarantee connection closure.
2.  **No Lazy Loading in APIs**: Use joined eager loading to fetch related category declarations to avoid `LazyLoading` errors after database sessions terminate.

### Preventing Test State Leakage (In-Memory SQLite)

When using in-memory SQLite (`sqlite:///:memory:`) for pytest suites, connection caching can keep the database state active across tests, resulting in contamination.
*   **The Issue**: If the database engine singleton remains cached, tables and schema states are shared dynamically.
*   **The Fix**: Force engine teardowns and cache-bypassing on setup/teardown within `conftest.py`.

#### Standard Teardown Block for `conftest.py`

```python
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database.db import Base, get_db

@pytest.fixture(autouse=True)
def clean_database():
    """
    Guarantees clean in-memory database isolation for every single test execution.
    """
    # 1. Create unique engine for the test run
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    # 2. Re-create all tables freshly
    Base.metadata.create_all(bind=engine)
    
    yield TestingSessionLocal
    
    # 3. Drop all tables on teardown and dispose of the engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
```

---

## 4. Error Mapping to Standard HTTP Exceptions

Any validation or reconciliation failure should raise a specialized exception that maps transparently to standard JSON errors via FastAPI's global exception handler.

```python
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from app.core.exceptions import EcoReconException, EntityNotFoundError

app = FastAPI()

@app.exception_handler(EcoReconException)
async def ecorecon_exception_handler(request: Request, exc: EcoReconException):
    """
    Captures platform-specific domain errors and returns formatted responses.
    """
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error_code": exc.error_code,
            "detail": exc.message,
            "timestamp": exc.timestamp.isoformat()
        }
    )
```
