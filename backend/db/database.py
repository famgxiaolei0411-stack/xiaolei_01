"""
数据库连接管理
================
SQLAlchemy 异步引擎 + 会话工厂。
MVP 使用 SQLite，后续可无缝切换到 PostgreSQL。
"""

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from config import DATABASE_URL

# ── 异步引擎 ──────────────────────────────────────
# SQLite + aiosqlite 使用 NullPool，不支持 pool_size 参数
# 通过 connect_args 优化并发写入
engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    future=True,
    pool_pre_ping=True,
    connect_args={
        "check_same_thread": False,  # SQLite 多线程支持
        "timeout": 30,               # 写入锁等待超时 (秒)
    },
)

# ── 会话工厂 ──────────────────────────────────────
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# ── ORM 基类 ──────────────────────────────────────
class Base(DeclarativeBase):
    """SQLAlchemy ORM 基类。"""
    pass


# ── 依赖注入 ──────────────────────────────────────
async def get_db() -> AsyncSession:
    """FastAPI 依赖注入：获取数据库会话。

    用法:
        @router.get("/items")
        async def list_items(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """创建所有表（应用启动时调用）。"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """释放数据库连接（应用关闭时调用）。"""
    await engine.dispose()
