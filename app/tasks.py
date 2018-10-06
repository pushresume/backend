from time import sleep
from datetime import datetime, timedelta

import sentry_sdk
from celery.utils.log import get_task_logger
from sentry_sdk.integrations.celery import CeleryIntegration

from . import create_app, db
from .providers import PushError, TokenError
from .models import (
    User, Credential, Resume, Confirmation, Subscription, Notification)


current_app = create_app()  # not app!
current_app.app_context().push()

celery = current_app.queue
logger = get_task_logger(__name__)
default_result = {'total': 0, 'success': 0, 'failed': 0}

sentry_sdk.init(
    dsn=current_app.config['SENTRY_DSN'],
    environment='development' if current_app.debug else 'production',
    integrations=[CeleryIntegration()])


@celery.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    cleanup_period = current_app.config['CLEANUP_PERIOD']
    sender.add_periodic_task(cleanup_period, cleanup_resume.s())
    sender.add_periodic_task(cleanup_period, cleanup_confirmations.s())
    sender.add_periodic_task(cleanup_period, cleanup_subscriptions.s())
    sender.add_periodic_task(cleanup_period, cleanup_notifications.s())
    sender.add_periodic_task(
        current_app.config['REAUTH_PERIOD'], refresh_credentials.s())
    sender.add_periodic_task(
        current_app.config['PUSH_PERIOD'], push_resume.s())
    sender.add_periodic_task(
        current_app.config['NOTIFICATIONS_PERIOD'], notify_by_telegram.s())


@celery.task
def cleanup_resume():
    result = default_result.copy()
    resumes = Resume.query.filter_by(enabled=False).all()
    for resume in resumes:
        try:
            logger.warning(f'Cleanup resume: {resume}')
            db.session.delete(resume)
            db.session.commit()
        except Exception as e:
            result['failed'] += 1
            logger.error(
                f'Cleanup resume failed: {resume}, err={e}', exc_info=1)
        else:
            result['success'] += 1
        finally:
            result['total'] += 1

    return result


@celery.task
def cleanup_confirmations():
    result = default_result.copy()
    confirmations = Confirmation.query.all()
    for confirm in confirmations:
        if confirm.is_expired:
            try:
                logger.warning(f'Cleanup confirmation: {confirm}')
                db.session.delete(confirm)
                db.session.commit()
            except Exception as e:
                result['failed'] += 1
                logger.error(
                    f'Cleanup confirmation failed: {confirm}, err={e}',
                    exc_info=1)
            else:
                result['success'] += 1
            finally:
                result['total'] += 1

    return result


@celery.task
def cleanup_subscriptions():
    result = default_result.copy()
    subscriptions = Subscription.query.filter_by(enabled=False).all()
    for sub in subscriptions:
        try:
            logger.warning(f'Cleanup subscription: {sub}')
            db.session.delete(sub)
            db.session.commit()
        except Exception as e:
            result['failed'] += 1
            logger.error(
                f'Cleanup subscription failed: {sub}, err={e}', exc_info=1)
        else:
            result['success'] += 1
        finally:
            result['total'] += 1

    return result


@celery.task
def cleanup_notifications():
    result = default_result.copy()
    notifications = Notification.query.all()
    for notice in notifications:
        if notice.is_expired or notice.is_sended:
            try:
                logger.warning(f'Cleanup notification: {notice}')
                db.session.delete(notice)
                db.session.commit()
            except Exception as e:
                result['failed'] += 1
                logger.error(
                    f'Cleanup notification failed: {notice}, {e}', exc_info=1)
            else:
                result['success'] += 1
            finally:
                result['total'] += 1

    return result


@celery.task
def refresh_credentials():
    result = default_result.copy()
    credentials = Credential.query.all()
    for credential in credentials:
        try:
            provider = current_app.providers[credential.provider]
            ids = provider.tokenize(credential.refresh, refresh=True)

            credential.access = ids['access_token']
            credential.refresh = ids['refresh_token']

            delta = timedelta(seconds=ids['expires_in'])
            credential.expires = datetime.utcnow() + delta

            db.session.add(credential)
            db.session.commit()
        except TokenError as e:
            result['failed'] += 1
            logger.warning(f'Reauth failed: {credential}, status={e}')
        except Exception as e:
            result['failed'] += 1
            logger.exception(
                f'Reauth failed: {credential}, err={e}', exc_info=1)
        else:
            result['success'] += 1
            logger.info(f'Reauth success: {credential}')
            Notification.create(
                user=credential.owner, msg='Token refresh success',
                ttl=current_app.config['NOTIFICATIONS_TTL'])
        finally:
            result['total'] += 1

    return result


@celery.task
def push_resume():
    result = default_result.copy()
    resumes = Resume.query.filter_by(enabled=True).all()
    for resume in resumes:
        try:
            provider = current_app.providers[resume.owner.provider]
            provider.push(token=resume.owner.access, resume=resume.uniq)
        except PushError as e:
            result['failed'] += 1
            logger.warning(f'Push failed: {resume}, status={e}')
        except Exception as e:
            result['failed'] += 1
            logger.exception(f'Push failed: {resume}, err={e}', exc_info=1)
        else:
            result['success'] += 1
            logger.info(f'Push success: {resume}')
            Notification.create(
                user=resume.owner, msg=f'Resume "{resume.name}" push success',
                ttl=current_app.config['NOTIFICATIONS_TTL'])
        finally:
            result['total'] += 1

    return result


@celery.task
def notify_by_telegram():
    result = default_result.copy()
    channel = 'telegram'

    users = User.query.all()
    for user in users:
        sub = Subscription.query.filter_by(owner=user, channel=channel).first()
        if sub:
            notices = Notification.query.filter_by(
                owner=user, channel=channel, sended=False).all()
            for notice in notices:
                if notice.is_expired:
                    logger.warning(f'Notification expired: {notice}')
                    continue
                try:
                    current_app.bot.send_message(sub.address, notice.message)
                    notice.sended = True
                    db.session.add(notice)
                except Exception as e:
                    result['failed'] += 1
                    logger.exception(
                        f'Notification send failed: {notice}, {e}', exc_info=1)
                else:
                    result['success'] += 1
                    logger.info(f'Notification send success: {notice}')
                finally:
                    result['total'] += 1
                    sleep(1)

            db.session.commit()

    return result
