"""
Centralized application configuration.
All values are sourced from environment variables (populated via Secret Manager
in Cloud Run, or a local .env file for development).
"""
from functools import lru_cache
from urllib.parse import quote_plus

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- General ---
    environment: str = "development"
    project_id: str = "your-gcp-project"
    region: str = "europe-west1"
    cors_origins: str = "http://localhost:5173"

    # --- Vertex AI ---
    vertex_location: str = "europe-west1"
    gemini_model: str = "gemini-2.5-flash"
    embedding_model: str = "text-embedding-004"

    # --- Cloud SQL (Postgres) ---
    sql_host: str = "localhost"
    sql_port: int = 5432
    sql_db: str = "app_db"
    sql_user: str = "app_user"
    sql_password: str = "change-me"
    sql_instance_connection_name: str = ""  # set only in Cloud Run

    @property
    def sql_url(self) -> str:
        user = quote_plus(self.sql_user)
        password = quote_plus(self.sql_password)
        if self.sql_host.startswith("/"):
            # Cloud Run mounts the instance socket at /cloudsql/PROJECT:REGION:INSTANCE
            return f"postgresql+asyncpg://{user}:{password}@/{self.sql_db}?host={quote_plus(self.sql_host)}"
        return f"postgresql+asyncpg://{user}:{password}@{self.sql_host}:{self.sql_port}/{self.sql_db}"

    # --- BigQuery ---
    bq_dataset: str = "graphrag"
    bq_vector_table: str = "document_embeddings"

    # --- Neo4j (AuraDB or self-hosted) ---
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "change-me"
    neo4j_database: str = "neo4j"

    # --- Cloud Storage ---
    gcs_bucket: str = "your-project-documents"

    # --- Auth ---
    firebase_project_id: str = ""
    admin_emails: str = ""  # comma-separated fallback allowlist; prefer Firebase custom claims

    @property
    def admin_email_list(self) -> list[str]:
        return [e.strip().lower() for e in self.admin_emails.split(",") if e.strip()]

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
