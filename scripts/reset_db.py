"""
scripts/reset_db.py
===================
Robust async script to reset/wipe the SQLite compliance database.
Uses SQLAlchemy to drop and recreate all tables in-place.
This bypasses file-locking issues, allowing reset even while the server is active.
"""

import asyncio
import os
import sys

# Add project root to sys.path so we can import app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database.db import get_engine, Base
from app.database import models  # noqa: F401

async def async_reset():
    print("Connecting to the database...")
    engine = get_engine()
    
    try:
        async with engine.begin() as conn:
            print("Dropping all existing compliance tables...")
            await conn.run_sync(Base.metadata.drop_all)
            
            print("Recreating clean compliance tables...")
            await conn.run_sync(Base.metadata.create_all)
            
        print("Success: Compliance database tables have been fully wiped and reset!")
        print("You can now submit clean declaration records successfully.")
    except Exception as e:
        print(f"Error during database reset: {e}")
    finally:
        await engine.dispose()

def main():
    # Run the async loop
    asyncio.run(async_reset())

if __name__ == "__main__":
    main()
