from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_APP_SECRET = "dev-secret-not-for-production-use"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    database_url: str = "postgresql+asyncpg://openavisio:devpassword123@localhost:5432/vaultdb"

    # Redis / Celery
    redis_url: str = "redis://localhost:6379/0"

    # JWT
    app_secret: str = DEV_APP_SECRET
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    # AI service
    ai_service_url: str = "http://localhost:8001"
    aiservice_token: str = ""  # shared secret for backend→aiservice calls (#46)

    @property
    def ai_service_headers(self) -> dict[str, str]:
        return {"X-AI-Service-Token": self.aiservice_token} if self.aiservice_token else {}

    # Document storage
    document_storage_path: str = "./data/documents"
    storage_backend: str = "local"  # "local" | "minio"

    # MinIO (used when storage_backend = "minio")
    minio_endpoint: str = ""
    minio_bucket: str = "openavisio"
    minio_access_key: str = ""
    minio_secret_key: str = ""
    minio_secure: bool = True

    # CORS
    cors_origins: str = "http://localhost:3000"

    # OCR / Pipeline
    embedding_scheduler_batch_size: int = 50
    embedding_scheduler_cron: str = "*/15 * * * *"

    # WebAuthn / Passkeys
    webauthn_rp_id: str = "localhost"
    webauthn_rp_name: str = "OpenAvisio"
    webauthn_origin: str = "http://localhost:3000"

    # Document encryption (envelope scheme — see ADR 018)
    # Generate with: python -c "import os,base64; print(base64.b64encode(os.urandom(32)).decode())"
    document_encryption_key: str = ""

    # Licensing
    license_public_key: str = ""  # Ed25519 public key (raw 32 bytes, base64); empty = use embedded production key

    # Frontend URL used in email links (e.g. https://app.example.com)
    app_url: str = ""

    # One-time token gating POST /organization/init in production (see setup.sh)
    bootstrap_token: str = ""

    # Demo instances: when set, document upload accepts ONLY a file with exactly
    # this sha256 (the bundled sample), and patient photos are refused entirely.
    demo_locked_upload_sha256: str = ""

    # SMTP fallback for hosted Deployments (#249). Normally SMTP is configured in
    # the admin UI and stored as SystemSetting rows; a hosted instance is handed
    # over ready to send, and writing into the customer's database to achieve
    # that is exactly what the operator promises not to do. DB rows win when set.
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""

    # Operator copy of pipeline alerts (#250). The instance admins are the
    # customer, who cannot fix a broken worker; the operator has no account here
    # by design. Counts only, never a patient reference.
    ops_alert_email: str = ""

    # Environment
    environment: str = "development"
    # Off for test runs only: the suite logs in dozens of times from one client
    # and would trip its own limiter. Never disable this in production (#109).
    rate_limit_enabled: bool = True

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_dev(self) -> bool:
        return self.environment == "development"

    @model_validator(mode="after")
    def _guard_production(self):
        """Fail closed: never boot a non-dev instance with dev defaults."""
        if self.is_dev:
            return self
        problems = []
        if self.app_secret == DEV_APP_SECRET:
            problems.append("APP_SECRET is the built-in dev default")
        if not self.document_encryption_key:
            problems.append("DOCUMENT_ENCRYPTION_KEY is unset")
        if "devpassword123" in self.database_url:
            problems.append("DATABASE_URL uses the dev default password")
        if not self.rate_limit_enabled:
            problems.append("RATE_LIMIT_ENABLED=false — that switch exists for the test suite only")
        if problems:
            raise ValueError(
                "Refusing to start with ENVIRONMENT=" + self.environment
                + ": " + "; ".join(problems)
            )
        return self


settings = Settings()
