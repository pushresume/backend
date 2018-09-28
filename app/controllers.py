from datetime import datetime, timedelta

from flask import current_app

from . import db
from .models import User, Resume


class UserController(object):
    """User Controller"""

    def __init__(self, provider):
        self._provider = provider

    def auth(self, code, refresh=False):
        ids = self._provider.tokenize(code, refresh=refresh)
        identity = self._provider.identity(ids['access_token'])

        user = User.query.filter_by(
            uniq=identity, provider=self._provider.name).first()
        if not user:
            user = User(uniq=identity, provider=self._provider.name)

        user.access = ids['access_token']
        user.refresh = ids['refresh_token']
        user.expires = datetime.utcnow() + timedelta(seconds=ids['expires_in'])

        db.session.add(user)
        db.session.commit()
        return user


class ResumeController(object):
    """Resume Controller"""

    @classmethod
    def fetch(self, user_id):
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
        return resumes

    @classmethod
    def toggle(self, user_id, uniq):
        user = User.query.get(user_id)
        resume = Resume.query.filter_by(uniq=uniq, owner=user).first()
        if resume:
            resume.enabled = not resume.enabled
            db.session.add(resume)
            db.session.commit()

        return resume


class StatsController(object):
    """Statistics Controller"""

    @classmethod
    def stats(self):
        users = User.query.count()
        resume = Resume.query.count()
        redis = current_app.redis.info('memory')

        result = {
            'db': {
                'rows': {'total': users + resume, 'max': 10000},
                'memory': {'total': redis['used_memory'], 'max': 25000000}
            },
            'users': {'items': [], 'total': users},
            'resume': {'items': [], 'total': resume}
        }

        ResumeUser = Resume.query.join(User)
        for prov in current_app.providers.keys():
            result['users']['items'].append(
                {prov: User.query.filter_by(provider=prov).count()})
            result['resume']['items'].append(
                {prov: ResumeUser.filter(User.provider == prov).count()})

        return result
