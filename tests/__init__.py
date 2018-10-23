import unittest

from flask import Flask

from app import db


class AppBase(unittest.TestCase):

    def setUp(self, app=None, config=None):
        if not app:
            app = Flask(__name__)

        if not config:
            import config
            config.SQLALCHEMY_DATABASE_URI = 'sqlite://'

        app.config.from_object(config)

        self.app = app
        self.app_context = self.app.app_context()
        self.app_context.push()

        db.init_app(self.app)
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()
