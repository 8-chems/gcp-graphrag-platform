import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.config import get_settings
from app.tools import neo4j_tool, sql_tool

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up (environment=%s)", settings.environment)
    try:
        await sql_tool.run_migrations()
    except Exception as exc:  # noqa: BLE001
        logger.warning("SQL migrations skipped/failed at startup: %s", exc)
    try:
        await neo4j_tool.ensure_constraints()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Neo4j constraint setup skipped/failed at startup: %s", exc)

    yield

    logger.info("Shutting down")
    await neo4j_tool.close_driver()


app = FastAPI(
    title="GraphRAG Platform API",
    description="FastAPI + LangGraph + Vertex AI + Neo4j + BigQuery/Cloud SQL agentic backend",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")


@app.get("/")
async def root():
    return {"service": "graphrag-platform-api", "status": "running"}
