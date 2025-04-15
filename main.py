import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
import httpx
import matplotlib.pyplot as plt
from io import BytesIO
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
from models import Base, Subscription

logging.basicConfig(level=logging.INFO)

bot = Bot(token="7559636676:AAEFpnGsmhOBhaOu_PUhldb8PJ4aSsFigAk")  # Замените на ваш токен
dp = Dispatcher()

engine = create_async_engine("postgresql+asyncpg://user:password@db_bot:5432/bot_db", echo=True)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

@dp.message(Command("stocks"))
async def cmd_stocks(message: types.Message) -> None:
    """Получить список всех акций."""
    async with httpx.AsyncClient() as client:
        response = await client.get("http://data_collector:8000/stocks")
        stocks = response.json()
        stock_list = "\n".join([f"- {stock['ticker']} ({stock['name']})" for stock in stocks])
        await message.answer(f"📜 Список доступных бумаг:\n{stock_list}")

@dp.message(Command("price"))
async def cmd_price(message: types.Message) -> None:
    """Получить цену и график акции."""
    ticker = message.text.split()[1].upper() if len(message.text.split()) > 1 else None
    if not ticker:
        await message.answer("❌ Укажите тикер, например: /price GAZP")
        return
    async with httpx.AsyncClient() as client:
        response = await client.get(f"http://data_collector:8000/stocks/{ticker}")
        if response.status_code != 200:
            await message.answer(f"❌ Бумага {ticker} не найдена")
            return
        stock = response.json()
        plt.figure(figsize=(5, 3))
        plt.plot([1, 2, 3], [stock['price'] - 10, stock['price'], stock['price'] + 10])
        plt.title(f"График {ticker}")
        buf = BytesIO()
        plt.savefig(buf, format="png")
        buf.seek(0)
        await message.answer_photo(
            photo=buf,
            caption=f"📈 Цена {ticker}: {stock['price']} RUB (на {stock['timestamp']})"
        )
        plt.close()

@dp.message(Command("subscribe"))
async def cmd_subscribe(message: types.Message) -> None:
    """Подписаться на уведомления по тикеру."""
    ticker = message.text.split()[1].upper() if len(message.text.split()) > 1 else None
    if not ticker:
        await message.answer("❌ Укажите тикер, например: /subscribe GAZP")
        return
    async with async_session() as session:
        async with session.begin():
            subscription = Subscription(user_id=message.from_user.id, ticker=ticker)
            session.add(subscription)
        await message.answer(f"✅ Вы подписались на уведомления по {ticker}!")

async def main() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())