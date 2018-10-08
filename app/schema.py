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
        'allowed': ['telegram']
    }
}
