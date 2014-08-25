# -*- coding: utf8 -*-

import tornadio2

from models import crud_event_handlers, User


class Connection(tornadio2.SocketConnection):
    def on_open(self, request):
        user_id = request.get_cookie('oid').value
        setattr(self, 'user', User.objects.get(id=user_id))

    def on_event(self, name, args=[], kwargs=dict()):
        if name in crud_event_handlers:
            result = crud_event_handlers[name](self, *args, **kwargs)
            if isinstance(result, tuple):
                return result
            else:
                return None, result
        else:
            return super(Connection, self).on_event(name, args, kwargs)

    # FIXME: it's fake
    @tornadio2.event('join-board')
    def on_join_board(self, *args, **kwargs):

        self.emit('joined-board',
                  *[{"ok": 0, "visitors":
                      [{"username": "admin", "email": "admin@admin.com",
                        "_id": self.user._id, "__v": 0,
                        "isFirstLogin": False, "roles": [],
                        "joined": "2014-06-14T11:46:48.575Z", "fullname": "",
                        "role": {"name": "admin",
                                 "desc": "Admin - full control"}}],
                     "message": "isMember"}])
