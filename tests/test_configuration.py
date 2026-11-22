"""Configuration failures should be responses, not startup crashes."""

from pymongo.errors import OperationFailure
import pytest

from mongo_memory.mongo_connector import MongoConnector


@pytest.mark.parametrize('uri', [None, 'invalid-uri', 'mongodb://127.0.0.1:1/?serverSelectionTimeoutMS=20'])
def test_configuration_errors(monkeypatch, uri):
    if uri is None:
        monkeypatch.delenv('MCP_MONGO_MEMORY_CONNECTION', raising=False)
    else:
        monkeypatch.setenv('MCP_MONGO_MEMORY_CONNECTION', uri)
    with MongoConnector() as connector:
        for operation, arguments in [
            ('create_entities', ([{'name': 'test'}],)),
            ('get_entity', ('test',)),
            ('update_entity', ('test', {'$set': {'type': 'test'}})),
            ('delete_entity', ('test',)),
            ('find_entities', ({'name': 'test'},)),
            ('get_memory_structure', ()),
            ('create_relationship', ('a', 'b', 'knows')),
            ('get_relationships', ()),
            ('delete_relationship', ('a', 'b', 'knows')),
        ]:
            result = getattr(connector, operation)(*arguments)
            assert result['success'] is False
            assert result == connector.config_error


def test_memory_structure(mongo_connector):
    assert mongo_connector.get_memory_structure() == {}
    collection = mongo_connector.client[mongo_connector.SYSTEM_MEMORY_DB]['sys']
    collection.insert_one({'structure': True, 'entity_types': ['user']})
    assert mongo_connector.get_memory_structure() == {'entity_types': ['user']}


def test_database_errors_not_reported_as_missing_entities(mongo_connector, monkeypatch):
    def fail(*args, **kwargs):
        message = 'Database read failed'
        raise OperationFailure(message)

    monkeypatch.setattr('pymongo.collection.Collection.find_one', fail)
    for operation, arguments in [
        ('get_entity', ('test',)),
        ('get_memory_structure', ()),
        ('create_relationship', ('a', 'b', 'knows')),
        ('delete_relationship', ('a', 'b', 'knows')),
    ]:
        result = getattr(mongo_connector, operation)(*arguments)
        assert result['success'] is False
        assert result['error'] == 'Database error'


def test_initialization_failure(monkeypatch, mongo_connector):
    def fail(self):
        message = 'No permission to initialize indexes'
        raise OperationFailure(message)

    monkeypatch.setattr(MongoConnector, 'init_entity_rules', fail)
    with MongoConnector() as connector:
        assert connector.get_entity('test')['success'] is False
        assert connector.config_error['error'] == 'MongoDB initialization failed'
