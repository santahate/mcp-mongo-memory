"""Tests for basic entity operations."""

from datetime import datetime

import pytest

from mongo_memory.mongo_connector import MongoConnector


@pytest.fixture(autouse=True)
def cleanup_db():
    """Clean up database before each test."""
    connector = MongoConnector()
    db = connector.client[connector.AGENT_MEMORY_DB]
    db.drop_collection(connector.ENTITY_COLLECTION)
    yield
    db.drop_collection(connector.ENTITY_COLLECTION)

@pytest.fixture
def mongo_connector():
    """Create a test instance of MongoConnector."""
    return MongoConnector()

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
    assert len(found) == 2
    assert any(e['name'] == 'test_entity_1' for e in found)
    assert any(e['name'] == 'test_entity_2' for e in found)

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
    assert not_found is None

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
            'updated_at': datetime.now(),
        },
    }
    result = mongo_connector.update_entity('test_entity', update)
    assert result['success'] is True

    # Verify update
    updated = mongo_connector.get_entity('test_entity')
    assert updated['data']['value'] == 2
    assert 'updated_at' in updated

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
    assert found is None

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
    assert len(found_test) == 2

    # Test finding by category
    found_category_a = mongo_connector.find_entities({'category': 'A'})
    assert len(found_category_a) == 2

    # Test finding with multiple criteria
    found_test_cat_a = mongo_connector.find_entities({
        'type': 'test',
        'category': 'A',
    })
    assert len(found_test_cat_a) == 1
    assert found_test_cat_a[0]['name'] == 'test_entity_1'

def test_entity_validation(mongo_connector):
    """Test entity validation rules."""
    # Test creating entity without required field
    invalid_entity = {
        'type': 'test',
        'data': {'value': 1},
    }
    with pytest.raises(ValueError):
        mongo_connector.create_entities([invalid_entity])

    # Test creating entity with invalid field type
    invalid_type_entity = {
        'name': 123,  # Should be string
        'type': 'test',
        'data': {'value': 1},
    }
    with pytest.raises(ValueError):
        mongo_connector.create_entities([invalid_type_entity])

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
