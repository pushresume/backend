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
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)

        provider = current_app.providers[user.provider]
        resumes = provider.fetch(user.access)

        for i in resumes:
            resume = Resume.query.filter_by(uniq=i['uniq'], owner=user).first()
            if not resume:
                resume = Resume(uniq=i['uniq'], enabled=False, owner=user)
                current_app.logger.info(f'Resume created: {resume}')
                db.session.add(resume)

            i['enabled'] = resume.enabled

        db.session.commit()

    except ProviderError as e:
        current_app.logger.error(f'Resume error: {e}')
        return abort(503, 'Provider error')

    except SQLAlchemyError as e:
        current_app.logger.error(f'{type(e).__name__}: {e}', exc_info=1)
        return abort(500, 'Database error')

    else:
        return jsonify(resumes)


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
        resume = Resume.query.filter_by(uniq=uniq, owner=user).first()

        if not resume:
            return abort(404, 'Resume not found')

        resume.enabled = not resume.enabled

        db.session.add(resume)
        db.session.commit()

    except SQLAlchemyError as e:
        current_app.logger.error(f'{type(e).__name__}: {e}', exc_info=1)
        return abort(500, 'Database error')

    else:
        current_app.logger.info(f'Resume toggled: {resume}')
        return jsonify(enabled=resume.enabled)
