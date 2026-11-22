"""Tests for basic entity operations."""

from copy import deepcopy
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from mongo_memory.mongo_connector import MongoConnector


def test_create_entities(mongo_connector):
    """Test creating multiple entities."""
    entities = [
        {
            'name': 'test_entity_1',
            'type': 'test',
            'data': {'value': 1},
        },
        {
            'name': 'test_entity_2',
            'type': 'test',
            'data': {'value': 2},
        },
    ]

    result = mongo_connector.create_entities(entities)
    assert result['success'] is True
    assert result['created'] == 2

    # Verify entities were created
    found = mongo_connector.find_entities({'type': 'test'})
    assert found['success'] is True
    assert found['count'] == 2
    assert {e['name'] for e in found['entities']} == {'test_entity_1', 'test_entity_2'}

def test_get_entity(mongo_connector):
    """Test retrieving a single entity."""
    # Create test entity
    entity = {
        'name': 'test_entity',
        'type': 'test',
        'data': {'value': 1},
    }
    mongo_connector.create_entities([entity])

    # Test retrieval
    found = mongo_connector.get_entity('test_entity')
    assert found is not None
    assert found['name'] == 'test_entity'
    assert found['type'] == 'test'
    assert found['data']['value'] == 1

    # Test non-existent entity
    not_found = mongo_connector.get_entity('non_existent')
    assert not_found['success'] is False
    assert not_found['error'] == 'Entity not found'

def test_update_entity(mongo_connector):
    """Test updating an entity."""
    # Create test entity
    entity = {
        'name': 'test_entity',
        'type': 'test',
        'data': {'value': 1},
    }
    mongo_connector.create_entities([entity])

    # Test update
    update = {
        '$set': {
            'data.value': 2,
            'updated_at': datetime.now(UTC),
        },
    }
    result = mongo_connector.update_entity('test_entity', update)
    assert result['success'] is True

    # Verify update
    updated = mongo_connector.get_entity('test_entity')
    assert updated['data']['value'] == 2
    assert 'updated_at' in updated

@pytest.mark.parametrize('operator', ['$set', '$inc', '$setOnInsert'])
def test_upsert_creation_timestamps(mongo_connector, operator):
    update = {operator: {'data.value': 1}}
    assert mongo_connector.update_entity('upserted', update, upsert=True)['success'] is True
    created = mongo_connector.get_entity('upserted')
    assert isinstance(created['created_at'], datetime)
    assert created['created_at'] == created['updated_at']

    assert mongo_connector.update_entity('upserted', {'$inc': {'data.value': 1}}, upsert=True)['success'] is True
    updated = mongo_connector.get_entity('upserted')
    assert updated['data']['value'] == 2
    assert updated['created_at'] == created['created_at']
    assert updated['updated_at'] >= created['updated_at']


@pytest.mark.parametrize('update', [
    {'$set': {'data.value': 1}},
    {'$setOnInsert': {'type': 'test'}},
    {'$setOnInsert': {'created_at': datetime(2020, 1, 1, tzinfo=UTC)}},
    {'$set': {'created_at': datetime(2020, 1, 1, tzinfo=UTC)}},
    {'$unset': {'created_at': ''}},
    {'$rename': {'old_created_at': 'created_at'}},
])
def test_upsert_timestamp_update_is_copied(monkeypatch, update):
    """Unit check: no MongoDB; preserve caller operators and nested dictionaries."""
    client = MagicMock()
    client.get_default_database.return_value.name = 'mongo_memory_test'
    collection = client['mongo_memory_test']['entities']
    collection.update_one.return_value.matched_count = 0
    collection.update_one.return_value.upserted_id = 'new'
    monkeypatch.setenv('MCP_MONGO_MEMORY_CONNECTION', 'mongodb://localhost/mongo_memory_test')
    monkeypatch.setattr(MongoConnector, 'get_connection', lambda _self: client)
    original = deepcopy(update)
    with MongoConnector() as connector:
        assert connector.update_entity('upserted', update, upsert=True)['success'] is True
    assert update == original
    call = collection.update_one.call_args
    assert call.args[0] == {'name': 'upserted'}
    assert call.kwargs == {'upsert': True}
    sent = call.args[1]
    assert sent['$set']['updated_at'].tzinfo == UTC
    if 'created_at' in update.get('$setOnInsert', {}):
        assert sent['$setOnInsert'] == update['$setOnInsert']
    elif any(key in update for key in ('$unset', '$rename')) or 'created_at' in update.get('$set', {}):
        assert '$setOnInsert' not in sent
    else:
        assert sent['$setOnInsert']['created_at'] == sent['$set']['updated_at']
        for key, value in update.get('$setOnInsert', {}).items():
            assert sent['$setOnInsert'][key] == value


def test_upsert_preserves_existing_creation_time(mongo_connector):
    assert mongo_connector.create_entities([{'name': 'existing'}])['success'] is True
    created = mongo_connector.get_entity('existing')
    assert mongo_connector.update_entity('existing', {'$set': {'type': 'test'}}, upsert=True)['success'] is True
    updated = mongo_connector.get_entity('existing')
    assert updated['created_at'] == created['created_at']
    assert updated['updated_at'] >= created['updated_at']


def test_delete_entity(mongo_connector):
    """Test deleting an entity."""
    # Create test entity
    entity = {
        'name': 'test_entity',
        'type': 'test',
        'data': {'value': 1},
    }
    mongo_connector.create_entities([entity])

    # Test deletion
    result = mongo_connector.delete_entity('test_entity')
    assert result['success'] is True

    # Verify deletion
    found = mongo_connector.get_entity('test_entity')
    assert found['success'] is False
    assert found['error'] == 'Entity not found'

def test_find_entities(mongo_connector):
    """Test finding entities with query."""
    # Create test entities
    entities = [
        {
            'name': 'test_entity_1',
            'type': 'test',
            'category': 'A',
            'data': {'value': 1},
        },
        {
            'name': 'test_entity_2',
            'type': 'test',
            'category': 'B',
            'data': {'value': 2},
        },
        {
            'name': 'test_entity_3',
            'type': 'other',
            'category': 'A',
            'data': {'value': 3},
        },
    ]
    mongo_connector.create_entities(entities)

    # Test finding by type
    found_test = mongo_connector.find_entities({'type': 'test'})
    assert found_test['count'] == 2
    assert len(found_test['entities']) == 2

    # Test finding by category
    found_category_a = mongo_connector.find_entities({'category': 'A'})
    assert found_category_a['count'] == 2

    # Test finding with multiple criteria
    found_test_cat_a = mongo_connector.find_entities({
        'type': 'test',
        'category': 'A',
    })
    assert found_test_cat_a['count'] == 1
    assert found_test_cat_a['entities'][0]['name'] == 'test_entity_1'

def test_entity_validation(mongo_connector):
    """Test entity validation rules."""
    # Test creating entity without required field
    invalid_entity = {
        'type': 'test',
        'data': {'value': 1},
    }
    result = mongo_connector.create_entities([invalid_entity])
    assert result['success'] is False
    assert result['error'] == 'Invalid entity structure'

    # Test creating entity with invalid field type
    invalid_type_entity = {
        'name': 123,  # Should be string
        'type': 'test',
        'data': {'value': 1},
    }
    result = mongo_connector.create_entities([invalid_type_entity])
    assert result['success'] is False
    assert result['error'] == 'Invalid entity structure'

def test_unique_constraint(mongo_connector):
    """Test unique name constraint."""
    entity = {
        'name': 'test_entity',
        'type': 'test',
        'data': {'value': 1},
    }

    # Create first entity
    result1 = mongo_connector.create_entities([entity])
    assert result1['success'] is True

    # Try to create duplicate
    duplicate = {
        'name': 'test_entity',
        'type': 'test',
        'data': {'value': 2},
    }
    result2 = mongo_connector.create_entities([duplicate])
    assert result2['success'] is False
    assert 'duplicate key error' in result2['error'].lower()
    assert result2['created'] == 0


@pytest.mark.parametrize('entities', [[], None, {}, [{'name': 'valid'}, {'type': 'missing_name'}], ['invalid']])
def test_invalid_batch_does_not_write(mongo_connector, entities):
    result = mongo_connector.create_entities(entities)
    assert result['success'] is False
    assert result['created'] == 0
    collection = mongo_connector.client[mongo_connector.AGENT_MEMORY_DB]['entities']
    assert collection.count_documents({}) == 0


def test_inputs_are_not_mutated(mongo_connector):
    entities = [{'name': 'unchanged', 'data': {'value': 1}}]
    assert mongo_connector.create_entities(entities)['success'] is True
    assert entities == [{'name': 'unchanged', 'data': {'value': 1}}]
    update = {'$set': {'data.value': 2}}
    assert mongo_connector.update_entity('unchanged', update)['success'] is True
    assert update == {'$set': {'data.value': 2}}


def test_partial_batch_reports_inserted_count(mongo_connector):
    mongo_connector.create_entities([{'name': 'existing'}])
    result = mongo_connector.create_entities([{'name': 'first'}, {'name': 'existing'}, {'name': 'last'}])
    assert result['success'] is False
    assert result['error'] == 'Duplicate key error'
    assert result['created'] == 1
    found = mongo_connector.find_entities({'name': {'$in': ['first', 'last']}})
    assert [entity['name'] for entity in found['entities']] == ['first']


@pytest.mark.parametrize('limit', [0, -1, True, '10', 1.5])
def test_find_entities_invalid_limit(mongo_connector, limit):
    result = mongo_connector.find_entities({'type': 'test'}, limit=limit)
    assert result['success'] is False
    assert result['error'] == 'Invalid limit value'


@pytest.mark.parametrize('update', [None, {}, {'data.value': 2}, {'$set': 'invalid'}])
def test_update_invalid_input(mongo_connector, update):
    result = mongo_connector.update_entity('test', update)
    assert result['success'] is False
    assert result['error'] == 'Invalid update'
