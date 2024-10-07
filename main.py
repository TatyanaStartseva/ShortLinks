from quart import Quart
from apispec import APISpec
from apispec.ext.marshmallow import MarshmallowPlugin
from modules.db import create_tables, delete_expired_links
from modules.routes import setup_routes
import logging
import asyncio

app = Quart(__name__)
logging.basicConfig(level=logging.INFO)
spec = APISpec(
    title="Short Links API",
    version="1.0.0",
    openapi_version="3.0.3",
    plugins=[MarshmallowPlugin()],
)
async def periodic_expiration_check():
    while True:
        try:
            await delete_expired_links()
        except Exception as e:
            logging.error(f"Error during periodic expiration check: {str(e)}")

        await asyncio.sleep(600)

@app.before_serving
async def startup():
    asyncio.create_task(periodic_expiration_check())
    await create_tables()

setup_routes(app, spec)

@app.route('/openapi.json', methods=['GET'])
async def openapi_spec():
    return spec.to_dict()

if __name__ == '__main__':
    app.run(debug=True)

