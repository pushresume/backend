from datetime import datetime, timedelta

from . import BaseProvider, IdentityError, ResumeError, PushError, TokenError


class Provider(BaseProvider):

    def __init__(self, refresh_token_url, **kwargs):
        super().__init__(**kwargs)
        self._headers.update({'X-Api-App-Id': self._prov.client_secret})
        self._prov.refresh_token_url = refresh_token_url

    def redirect(self):
        return self._prov.get_authorize_url(
            redirect_uri=self._redirect_uri, client_id=self._prov.client_id)

    def identity(self, token):
        try:
            session = self._prov.get_session(token=token)
            rv = session.get('user/current/', headers=self._headers)
        except Exception as e:
            raise IdentityError(f'{type(e).__name__}: {e}')
        else:
            if rv.status_code is not 200:
                raise IdentityError(f'{rv.status_code} {rv.json()}')
            return rv.json()['email']

    def fetch(self, token):
        try:
            session = self._prov.get_session(token=token)
            rv = session.get('user_cvs/', headers=self._headers)
        except Exception as e:
            raise ResumeError(f'{type(e).__name__}: {e}')
        else:
            if rv.status_code is not 200:
                raise ResumeError(f'{rv.status_code} {rv.json()}')
            arr = []
            for item in rv.json()['objects']:
                timestamp = datetime.fromtimestamp(item['date_published'])
                published = timestamp - timedelta(hours=3)
                arr.append({
                    'uniq': str(item['id']),
                    'name': f'{item["firstname"]} {item["lastname"]}',
                    'title': item['profession'],
                    'published': published,
                    'link': item['link']
                })
            return arr

    def push(self, token, resume):
        try:
            session = self._prov.get_session(token=token)
            rv = session.post(f'user_cvs/update_datepub/{resume}/')
        except Exception as e:
            raise PushError(f'{type(e).__name__}: {e}')
        else:
            if rv.status_code not in range(200, 299):
                raise PushError(f'{rv.status_code} {rv.json()}')
            return True

    def tokenize(self, token, refresh=False):
        post = {
            'client_id': self._prov.client_id,
            'client_secret': self._prov.client_secret
        }
        try:
            if not refresh:
                post['code'] = token,
                post['redirect_uri'] = self._redirect_uri
                rv = self._prov.get_raw_access_token(
                    data=post, headers=self._headers)
            else:
                post['refresh_token'] = token
                session = self._prov.get_session()
                rv = session.get(
                   self._prov.refresh_token_url,
                   headers=self._headers, params=post)
        except Exception as e:
            raise TokenError(f'{type(e).__name__}: {e}')
        else:
            if rv.status_code is not 200:
                raise TokenError(f'{rv.status_code} {rv.json()}')
            return rv.json()
