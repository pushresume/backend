from datetime import datetime, timedelta

from tests import AppBase

from app import db
from app.models import (
    User, Account, Resume, Confirmation, Subscription, Notification)


class UserTest(AppBase):

    def test_models_user_default_identity(self):
        user = User()
        db.session.add(user)
        db.session.commit()

        self.assertIsNotNone(user.identity)

    def test_models_user_repl(self):
        user = User(identity='fake_user')

        self.assertIn('fake_user', str(user))


class AccountTest(AppBase):

    @staticmethod
    def create_account(user=None, timestamp=None):
        if not user:
            user = User(identity='fake_user')

        if not timestamp:
            timestamp = datetime.utcnow()

        return Account(
            identity='fake_account', access='12345', refresh='qwerty',
            expires=timestamp, provider='fake_provider', owner=user)

    def test_models_account_is_expired(self):
        past = datetime.utcnow() - timedelta(days=1)
        account = self.create_account(timestamp=past)

        self.assertTrue(account.is_expired)

        future = datetime.utcnow() + timedelta(days=1)
        account = self.create_account(timestamp=future)

        self.assertFalse(account.is_expired)

    def test_models_account_repl(self):
        account = self.create_account()

        self.assertIn('fake_account', str(account))
        self.assertIn('fake_provider', str(account))
        self.assertIn('fake_user', str(account))


class ResumeTest(AppBase):

    @staticmethod
    def create_resume(user=None, account=None):
        if not user:
            user = User(identity='fake_user')

        if not account:
            exp = datetime.utcnow() + timedelta(days=1)
            account = AccountTest.create_account(user, timestamp=exp)

        return Resume(
            identity='fake_resume', enabled=False,
            name='faker', account=account, owner=user)

    def test_models_resume_toggle(self):
        resume = self.create_resume()

        self.assertFalse(resume.is_enabled)

        resume.toggle()

        self.assertTrue(resume.is_enabled)

    def test_models_resume_repl(self):
        resume = self.create_resume()

        self.assertIn('fake_resume', str(resume))
        self.assertIn('fake_provider', str(resume))
        self.assertIn('fake_user', str(resume))


class ConfirmationTest(AppBase):

    @staticmethod
    def create_confirmation(user=None, timestamp=None):
        if not user:
            user = User(identity='fake_user')

        if not timestamp:
            timestamp = datetime.utcnow()

        return Confirmation(
            code='fake_code', channel='fake_channel',
            expires=timestamp, owner=user)

    def test_models_confirmation_is_expired(self):
        past = datetime.utcnow() - timedelta(days=1)
        confirmation = self.create_confirmation(timestamp=past)

        self.assertTrue(confirmation.is_expired)

        future = datetime.utcnow() + timedelta(days=1)
        confirmation = self.create_confirmation(timestamp=future)

        self.assertFalse(confirmation.is_expired)

    def test_models_confirmation_seconds_left(self):
        past = datetime.utcnow() - timedelta(seconds=10)
        confirmation = self.create_confirmation(timestamp=past)

        self.assertEqual(confirmation.seconds_left, 0)

        future = datetime.utcnow() + timedelta(seconds=10)
        confirmation = self.create_confirmation(timestamp=future)

        self.assertGreater(confirmation.seconds_left, 0)

    def test_models_confirmation_repl(self):
        confirmation = self.create_confirmation()

        self.assertIn('fake_code', str(confirmation))
        self.assertIn('fake_channel', str(confirmation))
        self.assertIn('fake_user', str(confirmation))


class SubscriptionTest(AppBase):

    @staticmethod
    def create_subscription(user=None):
        if not user:
            user = User(identity='fake_user')

        return Subscription(
            address='fake_address', channel='fake_channel', owner=user)

    def test_models_subscription_is_enabled(self):
        subscription = self.create_subscription()

        self.assertFalse(subscription.is_enabled)

        subscription.enabled = True

        self.assertTrue(subscription.is_enabled)

    def test_models_subscription_is_confirmed(self):
        subscription = self.create_subscription()

        self.assertFalse(subscription.is_confirmed)

        subscription.confirmed = True

        self.assertTrue(subscription.is_confirmed)

    def test_models_subscription_repl(self):
        subscription = self.create_subscription()

        self.assertIn('fake_address', str(subscription))
        self.assertIn('fake_channel', str(subscription))
        self.assertIn('fake_user', str(subscription))


class NotificationTest(AppBase):

    @staticmethod
    def create_notification(user=None, timestamp=None):
        if not user:
            user = User(identity='fake_user')

        if not timestamp:
            timestamp = datetime.utcnow()

        return Notification(
            message='fake_message', channel='fake_channel',
            expires=timestamp, owner=user)

    def test_models_notification_create(self):
        user = User(identity='fake_user')
        db.session.add(user)

        subscription = SubscriptionTest.create_subscription(user)
        subscription.enabled = True
        db.session.add(subscription)

        db.session.commit()

        self.assertIs(len(user.notifications), 0)

        Notification.create(user, 'fake_message', 5)

        self.assertTrue(user.notifications)
        self.assertEqual(user.notifications[0].message, 'fake_message')

    def test_models_notification_is_expired(self):
        past = datetime.utcnow() - timedelta(days=1)
        notification = self.create_notification(timestamp=past)

        self.assertTrue(notification.is_expired)

        future = datetime.utcnow() + timedelta(days=1)
        notification = self.create_notification(timestamp=future)

        self.assertFalse(notification.is_expired)

    def test_models_notification_is_sended(self):
        notification = self.create_notification()

        self.assertFalse(notification.is_sended)

        notification.sended = True

        self.assertTrue(notification.is_sended)

    def test_models_notification_repl(self):
        notification = self.create_notification()

        self.assertIn('fake_message', str(notification))
        self.assertIn('fake_channel', str(notification))
        self.assertIn('fake_user', str(notification))
