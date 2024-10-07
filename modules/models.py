import shortuuid
from datetime import datetime
from modules.db import get_db_connection

async def generate_short_url(original_url):
    conn = await get_db_connection()
    if conn is None:
        return None

    try:
        existing_url = await conn.fetchrow(
            "SELECT short_url, ttl FROM short_urls WHERE original_url = $1",
            original_url
        )

        if existing_url:
            if datetime.utcnow() <= existing_url['ttl']:
                return existing_url['short_url']
            else:
                await conn.execute(
                    "DELETE FROM short_urls WHERE original_url = $1",
                    original_url
                )

        short_url = shortuuid.uuid()[:6]
        await conn.execute(
            "INSERT INTO short_urls (original_url, short_url) VALUES ($1, $2)",
            original_url, short_url
        )
        return short_url
    except Exception as e:
        logging.error(f"Error generating short URL: {str(e)}")
        return None
    finally:
        await conn.close()

