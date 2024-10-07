import asyncpg
import os
from datetime import datetime, timedelta
import logging
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv('DATABASE_URL')


async def delete_expired_links():
    pool = await asyncpg.create_pool(DATABASE_URL)
    async with pool.acquire() as conn:
        try:
            await conn.execute("DELETE FROM url_generation_tracker WHERE created_at < $1", datetime.utcnow() - timedelta(minutes=10))
            logging.info("Expired links deleted successfully.")
        except Exception as e:
            logging.error(f"Error deleting expired links: {str(e)}")
        finally:
            await pool.release(conn)


async def create_tables():
    conn = await get_db_connection()
    if conn is None:
        logging.error("No database connection available.")
        return

    try:
        await conn.execute('''CREATE TABLE IF NOT EXISTS short_urls (
            id SERIAL PRIMARY KEY,
            original_url VARCHAR(500) NOT NULL,
            short_url VARCHAR(10) UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ttl TIMESTAMP DEFAULT (CURRENT_TIMESTAMP + INTERVAL '10 minutes')
        );''')

        await conn.execute('''CREATE TABLE IF NOT EXISTS url_generation_tracker (
            id SERIAL PRIMARY KEY,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );''')

        logging.info("Tables created successfully.")
    except Exception as e:
        logging.error(f"Error creating tables: {str(e)}")
    finally:
        await conn.close()

async def get_db_connection():
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        return conn
    except Exception as e:
        logging.error(f"Error connecting to the database: {str(e)}")
        return None

async def check_generation_limit():
    conn = await get_db_connection()
    if conn is None:
        return False
    try:
        row = await conn.fetchrow(
            "SELECT COUNT(*) FROM url_generation_tracker WHERE created_at > $1",
            datetime.utcnow() - timedelta(minutes=1)
        )
        return row['count'] < 10
    finally:
        await conn.close()

async def increment_generation_count():
    conn = await get_db_connection()
    if conn is None:
        return
    try:
        await conn.execute(
            "INSERT INTO url_generation_tracker (created_at) VALUES (CURRENT_TIMESTAMP)"
        )
    finally:
        await conn.close()
