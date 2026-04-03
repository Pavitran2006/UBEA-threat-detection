import sys
import asyncio
from app.database import SessionLocal
from models.user import User
from app.routes import login
from fastapi import Request

async def test_error():
    db = SessionLocal()
    try:
        # Just query the user directly to see if the model has a typo or schema mismatch
        user = db.query(User).filter(User.email == "test@test.com").first()
        print("Query successful:", user)
    except Exception as e:
        print("DB Query Error:", type(e).__name__)
        print(e)
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(test_error())
