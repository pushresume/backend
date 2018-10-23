from datetime import datetime, timedelta

from celery.utils.log import get_task_logger

from . import create_app, db
from .models import User, Resume
from .providers import PushError, TokenError


current_app = create_app()  # not app!
current_app.app_context().push()

celery = current_app.queue
logger = get_task_logger(__name__)
default_result = {'total': 0, 'success': 0, 'failed': 0}


@celery.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    sender.add_periodic_task(current_app.config['CLEANUP_PERIOD'], cleanup.s())
    sender.add_periodic_task(current_app.config['REAUTH_PERIOD'], reauth.s())
    sender.add_periodic_task(current_app.config['PUSH_PERIOD'], push.s())


@celery.task
def cleanup():
    result = default_result.copy()
    resumes = Resume.query.filter_by(enabled=False).all()
    for resume in resumes:
        try:
            logger.warning(f'Cleanup: {resume}')
            db.session.delete(resume)
            db.session.commit()
        except Exception as e:
            result['failed'] += 1
            logger.error(f'Cleanup failed: {resume}, err={e}', exc_info=1)
        else:
            result['success'] += 1
        finally:
            result['total'] += 1

    return result


@celery.task
def reauth():
    result = default_result.copy()
    users = User.query.all()
    for user in users:
        try:
            provider = current_app.providers[user.provider]
            ids = provider.tokenize(user.refresh, refresh=True)

            user.access = ids['access_token']
            user.refresh = ids['refresh_token']

            delta = timedelta(seconds=ids['expires_in'])
            user.expires = datetime.utcnow() + delta

            db.session.add(user)
            db.session.commit()
        except TokenError as e:
            result['failed'] += 1
            logger.warning(f'Reauth failed: {user}, status={e}')
        except Exception as e:
            result['failed'] += 1
            logger.exception(f'Reauth failed: {user}, err={e}', exc_info=1)
        else:
            result['success'] += 1
            logger.info(f'Reauth success: {user}')
        finally:
            result['total'] += 1

    return result


@celery.task
def push():
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
        finally:
            result['total'] += 1

    return result
