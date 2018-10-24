from datetime import datetime

from . import BaseProvider, IdentityError, ResumeError, PushError, TokenError


class Provider(BaseProvider):

    def redirect(self):
        return self._prov.get_authorize_url(
            response_type='code', skip_choose_account='true')

    def identity(self, token):
        try:
            session = self._prov.get_session(token=token)
            rv = session.get('me')
        except Exception as e:
            raise IdentityError(f'{type(e).__name__}: {e}')
        else:
            if rv.status_code is not 200:
                raise IdentityError(f'{rv.status_code} {rv.json()}')
            return rv.json()['id']

    def fetch(self, token):
        try:
            session = self._prov.get_session(token=token)
            rv = session.get('resumes/mine')
        except Exception as e:
            raise ResumeError(f'{type(e).__name__}: {e}')
        else:
            if rv.status_code is not 200:
                raise ResumeError(f'{rv.status_code} {rv.json()}')
            arr = []
            for item in rv.json()['items']:
                published = datetime.strptime(
                    item['updated_at'], '%Y-%m-%dT%H:%M:%S%z')
                arr.append({
                    'uniq': item['id'],
                    'name': f'{item["first_name"]} {item["last_name"]}',
                    'title': item['title'],
                    'published': published,
                    'link': item['url']
                })
            return arr

    def push(self, token, resume):
        try:
            session = self._prov.get_session(token=token)
            rv = session.post(f'resumes/{resume}/publish')
        except Exception as e:
            raise PushError(f'{type(e).__name__}: {e}')
        else:
            if rv.status_code not in range(200, 299):
                raise PushError(f'{rv.status_code} {rv.json()}')
            return True

    def tokenize(self, token, refresh=False):
        if not refresh:
            post = {'code': f'{token}', 'grant_type': 'authorization_code'}
        else:
            post = {'refresh_token': f'{token}', 'grant_type': 'refresh_token'}
        try:
            rv = self._prov.get_raw_access_token(
                data=post, headers=self._headers)
        except Exception as e:
            raise TokenError(f'{type(e).__name__}: {e}')
        else:
            if rv.status_code is not 200:
                raise TokenError(f'{rv.status_code} {rv.json()}')
            return rv.json()
