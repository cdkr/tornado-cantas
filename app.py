# -*- coding: utf-8 -*-
import os
import base64
import uuid

from tornado import ioloop
from tornado.web import Application, StaticFileHandler
from tornado.options import define, options
from tornadio2.router import TornadioRouter

from handlers import *
from sock import Connection

define("port", default=8000)
define("debug", default=True, type=bool)
options.parse_command_line()

settings = {
    'login_url': '/login',
    'template_path': os.path.join(os.path.dirname(__file__), 'templates'),
    'cookie_secret': base64.b64encode(uuid.uuid4().bytes + uuid.uuid4().bytes),
    'xsrf_cookies': False,
    'debug': options.debug,
}

try:
    from secret import secret_settings

    secret_settings.update(secret_settings)
except ImportError:
    pass

SockServer = TornadioRouter(Connection)

static_urls = [
    (r'/%s/(.*)' % i, StaticFileHandler, {'path': './static/%s' % i})
    for i in ('javascripts', 'stylesheets', 'images', 'attachments')
]

urls = [
    (r'/', MainHandler),
    (r'/login', LoginHandler),
    (r'/logout', LogoutHandler),
    (r'/auth/qq', QQLoginHandler),
    (r'/(boards|cards)/(\w+)', MainHandler),
    (r'/api/mine', MyBoardsHandler),
    (r'/api/public', PublicBoardsHandler),
    (r'/api/closed', ClosedBoardsHandler),
    (r'/api/invited', InvitedBoardsHandler),
    (r'/api/new', NewBoardHandler),
    (r'/api/cards/mine', MyCardsHandler),
    (r'/api/archived/cards/(\w+)', ArchivedCardsHandler),
    (r'/api/archived/lists/(\w+)', ArchivedListsHandler),
    (r'/api/archived/getorders/(\w+)', OrderCardHandler),
    (r'/board/(\w+)/(\w+)', SingleBoardHandler),
    (r'/card/(\w+)/(\w+)', SingleCardHandler),
    (r'/upload/(\w+)', AttachmentHandler),
    (r'/attachment/(\w+)/download', AttachmentHandler),
    (r'/welcome', WelcomeHandler),
    (r'/standalonehelp', StandaloneHandler),
    (r'/help', MainHandler),
    (r'/account', MainHandler),
] + static_urls + SockServer.urls

if __name__ == '__main__':
    app = Application(urls, **settings)
    app.listen(port=options.port)
    ioloop.IOLoop.instance().start()
