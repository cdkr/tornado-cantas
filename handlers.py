# -*- coding: utf8 -*-
import os
import json

from mongoengine import DoesNotExist
from tornado.web import RequestHandler, authenticated, HTTPError
from tornado import gen

from auth import QQOAuth2Mixin
from utils import ComplexEncoder
from models import *

__all__ = (
    'ArchivedCardsHandler', 'ArchivedListsHandler', 'AttachmentHandler',
    'ClosedBoardsHandler', 'InvitedBoardsHandler', 'MyBoardsHandler',
    'Http404Handler', 'LoginHandler', 'LogoutHandler', 'MainHandler',
    'MyCardsHandler', 'NewBoardHandler', 'OrderCardHandler',
    'PublicBoardsHandler', 'QQLoginHandler', 'SingleBoardHandler',
    'SingleCardHandler', 'StandaloneHandler', 'WelcomeHandler',
)


class BaseHandler(RequestHandler):
    def get_current_user(self):
        user_id = self.get_cookie("oid")
        try:
            if user_id:
                user = User.objects.get(id=user_id)
                setattr(self, 'user', user)
                if user.isFirstLogin:
                    self.redirect('/welcome')
                    user.isFirstLogin = False
                    user.save()
                return user
        except DoesNotExist:
            pass

        return None

    def set_current_user(self, user):
        if user:
            self.set_cookie("oid", user._id)
        else:
            self.clear_cookie("oid")

    def render(self, *args, **kwargs):
        if self.current_user:
            kwargs['user'] = self.current_user
        kwargs['debug'] = self.settings.get('debug', False)
        super(BaseHandler, self).render(*args, **kwargs)

    def json(self, data):
        self.set_header("Content-Type", "application/json; charset=UTF-8")
        self.finish(json.dumps(data, cls=ComplexEncoder))


class QQLoginHandler(BaseHandler,
                     QQOAuth2Mixin):
    @gen.coroutine
    def get(self):
        redirect_uri = 'http://cantas.chifruit.com/auth/qq'
        if self.get_argument('code', None):
            qq_user = yield self.get_authenticated_user(
                redirect_uri=redirect_uri,
                client_id=self.settings['qq_oauth']['key'],
                client_secret=self.settings['qq_oauth']['secret'],
                code=self.get_argument('code'))
            try:
                user = User.objects.get(openId=qq_user['openid'])
            except DoesNotExist:
                user = User.objects.create(
                    username=qq_user['nickname'],
                    openId=qq_user['openid']
                )
            self.set_current_user(user)
            self.redirect('/')
        else:
            yield self.authorize_redirect(
                client_id=self.settings['qq_oauth']['key'],
                redirect_uri=redirect_uri
            )


class LoginHandler(BaseHandler):
    """ email/password login handler, used only in dev """

    def get(self):
        self.render('login.html', message='')

    def post(self):
        username = self.get_argument("username", "")
        password = self.get_argument("password", "")
        if self.check_permission(password, username):
            _email = 'admin@admin.com'

            try:
                user = User.objects.get(email=_email)
            except DoesNotExist:
                user = User.objects.create(
                    username=username,
                    password=password,
                    email=_email
                )
            self.set_current_user(user)
            self.redirect('/')
        else:
            self.redirect('/login')

    def check_permission(self, password, username):
        return username == password == "admin"


class LogoutHandler(BaseHandler):
    def get(self, *args, **kwargs):
        self.clear_all_cookies()
        self.redirect('/')


class MainHandler(BaseHandler):
    @authenticated
    def get(self, *args, **kwargs):
        self.render('application.html')


class BoardsHandler(BaseHandler):
    @authenticated
    def get(self, *args, **kwargs):
        self.json(self.get_boards().values())

    def get_boards(self):
        raise NotImplemented


class MyBoardsHandler(BoardsHandler):
    """ get my boards and invited boards """

    def get_boards(self):
        return Board.objects(
            creatorId=self.user.id, isClosed=False
        ) + BoardMemberRelation.get_invited_boards_by_member(self.user.id)


class PublicBoardsHandler(BoardsHandler):
    def get_boards(self):
        return Board.objects(isClosed=False,
                             isPublic=True).order_by('updated')


class ClosedBoardsHandler(BoardsHandler):
    def get_boards(self):
        return Board.objects(creatorId=self.user.id,
                             isClosed=True).order_by('updated')


class InvitedBoardsHandler(BoardsHandler):
    def get_boards(self):
        return BoardMemberRelation.get_invited_boards_by_member(self.user.id)


class NewBoardHandler(BaseHandler):
    @authenticated
    def get(self, *args, **kwargs):
        user = self.user
        board = Board.create_default(creator_id=user.id)

        activity_data = {
            'content': "This board is created by %s" % user.username,
            'creatorId': user.id,
            'boardId': board.id
        }

        Activity.objects.create(**activity_data)

        BoardMemberRelation.objects.create(
            boardId=board.id,
            userId=user.id,
        )

        self.json({'boardId': board.id})


class MyCardsHandler(BaseHandler):
    @authenticated
    def get(self, *args, **kwargs):
        cards = Card.objects(isArchived=False, creatorId=self.user.id).values()
        for card in cards:
            card['boardId'] = card.boardId.to_dict()
            card['listId'] = card.listId.to_dict()
        self.json(cards)


class ArchivedCardsHandler(BaseHandler):
    @authenticated
    def get(self, board_id, *args, **kwargs):
        self.json(Card.objects(isArchived=True, boardId=board_id).values())


class ArchivedListsHandler(BaseHandler):
    @authenticated
    def get(self, board_id, *args, **kwargs):
        self.json(List.objects(isArchived=True, boardId=board_id).values())


class OrderCardHandler(BaseHandler):
    @authenticated
    def get(self, list_id, *args, **kwargs):
        self.json(Card.objects(listId=list_id, isArchived=False).values())


class SingleBoardHandler(BaseHandler):
    @authenticated
    def get(self, board_id, *args, **kwargs):
        try:
            Board.objects.get(id=board_id)
            self.render('application.html')
        except:
            raise HTTPError(404)


class SingleCardHandler(BaseHandler):
    @authenticated
    def get(self, card_id, *args, **kwargs):
        try:
            Card.objects.get(id=card_id)
            self.render('application.html')
        except:
            raise HTTPError(404)


class AttachmentHandler(BaseHandler):
    attachment_dir = os.path.join(os.path.dirname(__file__),
                                  'static/attachments')

    @authenticated
    def get(self, *args, **kwargs):
        """handle downloading attachment"""
        pass

    @authenticated
    def post(self, card_id, *args, **kwargs):
        """handle uploading attachment"""

        # TODO: generate thumb img

        img = self.request.files['attachment'][0]
        file_name, extension = os.path.splitext(img['filename'])
        file_name += extension

        card_dir = os.path.join(self.attachment_dir, card_id)
        try:
            os.mkdir(card_dir)
        except OSError:
            pass

        with open(os.path.join(card_dir, file_name), 'w') as output_file:
            output_file.write(img['body'])
            size = os.path.getsize(output_file.name)

        attachment_data = dict(
            cardId=card_id,
            uploaderId=self.user.id,
            name=file_name,
            size=size,
            fileType='picture',
            path=file_name,
            cardThumbPath=file_name,
            cardDetailThumbPath=file_name
        )

        self.json({'attachment': attachment_data})


class StandaloneHandler(BaseHandler):
    def get(self, *args, **kwargs):
        self.render('standalone-help.html')


class WelcomeHandler(BaseHandler):
    @authenticated
    def get(self, *args, **kwargs):
        self.render('application.html')


class Http404Handler(BaseHandler):
    def get(self, *args, **kwargs):
        self.render('404.html')
