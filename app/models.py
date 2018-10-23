from uuid import uuid4
from datetime import datetime

from . import db


class User(db.Model):

    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    identity = db.Column(
        db.String(36), unique=True, default=lambda: f'{uuid4()}')

    def __str__(self):
        return self.identity


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
        return (
            f'{self.identity}, enabled={self.enabled}, '
            f'provider={self.account.provider}, user={self.owner}')


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
