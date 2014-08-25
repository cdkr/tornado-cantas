# -*- coding: utf-8 -*-

from mongoengine import *
from bson import ObjectId

from datetime import datetime


# FIXME: the *args seems never used
class SockCRUDMixin(object):
    event = ['create', 'read', 'update', 'delete', 'patch']

    # TODO: generate activity content after creating
    @classmethod
    def _create(cls, conn, *args, **kwargs):
        obj = cls.objects.create(**kwargs)
        conn.emit('/%s:create' % cls.__name__.lower(), obj.to_dict())
        return obj.to_dict()

    @classmethod
    def _read(cls, conn, *args, **kwargs):
        try:
            if '_id' in kwargs:
                return cls.objects.get(kwargs['_id']).to_dict()
            return cls.objects(**kwargs).values()
        except:
            return None

    @classmethod
    def _update(cls, conn, *args, **kwargs):
        object_id = kwargs.pop('_id')
        obj = cls.objects.get(id=object_id)
        obj = obj.update_doc(**kwargs)
        conn.emit('/%s/%s:update' % (cls.__name__.lower(), object_id),
                  obj.to_dict())
        return None

    @classmethod
    def _delete(cls, conn, *args, **kwargs):
        object_id = kwargs.pop('_id')
        obj = cls.objects.get(id=object_id)
        conn.emit('/%s/%s:delete' % (cls.__name__.lower(), object_id),
                  obj.to_dict())
        obj.delete()
        return None

    @classmethod
    def _patch(cls, conn, *args, **kwargs):
        object_id = kwargs.pop('id')
        obj = cls.objects.get(id=object_id)
        obj = obj.update_doc(**kwargs)
        conn.emit('/%s/%s:update' % (cls.__name__.lower(), object_id),
                  obj.to_dict())
        return None


class AutonowDatetimeField(DateTimeField):
    def __init__(self, default=datetime.now, auto_now_update=False, **kwargs):
        super(AutonowDatetimeField, self).__init__(default=default, **kwargs)
        if auto_now_update:
            self.auto_now_update = True


class AwesomerQuerySet(QuerySet):
    def exists(self):
        # FIXME: this could be more efficient
        return self.count() > 0

    def values(self):
        return [obj.to_dict() for obj in self]

    def __add__(self, other):
        """ perform union on two queryset """
        ids = set([obj.id for obj in self] + [obj.id for obj in other])
        return self._document.objects(id__in=ids)


class MyDocument(Document):
    meta = {
        'allow_inheritance': True,
        'abstract': True,
        'queryset_class': AwesomerQuerySet
    }

    def save(self, *args, **kwargs):
        for field_name in self:
            if getattr(getattr(self, field_name), 'auto_now_update', False):
                setattr(self, field_name, datetime.now())

        super(MyDocument, self).save(*args, **kwargs)
        return self

    @property
    def _id(self):
        return str(self.id)

    def to_dict(self):
        data = dict(self.to_mongo())

        for k, v in data.items():
            if isinstance(v, (datetime, ObjectId)):
                data[k] = str(v)
            if isinstance(v, list):
                data[k] = [str(o) for o in v]

        data.pop('_cls')
        data['_id'] = str(data['_id'])
        return data

    # FIXME
    def update_doc(self, **data_dict):
        def field_value(field, value):

            if field.__class__ in (ListField, SortedListField):
                return [
                    field_value(field.field, item)
                    for item in value
                ]
            if isinstance(field, ReferenceField):
                _id = value['_id'] if isinstance(value, dict) else value
                return field.document_type.objects.get(id=_id)
            if field.__class__ in (
                    EmbeddedDocumentField,
                    GenericEmbeddedDocumentField,
                    GenericReferenceField
            ):
                return field.document_type.objects.get(id=value)

            else:
                return value

        for key, value in data_dict.items():
            try:
                setattr(self, key, field_value(self._fields[key], value))
            except KeyError:
                pass
        self.save()

        return self
