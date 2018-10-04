from time import sleep

from celery.utils.log import get_task_logger

from . import create_app, db
from .models import User, Resume, OTP, Subscription, Notification
from .controllers import (
    UserController, SubscriptionController, NotificationController)
from .providers import PushError, TokenError


current_app = create_app()  # not app!
current_app.app_context().push()

celery = current_app.queue
logger = get_task_logger(__name__)
default_result = {'total': 0, 'success': 0, 'failed': 0}


@celery.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    cleanup_period = current_app.config['CLEANUP_PERIOD']
    sender.add_periodic_task(cleanup_period, cleanup_resume.s())
    sender.add_periodic_task(cleanup_period, cleanup_otp_codes.s())
    sender.add_periodic_task(cleanup_period, cleanup_subscriptions.s())
    sender.add_periodic_task(cleanup_period, cleanup_notifications.s())
    sender.add_periodic_task(
        current_app.config['REAUTH_PERIOD'], reauth_users.s())
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
def cleanup_otp_codes():
    result = default_result.copy()
    otp = OTP.query.all()
    for code in otp:
        if code.is_expired:
            try:
                logger.warning(f'Cleanup OTP: {code}')
                db.session.delete(otp)
                db.session.commit()
            except Exception as e:
                result['failed'] += 1
                logger.error(f'Cleanup OTP failed: {otp}, err={e}', exc_info=1)
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
        if notice.is_expired:
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
def reauth_users():
    result = default_result.copy()
    users = User.query.all()
    for user in users:
        try:
            provider = current_app.providers[user.provider]
            user_controller = UserController(provider)
            user = user_controller.auth(code=user.refresh, refresh=True)
        except TokenError as e:
            result['failed'] += 1
            logger.warning(f'Reauth failed: {user}, status={e}')
        except Exception as e:
            result['failed'] += 1
            logger.exception(f'Reauth failed: {user}, err={e}', exc_info=1)
        else:
            result['success'] += 1
            logger.info(f'Reauth success: {user}')
            NotificationController.create(user, 'Token refresh success')
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
            NotificationController.create(
                resume.owner, f'Resume "{resume.name}" push success')
        finally:
            result['total'] += 1

    return result


@celery.task
def notify_by_telegram():
    result = default_result.copy()
    channel = 'telegram'

    users = User.query.all()
    for user in users:
        subscription = SubscriptionController.fetch(user.id, channel)
        if subscription:
            notices = NotificationController.fetch(user.id, channel)
            for notice in notices:
                try:
                    NotificationController.send_telegram(
                        subscription.address, notice)
                    sleep(1)
                except Exception as e:
                    result['failed'] += 1
                    logger.exception(
                        f'Notification send failed: {notice}, {e}', exc_info=1)
                else:
                    result['success'] += 1
                    logger.info(f'Notification send success: {notice}')
                finally:
                    result['total'] += 1
        else:
            logger.warning(f'User {user} no have {channel} subscription')

    return result
