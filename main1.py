from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
from pydantic import BaseModel
import httpx
import asyncio
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    from models import Stock, Signal
    logger.info("Импорт Stock и Signal успешен")
except ImportError as e:
    logger.error(f"Ошибка импорта: {e}")
    raise

from tasks import collect_data_task, detect_anomalies_task

app = FastAPI()

# БД
engine = create_async_engine("postgresql+asyncpg://user:password@db_data:5432/data_db", echo=True)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# Pydantic модели
class StockResponse(BaseModel):
    ticker: str
    name: str
    price: float
    timestamp: str

class SignalResponse(BaseModel):
    ticker: str
    message: str
    timestamp: str

@app.get("/stocks")
async def get_stocks() -> list[StockResponse]:
    """Возвращает список всех акций."""
    async with async_session() as session:
        result = await session.execute(select(Stock))
        stocks = result.scalars().all()
        return [StockResponse(ticker=s.ticker, name=s.name, price=s.price, timestamp=s.timestamp) for s in stocks]

@app.get("/stocks/{ticker}")
async def get_stock(ticker: str) -> StockResponse | dict:
    """Возвращает данные по акции по тикеру."""
    async with async_session() as session:
        result = await session.execute(select(Stock).filter_by(ticker=ticker))
        stock = result.scalars().first()
        if stock:
            return StockResponse(ticker=stock.ticker, name=stock.name, price=stock.price, timestamp=stock.timestamp)
        return {"error": "Stock not found"}

@app.get("/signals")
async def get_signals(ticker: str) -> list[SignalResponse]:
    """Возвращает последние сигналы по тикеру."""
    async with async_session() as session:
        result = await session.execute(select(Signal).filter_by(ticker=ticker))
        signals = result.scalars().all()
        return [SignalResponse(ticker=s.ticker, message=s.message, timestamp=s.timestamp) for s in signals]

@app.on_event("startup")
async def startup() -> None:
    """Инициализация БД и запуск фоновых задач."""
    async with engine.begin() as conn:
        await conn.run_sync(Stock.metadata.create_all)
        await conn.run_sync(Signal.metadata.create_all)
    asyncio.create_task(collect_data_task())
    asyncio.create_task(detect_anomalies_task())