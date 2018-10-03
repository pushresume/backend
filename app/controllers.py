from random import randint
from datetime import datetime, timedelta

from flask import current_app

from . import db, __version__
from .models import User, Resume, OTP, Subscription, Notification


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

    @staticmethod
    def fetch(user_id):
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

    @staticmethod
    def toggle(user_id, uniq):
        user = User.query.get(user_id)
        resume = Resume.query.filter_by(uniq=uniq, owner=user).first()
        if resume:
            resume.enabled = not resume.enabled
            db.session.add(resume)
            db.session.commit()

        return resume


class StatsController(object):
    """Statistics Controller"""

    @staticmethod
    def stats():
        users = User.query.count()
        resume = Resume.query.count()
        otp = OTP.query.count()
        subscriptions = Subscription.query.count()
        notifications = Notification.query.count()
        redis = current_app.redis.info('memory')

        rows = users + resume + otp + subscriptions + notifications

        result = {
            'providers': [],
            'health': {
                'db': {'current': rows, 'max': 10000},
                'cache': {'current': redis['used_memory'], 'max': 25000000}
            },
            'version': __version__
        }

        ResumeUser = Resume.query.join(User)
        for prov in current_app.providers.keys():
            provider = {
                'name': prov,
                'users': User.query.filter_by(provider=prov).count(),
                'resume': ResumeUser.filter(User.provider == prov).count()
            }
            result['providers'].append(provider)

        return result


class OTPController(object):
    """OTP Controller"""

    @classmethod
    def create(cls, user_id, channel):
        user = User.query.get(user_id)

        if user.is_has_otp:
            if not user.otp.is_expired:
                return user.otp

            db.session.delete(user.otp)
            db.session.commit()

        code = cls.generate(length=current_app.config['OTP_LENGTH'])
        ttl = timedelta(seconds=current_app.config['OTP_TTL'])
        timestamp = datetime.utcnow() + ttl

        otp = OTP(code=code, expires=timestamp, channel=channel, owner=user)
        db.session.add(otp)
        db.session.commit()

        return otp

    @staticmethod
    def validate(code, channel):
        otp = OTP.query.filter_by(code=code).first()

        if not otp:
            current_app.logger.info(f'OTP code not found: {code}')
            return False

        if otp.is_expired:
            current_app.logger.info(f'OTP code is expired: {otp}')
            return False

        user = otp.owner
        sub = Subscription.query.filter_by(channel=channel, owner=user).first()
        if sub:
            current_app.logger.warning(f'Subscription already exists: {sub}')
            return False

        return otp.owner.id

    @staticmethod
    def generate(length=8):
        return randint(10**(length-1), (10**length)-1)


class SubscriptionController(object):
    """Subscription Controller"""

    @staticmethod
    def create(user_id, address, channel):
        user = User.query.get(user_id)

        sub = Subscription(address=address, channel=channel, owner=user)

        db.session.add(sub)
        db.session.commit()

        current_app.logger.info(f'Subscription created: {sub}')

        return sub

    @staticmethod
    def fetch(user_id, channel=None):
        user = User.query.get(user_id)

        query = Subscription.query.filter_by(owner=user)
        if channel:
            query = query.filter_by(channel=channel)

        sub = query.all()

        return [dict(channel=s.channel, enabled=s.enabled) for s in sub]

    @staticmethod
    def toggle(user_id, channel):
        user = User.query.get(user_id)

        sub = Subscription.query.filter_by(owner=user, channel=channel).first()
        if sub:
            sub.enabled = not sub.enabled
            db.session.add(sub)
            db.session.commit()

        return sub
