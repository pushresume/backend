from flask import Flask

from tests import AppBase

from app import create_app


class AppTest(AppBase):

    def setUp(self):
        app = create_app()
        super().setUp(app)

    def test_create_app(self):
        self.assertIsInstance(self.app, Flask)
