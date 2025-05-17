"""Tests for relationship management functions."""

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
    """Create MongoConnector instance for testing."""
    connector = MongoConnector()
    # Clean up relationships collection before each test
    database = connector.client[connector.AGENT_MEMORY_DB]
    database['relationships'].delete_many({})
    return connector


@pytest.fixture
def test_entities(mongo_connector):
    """Create test entities for relationship testing."""
    entities = [
        {'name': 'test_module_1', 'type': 'module'},
        {'name': 'test_module_2', 'type': 'module'},
    ]
    mongo_connector.create_entities(entities)
    yield entities
    # Cleanup
    for entity in entities:
        mongo_connector.delete_entity(entity['name'])


def test_get_relationships_basic(mongo_connector, test_entities):
    """Test basic relationship retrieval."""
    # Create test relationship
    mongo_connector.create_relationship(
        from_entity='test_module_1',
        to_entity='test_module_2',
        relationship_type='imports',
    )

    # Test retrieval
    result = mongo_connector.get_relationships()
    assert 'relationships' in result
    assert 'total_count' in result
    assert 'page_info' in result
    assert result['total_count'] >= 1
    assert len(result['relationships']) >= 1

    # Verify relationship data
    rel = result['relationships'][0]
    assert rel['from_entity'] == 'test_module_1'
    assert rel['to_entity'] == 'test_module_2'
    assert rel['type'] == 'imports'


def test_get_relationships_with_query(mongo_connector, test_entities):
    """Test relationship retrieval with query filter."""
    # Create test relationships
    mongo_connector.create_relationship(
        from_entity='test_module_1',
        to_entity='test_module_2',
        relationship_type='imports:scope=core',
    )
    mongo_connector.create_relationship(
        from_entity='test_module_2',
        to_entity='test_module_1',
        relationship_type='depends_on:priority=high',
    )

    # Test query by type
    result = mongo_connector.get_relationships({'type': 'imports'})
    assert result['total_count'] == 1
    assert result['relationships'][0]['type'] == 'imports'

    # Test query by entity
    result = mongo_connector.get_relationships({'from_entity': 'test_module_1'})
    assert result['total_count'] == 1
    assert result['relationships'][0]['from_entity'] == 'test_module_1'


def test_get_relationships_limit(mongo_connector, test_entities):
    """Test relationship retrieval with limit."""
    # Create multiple relationships
    for i in range(15):
        mongo_connector.create_relationship(
            from_entity='test_module_1',
            to_entity='test_module_2',
            relationship_type=f'test_type_{i}',
        )

    # Test with default limit
    result = mongo_connector.get_relationships()
    assert len(result['relationships']) == 10
    assert result['page_info']['has_next'] is True

    # Test with custom limit
    result = mongo_connector.get_relationships(limit=5)
    assert len(result['relationships']) == 5
    assert result['page_info']['has_next'] is True


def test_get_relationships_validation(mongo_connector):
    """Test input validation for get_relationships."""
    # Test invalid limit
    with pytest.raises(ValueError):
        mongo_connector.get_relationships(limit=0)
    with pytest.raises(ValueError):
        mongo_connector.get_relationships(limit=101)

    # Test invalid query
    with pytest.raises(TypeError):
        mongo_connector.get_relationships(query='invalid')


def test_delete_relationship_basic(mongo_connector, test_entities):
    """Test basic relationship deletion."""
    # Create relationship
    mongo_connector.create_relationship(
        from_entity='test_module_1',
        to_entity='test_module_2',
        relationship_type='imports',
    )

    # Delete relationship
    result = mongo_connector.delete_relationship(
        from_entity='test_module_1',
        to_entity='test_module_2',
        relationship_type='imports',
    )

    assert result['acknowledged'] is True
    assert result['deleted_count'] == 1
    assert result['error'] is None

    # Verify deletion
    result = mongo_connector.get_relationships({
        'from_entity': 'test_module_1',
        'to_entity': 'test_module_2',
        'type': 'imports',
    })
    assert result['total_count'] == 0


def test_delete_relationship_with_properties(mongo_connector, test_entities):
    """Test relationship deletion with properties."""
    # Create relationship with properties
    mongo_connector.create_relationship(
        from_entity='test_module_1',
        to_entity='test_module_2',
        relationship_type='imports:scope=core,priority=high',
    )

    # Delete relationship with properties
    result = mongo_connector.delete_relationship(
        from_entity='test_module_1',
        to_entity='test_module_2',
        relationship_type='imports:scope=core,priority=high',
    )

    assert result['acknowledged'] is True
    assert result['deleted_count'] == 1

    # Verify deletion
    result = mongo_connector.get_relationships({
        'from_entity': 'test_module_1',
        'to_entity': 'test_module_2',
        'type': 'imports',
    })
    assert result['total_count'] == 0


def test_delete_relationship_validation(mongo_connector):
    """Test input validation for delete_relationship."""
    # Test non-existent entities
    with pytest.raises(ValueError):
        mongo_connector.delete_relationship(
            from_entity='non_existent',
            to_entity='test_module_2',
            relationship_type='imports',
        )

    # Test invalid relationship type format
    with pytest.raises(ValueError):
        mongo_connector.delete_relationship(
            from_entity='test_module_1',
            to_entity='test_module_2',
            relationship_type='imports:invalid_format',
        )
