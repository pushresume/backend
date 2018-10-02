from datetime import datetime

from . import db


class User(db.Model):

    __tablename__ = 'users'
    __table_args__ = (db.Index('uniq', 'uniq', 'provider', unique=True),)

    id = db.Column(db.Integer, primary_key=True)
    uniq = db.Column(db.String(120), nullable=False)
    provider = db.Column(db.String(120), nullable=False)
    access = db.Column(db.String(200), nullable=False)
    refresh = db.Column(db.String(200), nullable=False)
    expires = db.Column(db.DateTime, nullable=False)
    updated = db.Column(db.DateTime, default=datetime.utcnow)

    resume = db.relationship(
        'Resume', foreign_keys='Resume.user_id', backref='owner')

    otp = db.relationship(
        'OTP', foreign_keys='OTP.user_id', backref='owner', uselist=False)

    subscription = db.relationship(
        'Subscription', foreign_keys='Subscription.user_id', backref='owner')

    @property
    def is_has_otp(self):
        return self.otp is not None

    def __str__(self):
        return f'{self.uniq}, provider={self.provider}'


class Resume(db.Model):

    __tablename__ = 'resume'

    id = db.Column(db.Integer, primary_key=True)
    uniq = db.Column(db.String(120), unique=True, nullable=False)
    enabled = db.Column(db.Boolean, default=False, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    def __str__(self):
        return f'{self.uniq}, enabled={self.enabled}, user={self.owner}'


class OTP(db.Model):

    __tablename__ = 'otp'

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(24), unique=True, nullable=False)
    expires = db.Column(db.DateTime, nullable=False)
    user_id = db.Column(
        db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)

    @property
    def is_expired(self):
        return datetime.utcnow() > self.expires

    def __str__(self):
        return f'{self.code}, expires={self.expires}, user={self.owner}'


class Subscription(db.Model):

    __tablename__ = 'subscriptions'

    id = db.Column(db.Integer, primary_key=True)
    address = db.Column(db.String(120), unique=True, nullable=False)
    channel = db.Column(db.String(120), unique=False, nullable=False)
    enabled = db.Column(db.Boolean, default=False, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    def __str__(self):
        return f'{self.address}, channel={self.channel}, user={self.owner}'
