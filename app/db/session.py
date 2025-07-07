from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.settings import get_settings

settings = get_settings()
engine = create_engine(
    settings.mysql_uri,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    pool_recycle=1800,
)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
