from flask import Blueprint, current_app, abort, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from .. import db
from ..models import User, Resume
from ..providers import ProviderError
from ..utils import validation_required
from ..schema import resume_schema


module = Blueprint('resume', __name__)


@module.route('/resume', methods=['GET'])
@jwt_required
def resume():
    """
    Получение списка резюме пользователя по всем аккаунтам

    .. :quickref: resume; Получить список резюме

    **Пример запроса**:

        .. sourcecode:: http

            GET /refresh HTTP/1.1
            Authorization: JWT q1w2.e3r4.t5y

    **Пример ответа**:

        .. sourcecode:: http

            HTTP/1.1 200 OK
            Content-Type: application/json

            {
                "provider_one": [
                    {
                        "enabled": false,
                        "link": "https://<provider's resume page>",
                        "name": "John Doe",
                        "published": "Fri, 05 Oct 2018 20:18:11 GMT",
                        "title": "Proctologist",
                        "identity": "erwhy2333r23rd2r32er23",
                        "photo": "https://<url to photo>"
                    }
                ],
                "provider_two": [
                    {
                        "enabled": true,
                        "link": "https://<provider's resume page>",
                        "name": "Lorem Ipsum",
                        "published": "Sat, 10 Mar 2018 12:59:06 GMT",
                        "title": "Jeweler",
                        "identity": "23rd2r32er23erwhy2333r"
                        "photo": "https://<url to photo>"
                    }
                ]
            }

    :reqheader Authorization: действующий JWT-токен

    :statuscode 200: OK
    :statuscode 401: ошибки авторизации/проблемы с токеном
    :statuscode 500: ошибки бэкенда
    :statuscode 503: ошибки взаимодействия с провайдером
    """
    result = {}
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)

        for account in user.accounts:
            provider = current_app.providers[account.provider]

            if provider.name not in result:
                result[provider.name] = []

            resumes = provider.fetch(account.access)
            for item in resumes:
                resume = Resume.query.filter_by(
                    identity=item['identity']).first()
                if not resume:
                    resume = Resume(
                        identity=item['identity'], enabled=False,
                        name=item['title'], owner=user, account=account)
                    current_app.logger.info(f'Resume created: {resume}')

                resume.name = item['title']
                resume.owner = user
                db.session.add(resume)

                item['enabled'] = resume.enabled

            result[provider.name].extend(resumes)

        db.session.commit()

    except ProviderError as e:
        current_app.logger.error(f'Resume error: {e}')
        return abort(503, 'Provider error')

    else:
        return jsonify(result)


@module.route('/resume', methods=['POST'])
@jwt_required
@validation_required(resume_schema)
def resume_toggle():
    """
    Включение/выключение автоматического обновления резюме

    .. :quickref: resume; Включить/выключить автообновление

    **Пример запроса**:

        .. sourcecode:: http

            POST /resume HTTP/1.1
            Authorization: JWT q1w2.e3r4.t5y
            Content-Type: application/json

            {
                "identity": "q1w2e3r4t5y6"
            }

    **Пример ответа**:

        .. sourcecode:: http

            HTTP/1.1 200 OK
            Content-Type: application/json

            {
                "enabled": true
            }

    :reqheader Authorization: действующий JWT-токен

    :reqjson string identity: идентификатор резюме

    :statuscode 200: OK
    :statuscode 400: невалидный JSON в теле запроса
    :statuscode 401: ошибки авторизации/проблемы с токеном
    :statuscode 500: ошибки бэкенда
    """
    user_id = get_jwt_identity()
    user = User.query.get(user_id)

    identity = request.get_json()['identity']
    resume = Resume.query.filter_by(identity=identity, owner=user).first()

    if not resume:
        return abort(404, 'Resume not found')

    resume.enabled = not resume.enabled
    db.session.add(resume)
    db.session.commit()

    current_app.logger.info(f'Resume toggled: {resume}')
    return jsonify(enabled=resume.enabled)
