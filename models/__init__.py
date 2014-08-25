# -*- coding: utf-8 -*-

from documents import *
from base import SockCRUDMixin


def _init_handlers():
    """

    :return {'board:read': Board._read,
             'card:create': Card._create,
             ...}

    """

    handlers = {}
    import documents

    for name, cls in documents.__dict__.items():
        try:
            if issubclass(cls, SockCRUDMixin):
                handlers.update({
                    '%s:%s' % (name.lower(), event): getattr(cls, '_' + event)
                    for event in SockCRUDMixin.event
                })
        except TypeError:
            pass
    return handlers


crud_event_handlers = _init_handlers()