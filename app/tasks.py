from time import sleep
from datetime import datetime, timedelta

from celery import Celery
from celery.utils.log import get_task_logger

from . import create_app, db
from .utils import load_sentry, load_scout_apm
from .providers import PushError, TokenError
from .models import (
    User, Account, Resume, Confirmation, Subscription, Notification)


current_app = create_app()  # not app!
current_app.app_context().push()

celery = Celery(
    'pushresume',
    broker=current_app.config['REDIS_URL'],
    broker_pool_limit=0,  # current_app.config['REDIS_MAX_CONNECTIONS'],
    redis_max_connections=current_app.config['REDIS_MAX_CONNECTIONS'])
logger = get_task_logger(__name__)

if current_app.config['SENTRY_DSN']:
    load_sentry(current_app, celery=True)

if current_app.config['SCOUT_KEY']:
    load_scout_apm(current_app, db, celery=True)

default_result = {'total': 0, 'success': 0, 'failed': 0}


@celery.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    cleanup_period = current_app.config['PERIOD_CLEANUP']
    sender.add_periodic_task(cleanup_period, cleanup_users.s())
    sender.add_periodic_task(cleanup_period, cleanup_resume.s())
    sender.add_periodic_task(cleanup_period, cleanup_accounts.s())
    sender.add_periodic_task(cleanup_period, cleanup_confirmations.s())
    sender.add_periodic_task(cleanup_period, cleanup_subscriptions.s())
    sender.add_periodic_task(cleanup_period, cleanup_notifications.s())
    sender.add_periodic_task(
        current_app.config['PERIOD_REAUTH'], refresh_accounts.s())
    sender.add_periodic_task(
        current_app.config['PERIOD_PUSH'], push_resume.s())
    sender.add_periodic_task(
        current_app.config['PERIOD_NOTIFICATIONS'], notify_by_telegram.s())


@celery.task
def cleanup_users():
    result = default_result.copy()
    users = User.query.all()
    for user in users:
        if not user.accounts and not user.resume:
            try:
                logger.warning(f'Cleanup user: {user}')
                db.session.delete(user)
                db.session.commit()
            except Exception as e:
                result['failed'] += 1
                logger.error(
                    f'Cleanup user failed: {user}, err={e}', exc_info=1)
            else:
                result['success'] += 1
            finally:
                result['total'] += 1

    return result


@celery.task
def cleanup_accounts():
    result = default_result.copy()
    accounts = Account.query.all()
    for account in accounts:
        deep_expires = account.expires + timedelta(days=30)
        deep_ttl_expired = datetime.utcnow() > deep_expires
        if account.is_expired and deep_ttl_expired:
            try:
                logger.warning(f'Cleanup account: {account}')
                db.session.delete(account)
                db.session.commit()
            except Exception as e:
                result['failed'] += 1
                logger.error(
                    f'Cleanup account failed: {account}, err={e}', exc_info=1)
            else:
                result['success'] += 1
            finally:
                result['total'] += 1

    return result


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
def refresh_accounts():
    result = default_result.copy()
    accounts = Account.query.all()
    for account in accounts:
        try:
            provider = current_app.providers[account.provider]
            ids = provider.tokenize(account.refresh, refresh=True)

            account.access = ids['access_token']
            account.refresh = ids['refresh_token']

            delta = timedelta(seconds=ids['expires_in'])
            account.expires = datetime.utcnow() + delta

            db.session.add(account)
            db.session.commit()
        except TokenError as e:
            result['failed'] += 1
            logger.warning(f'Reauth failed: {account}, status={e}')
        except Exception as e:
            result['failed'] += 1
            logger.exception(
                f'Reauth failed: {account}, err={e}', exc_info=1)
        else:
            result['success'] += 1
            logger.info(f'Reauth success: {account}')
            Notification.create(
                user=account.owner,
                msg=f'Токен для {account.provider} успешно обновлён',
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
            account = resume.account
            provider = current_app.providers[account.provider]
            provider.push(token=account.access, resume=resume.identity)
        except PushError as e:
            result['failed'] += 1
            logger.warning(f'Push failed: {resume}, status={e}')
            if str(e).startswith(('400', '403')):
                resume.toggle()
        except Exception as e:
            result['failed'] += 1
            logger.exception(f'Push failed: {resume}, err={e}', exc_info=1)
        else:
            result['success'] += 1
            logger.info(f'Push success: {resume}')
            Notification.create(
                user=resume.owner,
                msg=f'Резюме «{resume.name}» успешно обновлено',
                ttl=current_app.config['NOTIFICATIONS_TTL'])
        finally:
            result['total'] += 1

    return result


@celery.task
def notify_by_telegram():
    result = default_result.copy()
    result['expired'] = 0
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
                    result['expired'] += 1
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
