import os
import re
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker
from app.config import settings

# Convert standard PostgreSQL URL to asyncpg format if needed
db_url = settings.DATABASE_URL
if not db_url.startswith('postgresql+asyncpg://'):
    # Replace postgresql:// with postgresql+asyncpg://
    db_url = re.sub(r'^postgresql:\/\/', 'postgresql+asyncpg://', db_url)

# Create async engine
engine = create_async_engine(
    db_url,
    echo=False,
    future=True,
    pool_pre_ping=True,
)

# Create base class for models
Base = declarative_base()

# Create async session factory
async_session_factory = sessionmaker(
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
    class_=AsyncSession,
    bind=engine,
)

# Dependency to get DB session
async def get_db():
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()
