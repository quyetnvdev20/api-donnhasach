from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str
    RABBITMQ_URL: str
    KEYCLOAK_HOST: str
    KEYCLOAK_REALM: str
    KEYCLOAK_CLIENT_ID: str
    KEYCLOAK_CLIENT_SECRET: str
    OPENAI_API_KEY: str
    GOOGLE_API_KEY: str
    MINIO_ENDPOINT_XM: str
    MINIO_ACCESS_KEY_XM: str
    MINIO_SECRET_KEY_XM: str
    MINIO_BUCKET_NAME_XM: str
    MINIO_FOLDER_PATH_XM: str
    MINIO_USE_SSL_XM: str
    class Config:
        env_file = ".env"

settings = Settings() 