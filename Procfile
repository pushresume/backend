web: gunicorn -b 0.0.0.0:$PORT 'app:create_app()'
worker: celery worker -A app.tasks -B --scheduler redbeat.RedBeatScheduler -l info
