"""Async database engine and session management."""
from pathlib import Path
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool

from models import Base


class DatabaseEngine:
    """Async database engine wrapper."""
    
    def __init__(self, database_url: str):
        self.database_url = database_url
        self._engine = None
        self._session_factory = None
    
    async def init(self) -> None:
        """Initialize database engine and create tables."""
        # Ensure data directory exists for SQLite
        if "sqlite" in self.database_url:
            db_path = self.database_url.split("///")[-1]
            if db_path.startswith("./"):
                db_path = db_path[2:]
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Create async engine
        connect_args = {}
        if "sqlite" in self.database_url:
            connect_args = {"check_same_thread": False}
        
        self._engine = create_async_engine(
            self.database_url,
            echo=False,
            connect_args=connect_args,
        )
        
        # Create session factory
        self._session_factory = async_sessionmaker(
            self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        
        # Create all tables
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    
    async def close(self) -> None:
        """Close database engine."""
        if self._engine:
            await self._engine.dispose()
    
    def get_session(self) -> AsyncSession:
        """Get a new async session."""
        if not self._session_factory:
            raise RuntimeError("Database not initialized. Call init() first.")
        return self._session_factory()
    
    @property
    def engine(self):
        """Get the underlying engine."""
        return self._engine


# Global engine instance
_db_engine: DatabaseEngine | None = None


async def init_database(database_url: str) -> DatabaseEngine:
    """Initialize global database engine."""
    global _db_engine
    _db_engine = DatabaseEngine(database_url)
    await _db_engine.init()
    return _db_engine


def get_db_engine() -> DatabaseEngine:
    """Get global database engine."""
    if _db_engine is None:
        raise RuntimeError("Database not initialized")
    return _db_engine


def get_session() -> AsyncSession:
    """Get a new database session."""
    return get_db_engine().get_session()
