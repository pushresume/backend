from datetime import datetime, timedelta

from celery.utils.log import get_task_logger

from . import create_app, db
from .models import Account, Resume
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
            logger.exception(f'Reauth failed: {account}, err={e}', exc_info=1)
        else:
            result['success'] += 1
            logger.info(f'Reauth success: {account}')
        finally:
            result['total'] += 1

    return result


@celery.task
def push():
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
        finally:
            result['total'] += 1

    return result
