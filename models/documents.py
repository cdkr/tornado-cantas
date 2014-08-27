# -*- coding: utf8 -*-

from mongoengine import *

from base import MyDocument, AutonowDatetimeField, SockCRUDMixin


__all__ = ('Action', 'Activity', 'Attachment', 'Board', 'BoardMemberRelation',
           'Card', 'CardLabelRelation', 'CardSourceRelation', 'Checklist',
           'ChecklistItem', 'Comment', 'CommentSourceRelation', 'Group',
           'Label', 'List', 'LabelMetadata', 'Notification', 'Organization',
           'Permission', 'Role', 'SyncConfig', 'User', 'Vote')

connect('cantas')


class _Perm(EmbeddedDocument):
    users = ListField(ReferenceField('User'))
    roles = ListField(ReferenceField('Roled'))


class Perm(EmbeddedDocument):
    delete = EmbeddedDocumentField(_Perm)
    update = EmbeddedDocumentField(_Perm)


class Action(MyDocument):
    idMemberCreator = ReferenceField('User')
    data = DictField(default={})
    type = StringField()
    created = AutonowDatetimeField()


class Activity(MyDocument,
               SockCRUDMixin):
    content = StringField(required=True)
    creatorId = ReferenceField('User')
    boardId = ReferenceField('Board')
    createdOn = AutonowDatetimeField()


class Attachment(MyDocument,
                 SockCRUDMixin):
    cardId = ReferenceField('Card', required=True)
    uploaderId = ReferenceField('User')
    name = StringField(required=True)
    size = FloatField(required=True)
    fileType = StringField(default='other')
    path = StringField(required=True)
    isCover = BooleanField(default=False)
    cardThumbPath = StringField(default='')
    cardDetailThumbPath = StringField(default='')
    createdOn = AutonowDatetimeField()

    def to_dict(self):
        data = super(Attachment, self).to_dict()
        data['uploaderId'] = self.uploaderId.to_dict()
        return data

    @property
    def url(self):
        pass  # TODO


class Board(MyDocument,
            SockCRUDMixin):
    title = StringField(required=True)
    description = StringField(default='')
    isClosed = BooleanField(default=False)
    updated = AutonowDatetimeField(auto_now_update=True)
    created = AutonowDatetimeField()
    creatorId = ReferenceField('User', required=True)
    groupId = ReferenceField('Group')
    isPublic = BooleanField(default=True)
    voteStatus = StringField(default='enabled')
    commentStatus = StringField(default='enabled')
    perms = EmbeddedDocumentField(Perm)

    def to_dict(self):
        data = super(Board, self).to_dict()
        data['creatorId'] = self.creatorId.to_dict()
        return data

    @classmethod
    def create_default(cls, creator_id):
        """ create board using default name and create default lists in board """

        board = Board(title='Hello Cantas', creatorId=creator_id).save()
        board._create_default_lists()

        return board

    def _create_default_lists(self):
        for title, order in (("To Do", 65535),
                             ("Doing", 131071),
                             ("Done", 196607)):
            List(title=title, order=order,
                 creatorId=self.creatorId, boardId=self.id).save()

    @classmethod
    def _read(cls, conn, *args, **kwargs):
        return cls.objects.get(id=kwargs['_id']).to_dict()


class BoardMemberRelation(MyDocument,
                          SockCRUDMixin):
    member_status = {
        'unknown': "unknown",
        'available': "available",
        'inviting': "inviting",
        'kickedOff': "kickedOff"
    }

    boardId = ReferenceField('Board', required=True)
    userId = ReferenceField('User', required=True)
    addedOn = AutonowDatetimeField()
    quitOn = DateTimeField()  # FIXME
    status = StringField(default=member_status['available'])

    @classmethod
    def is_board_member(cls, user_id, board_id):
        """return True if user is member of board or user is creator"""

        return cls.objects(
            Q(userId=user_id) & Q(boardId=board_id) &
            (Q(status='inviting') | Q(status='available'))
        ).exists() or Board.objects.get(id=board_id).creatorId._id == user_id

    @classmethod
    def revoke(cls, user_id, board_id):
        pass  # TODO

    @classmethod
    def get_board_members(cls, board_id):
        return [relation.userId for relation in cls.objects(
            Q(boardId=board_id) &
            (Q(status='inviting') | Q(status='available'))
        )]

    @classmethod
    def get_invited_boards_by_member(cls, user_id):
        board_ids = [relation.boardId.id for relation in
                     cls.objects(Q(status='inviting') & Q(userId=user_id))]

        return Board.objects(id__in=board_ids)

    @classmethod
    def _read(cls, conn, *args, **kwargs):
        query_set = cls.objects
        if '$or' in kwargs:
            q = Q()
            for condition in kwargs.pop('$or'):
                q |= Q(**condition)
            query_set = query_set.filter(q)
        result = query_set.filter(**kwargs).values()
        for obj in result:
            obj['userId'] = User.objects.get(id=obj['userId']).to_dict()
        return result


class Card(MyDocument,
           SockCRUDMixin):
    title = StringField(required=True)
    description = StringField(default='Description')
    isArchived = BooleanField(default=False)
    updated = AutonowDatetimeField(auto_now_update=True)
    created = AutonowDatetimeField()
    dueDate = DateTimeField()
    order = IntField(default=-1)
    creatorId = ReferenceField('User', required=True)
    assignees = ListField(ReferenceField('User'))
    listId = ReferenceField('List', required=True)
    boardId = ReferenceField('Board', required=True)
    subscribeUserIds = ListField(ReferenceField('User'))

    def to_dict(self):
        data = super(Card, self).to_dict()
        data['badges'] = self.get_badges()
        data['cover'] = self.get_cover()
        data['board'] = self.get_board_meta()
        data['list'] = self.get_list_meta()
        return data

    def get_badges(self):
        """

        get count of comments, checklists, checked checklists, votes, attachments of card

        """

        check_lists = Checklist.objects(cardId=self)
        checkitems = ChecklistItem.objects(checklistId__in=check_lists)

        return {
            "votesNo": Vote.objects(cardId=self, yesOrNo=False).count(),
            "votesYes": Vote.objects(cardId=self, yesOrNo=True).count(),
            "comments": Comment.objects(cardId=self).count(),
            "attachments": Attachment.objects(cardId=self).count(),
            "checkitems": checkitems.count(),
            "checkitemsChecked": checkitems.filter(checked=True).count(),
        }

    def get_cover(self):
        attachment = Attachment.objects(cardId=self, isCover=True).first()
        if attachment:
            return attachment.cardThumbPath or attachment.path
        return ''

    def get_board_meta(self):
        return self.boardId.to_dict()

    def get_list_meta(self):
        return self.listId.to_dict()

    @classmethod
    def _read(cls, conn, *args, **kwargs):
        if '$query' in kwargs:
            kwargs = kwargs.pop('$query')
        return cls.objects(**kwargs).values()

    @classmethod
    def _create(cls, conn, *args, **kwargs):
        kwargs.update(creatorId=conn.user.id)
        card = cls.objects.create(**kwargs)
        conn.emit('/card:create', card.to_dict())
        return []


class CardLabelRelation(MyDocument,
                        SockCRUDMixin):
    boardId = ReferenceField('Board', required=True)
    cardId = ReferenceField('Card', required=True)
    labelId = ReferenceField('Label', required=True)
    selected = BooleanField(default=False)
    createdOn = AutonowDatetimeField()
    updatedOn = AutonowDatetimeField(auto_now_update=True)


class CardSourceRelation(MyDocument):
    syncConfigId = ReferenceField('SyncConfig', required=True)
    cardId = ReferenceField('Card', required=True)
    sourceId = StringField(required=True)
    sourceType = StringField(required=True)
    lastSyncTime = AutonowDatetimeField()


class Checklist(MyDocument,
                SockCRUDMixin):
    title = StringField(default="New Checklist")
    cardId = ReferenceField('Card', required=True)
    authorId = ReferenceField('User', required=True)
    createdOn = AutonowDatetimeField()
    updatedOn = AutonowDatetimeField(auto_now_update=True)


class ChecklistItem(MyDocument,
                    SockCRUDMixin):
    content = StringField(required=True)
    checked = BooleanField(default=False)
    order = IntField(default=1)
    checklistId = ReferenceField('Checklist', required=True)
    cardId = ReferenceField('Card', required=True)
    authorId = ReferenceField('User', required=True)
    createdOn = AutonowDatetimeField()
    updatedOn = AutonowDatetimeField(auto_now_update=True)


class Comment(MyDocument,
              SockCRUDMixin):
    content = StringField(required=True)
    cardId = ReferenceField('Card', required=True)
    authorId = ReferenceField('User', required=True)
    createdOn = AutonowDatetimeField()
    updatedOn = AutonowDatetimeField(auto_now_update=True)


class CommentSourceRelation(MyDocument):
    commentId = ReferenceField('Comment', required=True)
    cardId = ReferenceField('Card', required=True)
    sourceId = StringField(required=True)
    sourceType = StringField(required=True)
    lastSyncTime = AutonowDatetimeField()


class Group(MyDocument):
    name = StringField(required=True)
    description = StringField(default='')
    created = AutonowDatetimeField()


class Label(MyDocument):
    title = StringField(default='')
    order = IntField(required=True)
    color = StringField(required=True)
    boardId = ReferenceField('Board', required=True)
    createdOn = AutonowDatetimeField()
    updatedOn = AutonowDatetimeField(auto_now_update=True)


class List(MyDocument,
           SockCRUDMixin):
    title = StringField(required=True)
    isArchived = BooleanField(default=False)
    created = AutonowDatetimeField()
    creatorId = ReferenceField('User', required=True)
    order = IntField(default=-1)
    boardId = ReferenceField('Board', required=True)
    perms = EmbeddedDocumentField(Perm)

    @classmethod
    def _read(cls, conn, *args, **kwargs):
        return cls.objects(boardId=kwargs['boardId']).values()


class LabelMetadata(MyDocument):
    order = IntField(required=True, unique=True)
    title = StringField(default='')
    color = StringField(required=True, unique=True)


class Notification(MyDocument,
                   SockCRUDMixin):
    notification_type = {
        'invitation': "invitation",
        'subscription': "subscription",
        'mentioned': "mentioned",
        'information': "information"
    }

    userId = ReferenceField('User', required=True)
    massage = StringField(required=True)
    type = StringField(required=True,
                       default=notification_type['information'])
    isUnread = BooleanField(default=True)
    created = AutonowDatetimeField()


class Organization(MyDocument):
    name = StringField()
    description = StringField()


# FIXME
class Permission(MyDocument):
    idMember = ReferenceField('User')
    scope = StringField()
    # data = ListField(default=[])
    created = AutonowDatetimeField()


class Role(MyDocument):
    name = StringField(required=True)
    perms = EmbeddedDocumentField('Perm')


class SyncConfig(MyDocument,
                 SockCRUDMixin):
    boardId = ReferenceField('Board', required=True)
    listId = ReferenceField('List')
    queryUrl = StringField()
    queryType = StringField(required=True)
    isActive = BooleanField(default=True)
    intervalTime = IntField(default=8)
    creatorId = ReferenceField('User', required=True)
    createdOn = AutonowDatetimeField()
    updatedOn = AutonowDatetimeField(auto_now_update=True)


class User(MyDocument):
    username = StringField(required=True)
    fullname = StringField(default='')
    password = StringField(default='')
    email = StringField(default='')
    joined = AutonowDatetimeField()
    isFirstLogin = BooleanField(default=True)
    roles = ListField(ReferenceField('Role'))
    openId = StringField(unique=True, required=False, default='')


class Vote(MyDocument,
           SockCRUDMixin):
    yesOrNo = BooleanField(default=True)
    cardId = ReferenceField('Card', required=True)
    authorId = ReferenceField('User', required=True)
    createdOn = AutonowDatetimeField()
    updatedOn = AutonowDatetimeField(auto_now_update=True)

    @classmethod
    def _create(cls, conn, *args, **kwargs):
        vote = cls.objects.create(**kwargs)
        conn.emit('/vote:create', vote.to_dict())
        return 'Can not vote', vote.to_dict()
