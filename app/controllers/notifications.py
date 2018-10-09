
from datetime import datetime, timedelta

from flask import Blueprint, current_app, request, jsonify, abort
from flask_jwt_extended import jwt_required, get_jwt_identity
from telebot import types

from .. import db
from ..models import User, Confirmation, Subscription
from ..utils import validation_required, generate_confirm_code
from ..schema import subscription_schema


module = Blueprint('notifications', __name__, url_prefix='/notifications')


@module.route('/channels', methods=['GET'])
@jwt_required
def channels():
    """
    Список доступных каналов уведомлений

    .. :quickref: notifications; Доступные каналы уведомлений

    **Пример запроса**:

        .. sourcecode:: http

            GET /notifications/channels HTTP/1.1
            Authorization: JWT q1w2.e3r4.t5y

    **Пример ответа**:

        .. sourcecode:: http

            HTTP/1.1 200 OK
            Content-Type: application/json

            [
                "<channel_1>",
                "<channel_2>"
            ]

    :reqheader Authorization: действующий JWT-токен

    :statuscode 200: OK
    :statuscode 401: ошибки авторизации/проблемы с токеном
    :statuscode 500: ошибки бэкенда
    """
    return jsonify(current_app.config['NOTIFICATIONS_CHANNELS'])


@module.route('/confirm/<channel>', methods=['GET'])
@jwt_required
def confirmation(channel):
    """
    Генерация кода подтверждения канала уводомлений

    .. :quickref: notifications; Генерация кода подтверждения

    **Пример запроса**:

        .. sourcecode:: http

            GET /notifications/confirm/<channel_name> HTTP/1.1
            Authorization: JWT q1w2.e3r4.t5y

    **Пример ответа**:

        .. sourcecode:: http

            HTTP/1.1 200 OK
            Content-Type: application/json

            {
                "code": "12345678",
                "ttl": 37
            }

    :reqheader Authorization: действующий JWT-токен

    :reqjson string channel: канал уведомлений

    :statuscode 200: OK
    :statuscode 401: ошибки авторизации/проблемы с токеном
    :statuscode 500: ошибки бэкенда
    """

    if channel not in current_app.config['NOTIFICATIONS_CHANNELS']:
        return abort(404, 'Notification channel not found')

    user_id = get_jwt_identity()
    user = User.query.get(user_id)

    for confirm in user.confirmations:
        if confirm.channel == channel and not confirm.is_expired:
            return jsonify(code=confirm.code, ttl=confirm.seconds_left)

        db.session.delete(confirm)
        db.session.commit()

    code = generate_confirm_code(length=current_app.config['OTP_LENGTH'])
    ttl = timedelta(seconds=current_app.config[f'OTP_TTL_{channel.upper()}'])
    timestamp = datetime.utcnow() + ttl

    confirmation = Confirmation(
        code=code, expires=timestamp, channel=channel, owner=user)
    db.session.add(confirmation)
    db.session.commit()

    current_app.logger.info(f'Confirmation: {confirmation}')
    return jsonify(code=confirmation.code, ttl=confirmation.seconds_left)


@module.route('/subscriptions', methods=['GET'])
@jwt_required
def subscriptions():
    """
    Список подписок на каналы уведомлений

    .. :quickref: notifications; Получить подписки пользователя

    **Пример запроса**:

        .. sourcecode:: http

            GET /notifications/subscriptions HTTP/1.1
            Authorization: JWT q1w2.e3r4.t5y

    **Пример ответа**:

        .. sourcecode:: http

            HTTP/1.1 200 OK
            Content-Type: application/json

            [
                {
                    "channel": "<channel_type_1>",
                    "enabled": true
                },
                {
                    "channel": "<channel_type_2>",
                    "enabled": false
                }
            ]

    :reqheader Authorization: действующий JWT-токен

    :statuscode 200: OK
    :statuscode 401: ошибки авторизации/проблемы с токеном
    :statuscode 500: ошибки бэкенда
    """
    user_id = get_jwt_identity()
    user = User.query.get(user_id)

    subscriptions = []
    for sub in user.subscriptions:
        item = {
            'channel': sub.channel,
            'enabled': sub.enabled,
            'confirmed': sub.confirmed
        }
        subscriptions.append(item)

    return jsonify(subscriptions)


@module.route('/subscriptions', methods=['POST'])
@jwt_required
@validation_required(subscription_schema)
def subscriptions_toggle():
    """
    Включение/выключение уведомления через выбранный канал

    .. :quickref: notifications; Включить/выключить уведомления

    **Пример запроса**:

        .. sourcecode:: http

            POST /notifications/subscriptions HTTP/1.1
            Authorization: JWT q1w2.e3r4.t5y
            Content-Type: application/json

            {
                "channel": "<channel_type>"
            }

    **Пример ответа**:

        .. sourcecode:: http

            HTTP/1.1 200 OK
            Content-Type: application/json

            {
                "enabled": true
            }

    :reqheader Authorization: действующий JWT-токен

    :reqjson string channel: канал уведомлений

    :statuscode 200: OK
    :statuscode 400: невалидный JSON в теле запроса
    :statuscode 401: ошибки авторизации/проблемы с токеном
    :statuscode 500: ошибки бэкенда
    """
    user_id = get_jwt_identity()
    user = User.query.get(user_id)

    post_data = request.get_json()
    channel = post_data['channel']

    sub = Subscription.query.filter_by(
        owner=user, channel=channel).first_or_404()

    if not sub.is_confirmed:
        return abort(403, 'Channel not confirmed')

    sub.enabled = not sub.enabled
    db.session.add(sub)
    db.session.commit()

    current_app.logger.info(f'Subscription toggled: {sub}')
    return jsonify(enabled=sub.enabled)


@module.route(f'/{current_app.tgsecret}', methods=['POST'])
def webhook():
    try:
        post_data = request.get_json()
        update = types.Update.de_json(post_data)
        current_app.bot.process_new_updates([update])
    except Exception as e:
        current_app.logger.error(f'Read telegram updates failed: {e}')
    finally:
        return '', 200


@current_app.bot.message_handler(commands=['start'])
def command_start(msg):
    current_app.bot.send_message(
        msg.chat.id, 'Please, enter the confirmation code')


@current_app.bot.message_handler(regexp='^[0-9]{8}$')
def validate_confirmation(msg):
    code = msg.text
    confirmation = Confirmation.query.filter_by(code=code).first()

    if not confirmation:
        current_app.logger.info(f'Confirmation code not found: {code}')
        current_app.bot.send_message(
            msg.chat.id, 'Confirmation code not found')
        return

    if confirmation.is_expired:
        current_app.logger.info(
            f'Confirmation code is expired: {confirmation}')
        current_app.bot.send_message(
            msg.chat.id, 'Confirmation code is expired')
        return

    sub = Subscription.query.filter_by(
        channel='telegram', owner=confirmation.owner).first()

    if sub:
        current_app.logger.warning(f'Subscription already exists: {sub}')
        current_app.bot.send_message(
            msg.chat.id, 'Subscription already exists')
        return

    sub = Subscription(
        address=msg.chat.id, channel='telegram',
        owner=confirmation.owner, confirmed=True)

    db.session.add(sub)
    db.session.commit()

    current_app.logger.info(f'Subscription created: {sub}')
    current_app.bot.send_message(
        msg.chat.id, 'Success. You may enable notifications on site')
    return


@current_app.bot.message_handler(func=lambda msg: True)
def invalid_message(msg):
    return_text = 'Invalid message'
    current_app.logger.debug(f'{return_text}: {msg.text}')
    current_app.bot.send_message(msg.chat.id, return_text)
