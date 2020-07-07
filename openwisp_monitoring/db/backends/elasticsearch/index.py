import uuid

from django.conf import settings
from elasticsearch.exceptions import NotFoundError
from elasticsearch_dsl import Date, Document, InnerDoc, Nested, Q, Search


class Point(InnerDoc):
    time = Date(required=True, default_timezone=settings.TIME_ZONE)
    fields = Nested(dynamic=True, required=True, multi=True)


class MetricDocument(Document):
    tags = Nested(dynamic=True, required=False, multi=True)
    points = Nested(Point)

    class Index:
        name = 'metric'
        settings = {
            'number_of_shards': 1,
            'number_of_replicas': 0,
            'lifecycle.name': 'default',
            'lifecycle.rollover_alias': 'metric',
        }


def find_metric(client, index, tags, retention_policy=None, add=False):
    search = Search(using=client, index=index)
    if tags:
        tags_dict = dict()
        for key, value in tags.items():
            tags_dict[f'tags.{key}'] = value
        q = Q(
            'nested',
            path='tags',
            query=Q(
                'bool', must=[Q('match', **{k: str(v)}) for k, v in tags_dict.items()]
            ),
        )
    else:
        q = Q()
    try:
        result = list(search.query(q).execute())[0].meta
        return result['id'], result['index']
    except (NotFoundError, AttributeError, IndexError):
        if add:
            document = create_document(
                client, index, tags, retention_policy=retention_policy
            )
            return document['_id'], document['_index']
        return None


def create_document(client, key, tags, _id=None, retention_policy=None):
    """
    Adds document to relevant index using ``keys``, ``tags`` and ``id`` provided.
    If no ``id`` is provided a random ``uuid`` would be used.
    """
    _id = str(_id or uuid.uuid1())
    # If index exists, create the document and return
    try:
        index_aliases = client.indices.get_alias(index=key)
        for k, v in index_aliases.items():
            if v['aliases'][key]['is_write_index']:
                break
        client.create(index=k, id=_id, body={'tags': tags})
        return {'_id': _id, '_index': k}
    except NotFoundError:
        pass
    # Create a new index if it doesn't exist
    name = f'{key}-000001'
    document = MetricDocument(meta={'id': _id})
    document._index = document._index.clone(name)
    # Create a new index template if it doesn't exist
    if not client.indices.exists_template(name=key):
        document._index.settings(**{'lifecycle.rollover_alias': key})
        if retention_policy:
            document._index.settings(**{'lifecycle.name': retention_policy})
        # add index pattern is added for Index Lifecycle Management
        document._index.as_template(key, f'{key}-*').save(using=client)
    document.init(using=client, index=name)
    document.meta.index = name
    document.tags = tags
    document.save(using=client, index=name)
    client.indices.put_alias(index=name, name=key, body={'is_write_index': True})
    if retention_policy:
        client.indices.put_settings(
            body={'lifecycle.name': retention_policy}, index=name
        )
    client.indices.put_settings(body={'lifecycle.rollover_alias': key}, index=name)
    client.indices.refresh(index=key)
    return document.to_dict(include_meta=True)
