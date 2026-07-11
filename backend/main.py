from dotenv import load_dotenv
from pathlib import Path
from fastapi.middleware.cors import CORSMiddleware

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import os
import logging
from fastapi import FastAPI
from motor.motor_asyncio import AsyncIOMotorClient

from routes_auth import router as auth_router
from routes_app import router as app_router
from seed import seed_database

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("learnhero")

mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

app = FastAPI(title="Brainrot Academy API")
app.state.db = db

def _csv_env(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


origins = _csv_env("CORS_ORIGINS", os.environ.get("FRONTEND_URL", "http://localhost:5173"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/")
async def root():
    return {"app": "Brainrot-Academy", 
            "status": "ok",
            "message": "Brainrot-Academy API is running successfully!!"
            }


app.include_router(auth_router)
app.include_router(app_router)


async def ensure_indexes():
    await db.users.create_index("email", unique=True)
    await db.users.create_index("user_id", unique=True)
    await db.courses.create_index("course_id", unique=True)
    await db.enrollments.create_index([("user_id", 1), ("course_id", 1)], unique=True)
    await db.user_sessions.create_index("session_token", unique=True)
    await db.notifications.create_index([("user_id", 1), ("created_at", -1)])


@app.on_event("startup")
async def on_startup():
    await ensure_indexes()
    if os.environ.get("SEED_ON_STARTUP", "false").lower() == "true":
        try:
            await seed_database(db)
            logger.info("Database seeded")
        except Exception as e:
            logger.error(f"Seed failed: {e}")


@app.on_event("shutdown")
async def on_shutdown():
    client.close()
