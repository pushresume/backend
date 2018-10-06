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

confirmation_schema = {
    'channel': {
        'type': 'string',
        'required': True,
        'allowed': ['telegram']
    }
}

subscription_schema = confirmation_schema
