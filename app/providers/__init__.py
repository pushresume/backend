from rauth import OAuth2Service


class ProviderError(Exception):
    """Provider Error"""


class IdentityError(ProviderError):
    """Identity Error"""


class ResumeError(ProviderError):
    """Resume Error"""


class PushError(ProviderError):
    """Push Error"""


class TokenError(ProviderError):
    """Token Error"""


class BaseProvider(object):
    """Base Provider"""

    _headers = {'User-Agent': 'PushResume'}

    def __init__(self, name, redirect_uri, **kwargs):
        self.name = name
        self._redirect_uri = redirect_uri
        self._prov = OAuth2Service(name=name, **kwargs)

    def redirect(self):
        raise NotImplemented

    def identity(self, token):
        raise NotImplemented

    def fetch(self, token):
        raise NotImplemented

    def push(self, token, resume):
        raise NotImplemented

    def tokenize(self, code, refresh=False):
        raise NotImplemented

    def __str__(self):
        return f'{self.name}'
