from quart import request, jsonify, redirect
from marshmallow import Schema, fields
from modules.models import generate_short_url
from modules.db import check_generation_limit, increment_generation_count, get_db_connection
from datetime import datetime
import logging


class ShortUrlSchema(Schema):
    url = fields.String(required=True)


class ExpandUrlSchema(Schema):
    short_url = fields.String(required=True)


def setup_routes(app, spec):
    @app.route('/short', methods=['POST'])
    async def shorten_url():
        """Создать короткую ссылку.

        ---
        requestBody:
            required: true
            content:
                application/json:
                    schema:
                        $ref: '#/components/schemas/ShortUrl'
        responses:
            201:
                description: Успешное создание короткой ссылки
                content:
                    application/json:
                        schema:
                            type: object
                            properties:
                                short_url:
                                    type: string
                                    example: "abc123"
            400:
                description: Неверный формат URL
            500:
                description: Ошибка генерации короткой ссылки
            429:
                description: Лимит на генерацию ссылок превышен
        """
        data = await request.get_json()
        short_url_schema = ShortUrlSchema()

        try:
            original_url = short_url_schema.load(data)['url']
        except Exception as e:
            return jsonify({'error': 'Invalid input data'}), 400

        conn = await get_db_connection()
        if conn is None:
            return jsonify({'error': 'Database connection error'}), 500

        try:
            if await check_generation_limit():
                short_url = await generate_short_url(original_url)
                if short_url:
                    await increment_generation_count()
                    return jsonify({'short_url': short_url}), 201
                return jsonify({'error': 'Error generating short URL'}), 500
            else:
                return jsonify({'limit': "is over, wait a minute"}), 429
        except Exception as e:
            logging.error(f"Error generating short URL: {str(e)}")
            return jsonify({'error': 'Error generating short URL'}), 500
        finally:
            await conn.close()

    @app.route('/<short_url>', methods=['GET'])
    async def redirect_to_original(short_url):
        """Перенаправить на оригинальную ссылку по короткому URL.

        ---
        parameters:
            - name: short_url
              in: path
              required: true
              description: Короткий URL для расширения
              schema:
                  type: string
        responses:
            302:
                description: Перенаправление на оригинальный URL
            404:
                description: Короткий URL не найден
            410:
                description: Короткий URL истек
            500:
                description: Ошибка перенаправления
        """
        conn = await get_db_connection()
        if conn is None:
            return jsonify({'error': 'Database connection error'}), 500

        try:
            url_data = await conn.fetchrow("SELECT original_url, ttl FROM short_urls WHERE short_url = $1", short_url)

            if not url_data:
                return jsonify({'error': 'Short URL not found'}), 404

            original_url, ttl = url_data['original_url'], url_data['ttl']
            if datetime.utcnow() > ttl:
                return jsonify({'error': 'Short URL expired'}), 410

            return redirect(original_url)
        except Exception as e:
            logging.error(f"Error redirecting to original URL: {str(e)}")
            return jsonify({'error': 'Error redirecting to original URL'}), 500
        finally:
            await conn.close()

    @app.route('/expand', methods=['POST'])
    async def expand_url():
        """Расширить короткую ссылку и вернуть оригинальный URL.

        ---
        requestBody:
            required: true
            content:
                application/json:
                    schema:
                        $ref: '#/components/schemas/ExpandUrl'
        responses:
            200:
                description: Успешное расширение короткой ссылки
                content:
                    application/json:
                        schema:
                            type: object
                            properties:
                                original_url:
                                    type: string
                                    example: "https://www.example.com/original-url"
            404:
                description: Короткий URL не найден
            410:
                description: Короткий URL истек
            500:
                description: Ошибка расширения короткой ссылки
        """
        data = await request.get_json()
        expand_url_schema = ExpandUrlSchema()

        try:
            short_url = expand_url_schema.load(data)['short_url']
        except Exception as e:
            return jsonify({'error': 'Invalid input data'}), 400

        conn = await get_db_connection()
        if conn is None:
            return jsonify({'error': 'Database connection error'}), 500

        try:
            url_data = await conn.fetchrow("SELECT original_url, ttl FROM short_urls WHERE short_url = $1", short_url)

            if not url_data:
                return jsonify({'error': 'Short URL not found'}), 404

            original_url, ttl = url_data['original_url'], url_data['ttl']
            if datetime.utcnow() > ttl:
                return jsonify({'error': 'Short URL expired'}), 410

            return jsonify({'original_url': original_url})
        except Exception as e:
            logging.error(f"Error expanding short URL: {str(e)}")
            return jsonify({'error': 'Error expanding short URL'}), 500
        finally:
            await conn.close()

    spec.path(path='/short', view=shorten_url)
    spec.path(path='/<short_url>', view=redirect_to_original)
    spec.path(path='/expand', view=expand_url)

    spec.components.schema('ShortUrl', {
        'type': 'object',
        'properties': {
            'url': {
                'type': 'string',
                'example': 'https://www.example.com'
            }
        }
    })

    spec.components.schema('ExpandUrl', {
        'type': 'object',
        'properties': {
            'short_url': {
                'type': 'string',
                'example': 'abc123'
            }
        }
    })
