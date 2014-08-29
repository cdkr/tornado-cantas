# -*- coding: utf-8 -*-
import json
import datetime

from bson import ObjectId


class ComplexEncoder(json.JSONEncoder):
    """ json encoder for unsupported data type """
    def default(self, obj):
        if isinstance(obj, datetime.datetime):
            return str(obj)
        if isinstance(obj, ObjectId):
            return str(obj)
        return json.JSONEncoder.default(self, obj)
