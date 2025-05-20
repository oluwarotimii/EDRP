import os
import re
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.ext.asyncio import async_sessionmaker
from app.config import settings

# Extract database connection components from URL
# Replit Database URL format: postgresql://user:pass@host/dbname?sslmode=require
url_pattern = r'postgresql://([^:]+):([^@]+)@([^/]+)/([^\?]+)(\?.*)?'
match = re.search(url_pattern, settings.DATABASE_URL)

if match:
    user, password, host, dbname, _ = match.groups()
    # Construct a URL that works with asyncpg
    db_url = f"postgresql+asyncpg://{user}:{password}@{host}/{dbname}"
else:
    # Fallback if pattern doesn't match
    db_url = settings.DATABASE_URL.replace('postgresql://', 'postgresql+asyncpg://')
    # Remove sslmode parameter
    db_url = re.sub(r'\?sslmode=require', '', db_url)

# Create async SQLAlchemy engine with SSL configuration
engine = create_async_engine(
    db_url,
    echo=False,
    future=True,
    connect_args={"ssl": True},
)

# Create base class for models
Base = declarative_base()

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    expire_on_commit=False,
    class_=AsyncSession,
)

# Dependency to get DB session
async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
