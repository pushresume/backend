from flask import Blueprint, current_app, abort, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy.exc import SQLAlchemyError

from .. import db
from ..models import User, Resume
from ..providers import ProviderError
from ..utils import validation_required


module = Blueprint('resume', __name__)


@module.route('/resume', methods=['GET'])
@jwt_required
def resume():
    """
    User's resume list

    .. :quickref: protected; Retrieve user's resume list directly from provider

    **Request**:

        .. sourcecode:: http

            GET /refresh HTTP/1.1
            Authorization: JWT q1w2.e3r4.t5y

    **Response**:

        .. sourcecode:: http

            HTTP/1.1 200 OK
            Content-Type: application/json

            [
                {
                    "enabled": true,
                    "link": "https://<provider's resume page>",
                    "name": "John Doe",
                    "published": "2018-08-19T17:41:52+0300",
                    "title": "Proctologist-jeweler",
                    "uniq": "erwhy2333r23rd2r32er23"
                }
            ]

    :reqheader Authorization: valid JWT token

    :statuscode 200: OK
    :statuscode 401: auth errors
    :statuscode 500: unexpected errors
    :statuscode 503: provider errors
    """
    result = {}
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)

        for account in user.accounts:
            provider = current_app.providers[account.provider]
            resumes = provider.fetch(account.access)

            for item in resumes:
                resume = Resume.query.filter_by(identity=item['uniq']).first()

                if not resume:
                    resume = Resume(
                        identity=item['uniq'], enabled=False,
                        name=item['title'], owner=user, account=account)
                    current_app.logger.info(f'Resume created: {resume}')

                resume.name = item['title']
                resume.owner = user
                db.session.add(resume)

                item['enabled'] = resume.enabled

            if resumes:
                if provider.name not in result:
                    result[provider.name] = []
                result[provider.name].extend(resumes)

        db.session.commit()

    except ProviderError as e:
        current_app.logger.error(f'Resume error: {e}')
        return abort(503, 'Provider error')

    except SQLAlchemyError as e:
        current_app.logger.error(f'{type(e).__name__}: {e}', exc_info=1)
        return abort(500, 'Database error')

    else:
        struct = [dict(provider=k, resume=v) for k, v in result.items()]
        return jsonify(struct)


@module.route('/resume', methods=['POST'])
@jwt_required
@validation_required({'uniq': {'type': 'string', 'required': True}})
def resume_toggle():
    """
    Enable/disable automatically publish user's resume

    .. :quickref: protected; Toggle automatically publish user's resume

    **Request**:

        .. sourcecode:: http

            POST /resume HTTP/1.1
            Content-Type: application/json

            {
                "uniq": "q1w2e3r4t5y6"
            }

    **Response**:

        .. sourcecode:: http

            HTTP/1.1 200 OK
            Content-Type: application/json

            {
                "enabled": true
            }

    :reqjson string uniq: provider's resume id

    :statuscode 200: OK
    :statuscode 400: invalid JSON in request's body
    :statuscode 401: auth errors
    :statuscode 500: unexpected errors
    """
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        uniq = request.get_json()['uniq']
        resume = Resume.query.filter_by(identity=uniq, owner=user).first()

        if not resume:
            return abort(404, 'Resume not found')

        resume.toggle()

    except SQLAlchemyError as e:
        current_app.logger.error(f'{type(e).__name__}: {e}', exc_info=1)
        return abort(500, 'Database error')

    else:
        current_app.logger.info(f'Resume toggled: {resume}')
        return jsonify(enabled=resume.enabled)
