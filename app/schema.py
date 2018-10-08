from flask import current_app


login_schema = {
    'code': {
        'type': 'string',
        'required': True
    }
}

resume_schema = {
    'identity': {
        'type': 'string',
        'required': True
    }
}

subscription_schema = {
    'channel': {
        'type': 'string',
        'required': True,
        'allowed': current_app.config['NOTIFICATIONS_CHANNELS']
    }
}
