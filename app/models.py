from uuid import uuid4
from datetime import datetime, timedelta

from sqlalchemy.orm import backref

from . import db


class User(db.Model):

    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    identity = db.Column(
        db.String(36), unique=True, default=lambda: f'{uuid4()}')

    def __str__(self):
        return self.identity


class Account(db.Model):

    __tablename__ = 'accounts'

    id = db.Column(db.Integer, primary_key=True)
    identity = db.Column(db.String(120), unique=True, nullable=False)
    access = db.Column(db.String(200), nullable=False)
    refresh = db.Column(db.String(200), nullable=False)
    expires = db.Column(db.DateTime, nullable=False)
    provider = db.Column(db.String(120), nullable=False)

    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    owner = db.relationship('User', backref='accounts')

    @property
    def is_expired(self):
        return datetime.utcnow() > self.expires

    def __str__(self):
        return f'{self.identity}, provider={self.provider}, user={self.owner}'


class Resume(db.Model):

    __tablename__ = 'resume'

    id = db.Column(db.Integer, primary_key=True)
    identity = db.Column(db.String(120), unique=True, nullable=False)
    enabled = db.Column(db.Boolean, default=False, nullable=False)
    name = db.Column(db.String(120), nullable=False)

    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    account_id = db.Column(
        db.Integer, db.ForeignKey('accounts.id'), nullable=False)

    owner = db.relationship('User', backref='resume')
    account = db.relationship('Account', backref='resume', uselist=False)

    def toggle(self):
        self.enabled = not self.enabled
        db.session.add(self)
        db.session.commit()

    @property
    def is_enabled(self):
        return self.enabled

    def __str__(self):
        return f'{self.identity}, enabled={self.enabled},\
            provider={self.account.provider}, user={self.owner}'


class Confirmation(db.Model):

    __tablename__ = 'confirmations'
    __table_args__ = (
        db.Index(f'uniq_{__tablename__}', 'user_id', 'channel', unique=True),)

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(24), unique=True, nullable=False)
    expires = db.Column(db.DateTime, nullable=False)
    channel = db.Column(db.String(120), unique=False, nullable=False)

    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    owner = db.relationship(
        'User', backref=backref('confirmations', cascade='all,delete'))

    @property
    def is_expired(self):
        return datetime.utcnow() > self.expires

    @property
    def seconds_left(self):
        if self.expires < datetime.utcnow():
            return 0
        return (self.expires - datetime.utcnow()).seconds

    def __str__(self):
        return f'{self.code}, expires={self.expires}, user={self.owner}'


class Subscription(db.Model):

    __tablename__ = 'subscriptions'
    __table_args__ = (
        db.Index(f'uniq_{__tablename__}', 'user_id', 'channel', unique=True),)

    id = db.Column(db.Integer, primary_key=True)
    address = db.Column(db.String(120), unique=False, nullable=False)
    channel = db.Column(db.String(120), unique=False, nullable=False)
    confirmed = db.Column(db.Boolean, default=False, nullable=False)
    enabled = db.Column(db.Boolean, default=False, nullable=False)

    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    owner = db.relationship(
        'User', backref=backref('subscriptions', cascade='all,delete'))

    @property
    def is_enabled(self):
        return self.enabled

    @property
    def is_confirmed(self):
        return self.confirmed

    def __str__(self):
        return f'{self.address}, channel={self.channel},\
            enabled={self.enabled}, user={self.owner}'


class Notification(db.Model):

    __tablename__ = 'notifications'

    id = db.Column(db.Integer, primary_key=True)
    message = db.Column(db.Text, unique=False, nullable=False)
    channel = db.Column(db.String(120), unique=False, nullable=False)
    expires = db.Column(db.DateTime, nullable=False)
    sended = db.Column(db.Boolean, default=False, nullable=False)

    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    owner = db.relationship(
        'User', backref=backref('notifications', cascade='all,delete'))

    @classmethod
    def create(cls, user, msg, ttl):
        timestamp = datetime.utcnow() + timedelta(seconds=ttl)

        for sub in user.subscriptions:
            if sub.is_enabled:
                notification = cls(
                    message=msg, channel=sub.channel,
                    expires=timestamp, owner=user)

                db.session.add(notification)

        db.session.commit()

    @property
    def is_expired(self):
        return datetime.utcnow() > self.expires

    @property
    def is_sended(self):
        return self.sended

    def __str__(self):
        return f'{self.message}, channel={self.channel},\
            expires={self.expires}, user={self.owner}'
