import six

from ..exceptions import ImmutableAttributeError
from ..shared.objects import SetOnceDescriptor


class ManyToOneDescriptor(object):
    def __init__(self, name, relation):
        self.name = name
        self.relation = relation.copy()

    def __get__(self, instance, owner):
        if instance is None:
            self.relation

        return instance.match_relations(self.relation.type, rev=True).one

    def __set__(self, instance, value):
        raise ImmutableAttributeError(self.name, instance)

    def __delete__(self, instance):
        raise ImmutableAttributeError(self.name, instance)


class RelationMeta(type):
    def __init__(cls, class_name, bases, attrs):
        cls.type = SetOnceDescriptor('type', type=str)
        cls.backref = SetOnceDescriptor('backref', type=str)
        cls.obj = SetOnceDescriptor('obj')
        cls.restricted_types = SetOnceDescriptor('restricted_types',
                                                 type=RelationMeta.restricted)
        for attr in ('unbound_start', 'unbound_end'):
            setattr(cls, attr, SetOnceDescriptor(attr, type=bool))
        super(RelationMeta, cls).__init__(class_name, bases, attrs)

    @staticmethod
    def restricted(types):
        def get_type(t):
            try:
                return t.__node__.type
            except AttributeError:
                return t

        return tuple(get_type(t) for t in types)


@six.add_metaclass(RelationMeta)
class Relation(object):
    def __init__(self, type_, obj=None, backref=None,
                 restrict_types=(), **unbound_args):
        self.type = type_
        self.obj = obj
        self.backref = backref
        unbound = unbound_args['unbound'] = bool(unbound_args.get('unbound'))
        for arg in ('unbound_start', 'unbound_end'):
            unbound_args[arg] = bool(unbound_args.get(arg, unbound))
        self.__unbound_args = unbound_args
        self.restricted_types = restrict_types

    def copy(self, obj=None):
        return self.__class__(self.type, obj=obj or self.obj,
                              backref=self.backref,
                              restrict_types=self.restricted_types,
                              **dict(self.unbound_args))

    def create(self, related):
        if self.restricted_types:
            if not any(label in related.__node__.labels
                       for label in self.restricted_types):
                restricted_types = map(str, self.restricted_types)
                raise ValueError("Related object is '%r' but must be one of: "
                                 "'%s'" % (related,
                                           ', '.join(restricted_types)))
        return self.obj.create_relation(self.type, related,
                                        **self.__unbound_args)

    def delete(self, related):
        return self.obj.delete_relation(self.type, related,
                                        **self.__unbound_args)

    def match(self, *labels, **properties):
        return self.obj.match_relations(self.type, *labels, **properties)

    def merge(self, related):
        if self.restricted_types:
            if not any(label in related.__node__.labels
                       for label in self.restricted_types):
                restricted_types = map(str, self.restricted_types)
                raise ValueError("Related object is '%r' but must be one of: "
                                 "'%s'" % (related,
                                           ', '.join(restricted_types)))
        return self.obj.merge_relation(self.type, related,
                                       **self.__unbound_args)

    def create_backref(self, cls):
        raise NotImplementedError

    @property
    def unbound_args(self):
        return self.__unbound_args.items()


class OneToManyRelation(Relation):
    def __init__(self, type_, **kw):
        kw['unbound_start'] = kw['unbound'] = False
        super(OneToManyRelation, self).__init__(type_, **kw)

    def create_backref(self, cls):
        setattr(cls, self.backref, ManyToOneDescriptor(self.backref, self))


class ManyToManyRelation(Relation):
    def create_backref(self, cls):
        setattr(cls, self.backref, self.copy())
