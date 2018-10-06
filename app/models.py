from datetime import datetime, timedelta

from . import db


class User(db.Model):

    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    identity = db.Column(db.String(120), unique=True, nullable=False)

    credentials = db.relationship(
        'Credential', foreign_keys='Credential.user_id', backref='owner')

    resume = db.relationship(
        'Resume', foreign_keys='Resume.user_id', backref='owner')

    confirmations = db.relationship(
        'Confirmation', foreign_keys='Confirmation.user_id', backref='owner')

    subscriptions = db.relationship(
        'Subscription', foreign_keys='Subscription.user_id', backref='owner')

    notifications = db.relationship(
        'Notification', foreign_keys='Notification.user_id', backref='owner')

    def __str__(self):
        return self.identity


class Credential(db.Model):

    __tablename__ = 'credentials'
    __table_args__ = (
        db.Index(f'uniq_{__tablename__}', 'user_id', 'provider', unique=True),)

    id = db.Column(db.Integer, primary_key=True)
    provider = db.Column(db.String(120), nullable=False)
    access = db.Column(db.String(200), nullable=False)
    refresh = db.Column(db.String(200), nullable=False)
    expires = db.Column(db.DateTime, nullable=False)

    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    @property
    def is_expired(self):
        return datetime.utcnow() > self.expires

    def __str__(self):
        return f'{self.owner.identity}, provider={self.provider}'


class Resume(db.Model):

    __tablename__ = 'resume'

    id = db.Column(db.Integer, primary_key=True)
    identity = db.Column(db.String(120), unique=True, nullable=False)
    enabled = db.Column(db.Boolean, default=False, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    provider = db.Column(db.String(120), nullable=False)

    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    @property
    def is_enabled(self):
        return self.enabled

    def __str__(self):
        return f'{self.identity}, enabled={self.enabled}, user={self.owner}'


class Confirmation(db.Model):

    __tablename__ = 'confirmations'
    __table_args__ = (
        db.Index(f'uniq_{__tablename__}', 'user_id', 'channel', unique=True),)

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(24), unique=True, nullable=False)
    expires = db.Column(db.DateTime, nullable=False)
    channel = db.Column(db.String(120), unique=False, nullable=False)

    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

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

    @property
    def is_enabled(self):
        return self.enabled

    @property
    def is_confirmed(self):
        return self.confirmed

    def __str__(self):
        return '{0}, channel={1}, enabled={2}, user={3}'.format(
            self.address, self.channel, self.enabled, self.owner)


class Notification(db.Model):

    __tablename__ = 'notifications'

    id = db.Column(db.Integer, primary_key=True)
    message = db.Column(db.Text, unique=False, nullable=False)
    channel = db.Column(db.String(120), unique=False, nullable=False)
    expires = db.Column(db.DateTime, nullable=False)
    sended = db.Column(db.Boolean, default=False, nullable=False)

    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

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
        return '{0}, channel={1}, expires={2}, user={3}'.format(
            self.message, self.channel, self.expires, self.owner)
