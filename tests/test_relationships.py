"""Tests for relationship management functions."""

import pytest


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
    for limit in (0, 101, -1, True, '10', 1.5):
        result = mongo_connector.get_relationships(limit=limit)
        assert result['success'] is False
        assert result['error'] == 'Invalid limit value'

    # Test invalid query
    result = mongo_connector.get_relationships(query='invalid')
    assert result['success'] is False
    assert result['error'] == 'Invalid query type'


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
    assert result['success'] is True

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


def test_delete_relationship_validation(mongo_connector, test_entities):
    """Test input validation for delete_relationship."""
    # Test non-existent entities
    result = mongo_connector.delete_relationship(
        from_entity='non_existent',
        to_entity='test_module_2',
        relationship_type='imports',
    )
    assert result['success'] is False
    assert result['error'] == 'Source entity not found'

    # Test invalid relationship type format
    result = mongo_connector.delete_relationship(
        from_entity='test_module_1',
        to_entity='test_module_2',
        relationship_type='imports:invalid_format',
    )
    assert result['success'] is False
    assert result['error'] == 'Invalid relationship_type format'


@pytest.mark.parametrize('relationship_type', ['', ':key=value', 'imports:invalid', 'imports:=value', 'imports:key=v,', None])
def test_relationship_format_rejected(mongo_connector, test_entities, relationship_type):
    for operation in (mongo_connector.create_relationship, mongo_connector.delete_relationship):
        result = operation('test_module_1', 'test_module_2', relationship_type)
        assert result['success'] is False
        assert result['error'] == 'Invalid relationship_type format'


@pytest.mark.parametrize('relationship_type', ['knows', 'knows:', 'knows:key=a=b'])
def test_relationship_round_trip(mongo_connector, test_entities, relationship_type):
    result = mongo_connector.create_relationship('test_module_1', 'test_module_2', relationship_type)
    assert result['success'] is True
    result = mongo_connector.delete_relationship('test_module_1', 'test_module_2', relationship_type)
    assert result['success'] is True
    assert result['deleted_count'] == 1


def test_relationship_missing_entity(mongo_connector, test_entities):
    for source, target, role in [('missing', 'test_module_2', 'Source'), ('test_module_1', 'missing', 'Target')]:
        result = mongo_connector.create_relationship(source, target, 'knows')
        assert result['success'] is False
        assert result['error'] == f'{role} entity not found'


def test_relationship_duplicate(mongo_connector, test_entities):
    assert mongo_connector.create_relationship('test_module_1', 'test_module_2', 'knows')['success'] is True
    result = mongo_connector.create_relationship('test_module_1', 'test_module_2', 'knows:key=other')
    assert result['success'] is False
    assert result['error'] == 'Duplicate key error'


def test_relationship_indexes(mongo_connector):
    collection = mongo_connector.client[mongo_connector.AGENT_MEMORY_DB]['relationships']
    indexes = collection.index_information()
    assert 'from_name_1' not in indexes
    assert 'to_name_1' not in indexes
    assert indexes['from_entity_1_to_entity_1_type_1']['unique'] is True
