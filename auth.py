# -*- coding: utf-8 -*-
import re
import functools

from tornado import httpclient
from tornado import escape
from tornado.httputil import url_concat
from tornado.auth import OAuth2Mixin, _auth_return_future, AuthError

try:
    import urllib.parse as urllib_parse
except ImportError:
    import urllib as urllib_parse


class QQOAuth2Mixin(OAuth2Mixin):
    """Handles the login for the QQ user, returning a user object.

        Example usage::

        class QQLoginHandler(tornado.web.RequestHandler,
                             QQOAuth2Mixin):

            @gen.coroutine
            def get(self):
                redirect_uri = <YOUR_REDIRCT_URI>
                if self.get_argument('code', None):
                    qq_user = yield self.get_authenticated_user(
                        redirect_uri=redirect_uri,
                        client_id=self.settings['qq_oauth']['key'],
                        client_secret=self.settings['qq_oauth']['secret'],
                        code=self.get_argument('code'))
                else:
                    yield self.authorize_redirect(
                        client_id=self.settings['qq_oauth']['key'],
                        redirect_uri=redirect_uri)
    """
    _OAUTH_ACCESS_TOKEN_URL = 'https://graph.qq.com/oauth2.0/token?'
    _OAUTH_AUTHORIZE_URL = 'https://graph.qq.com/oauth2.0/authorize?'

    @_auth_return_future
    def get_authenticated_user(self, redirect_uri, client_id, client_secret,
                               code, callback, grant_type='authorization_code',
                               extra_fields=None):
        http = self.get_auth_http_client()
        args = {
            'redirect_uri': redirect_uri,
            'code': code,
            'client_id': client_id,
            'client_secret': client_secret,
            'extra_params': {'grant_type': grant_type}
        }

        fields = {'nickname', 'figureurl'}

        if extra_fields:
            fields.update(extra_fields)

        http.fetch(self._oauth_request_token_url(**args),
                   functools.partial(self._on_access_token, client_id,
                                     callback, fields))

    def _on_access_token(self, client_id, future, fields, response):
        if response.error:
            future.set_exception(AuthError('QQ auth error %s' % str(response)))
            return

        args = escape.native_str(response.body).split('&')
        session = {
            'access_token': args[0].split('=')[1],
            'expires': args[1].split('=')[1],
        }

        http = self.get_auth_http_client()
        http.fetch(url_concat('https://graph.qq.com/oauth2.0/me?',
                              {'access_token': session['access_token']}),
                   functools.partial(self._on_access_openid, client_id,
                                     session, future, fields))

    def _on_access_openid(self, client_id, session, future, fields, response):
        if response.error:
            future.set_exception(
                AuthError('Error response %s fetching %s',
                          response.error, response.request.url)
            )
            return

        res = re.search(r'"openid":"([a-zA-Z0-9]+)"',
                        escape.native_str(response.body))

        session['openid'] = res.group(1)

        self.qq_request(
            path='/user/get_user_info',
            callback=functools.partial(
                self._on_get_user_info, future, session, fields),
            access_token=session['access_token'],
            openid=session['openid'],
            oauth_consumer_key=client_id,
        )

    def _on_get_user_info(self, future, session, fields, user):
        if user is None:
            future.set_result(None)
            return

        fieldmap = {field: user.get(field) for field in fields}

        fieldmap.update({'access_token': session['access_token'],
                         'session_expires': session.get('expires'),
                         'openid': session['openid']})

        future.set_result(fieldmap)

    @_auth_return_future
    def qq_request(self, path, callback, response_format='json',
                   post_data=None, **args):
        url = 'https://graph.qq.com' + path
        all_args = {'format': response_format}
        all_args.update(args)

        url += '?' + urllib_parse.urlencode(all_args)

        callback = functools.partial(self._on_qq_request, callback)
        http = self.get_auth_http_client()
        if post_data is not None:
            http.fetch(url, callback=callback, method="POST",
                       body=urllib_parse.urlencode(post_data))
        else:
            http.fetch(url, callback=callback)

    def _on_qq_request(self, future, response):
        if response.error:
            future.set_exception(
                AuthError('Error response %s fetching %s',
                          response.error, response.request.url)
            )
            return

        future.set_result(escape.json_decode(response.body))

    def get_auth_http_client(self):
        return httpclient.AsyncHTTPClient()
