"""MongoDB connector for agent memory operations."""

from collections.abc import Iterator, Mapping
from datetime import datetime
import os
from types import TracebackType
from typing import Any, Optional

from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError, PyMongoError, ServerSelectionTimeoutError


class MongoConnector:
    """Handles MongoDB connections and operations for agent memory.

    This class manages MongoDB connections, provides CRUD operations for entities,
    and maintains validation rules for the memory structure.

    Attributes:
        AGENT_MEMORY_DB (str): Name of the agent memory database
        AGENT_MEMORY_INDEX_FIELD (str): Name of the index field for entities
        AGENT_MEMORY_DESCRIPTION_FIELD (str): Name of the description field
        ENTITY_COLLECTION (str): Name of the entities collection
        SYSTEM_MEMORY_DB (str): Name of the system memory database
    """

    def _load_envs(self) -> None:
        """Load MongoDB connection string from environment variables.

        Raises:
            ValueError: If required environment variable is missing.
        """
        # Get connection string from environment variable
        self.mongo_uri = os.getenv('MCP_MONGO_MEMORY_CONNECTION')
        if not self.mongo_uri:
            msg = 'No MCP_MONGO_MEMORY_CONNECTION set for MongoDB'
            raise ValueError(msg)

    # Method removed as direct connection string is now used

    def get_connection(self) -> MongoClient:
        """Get MongoDB client connection.

        Returns:
            MongoDB client instance
        """
        return MongoClient(self.mongo_uri)

    def test_connection(self) -> bool:
        """Test MongoDB connection by pinging the server.

        Returns:
            True if connection successful, False otherwise
        """
        client = self.get_connection()
        db = client.test
        try:
            db.command('ping')
        except ServerSelectionTimeoutError:
            return False
        return True

    def __init__(self) -> None:
        """Initialize MongoDB connector with default settings and connection."""
        self.AGENT_MEMORY_DB = 'agent_memory'
        self.AGENT_MEMORY_INDEX_FIELD = 'name'
        self.AGENT_MEMORY_DESCRIPTION_FIELD = 'description'
        self.ENTITY_COLLECTION = 'entities'
        self.SYSTEM_MEMORY_DB = 'memory'

        self._load_envs()
        self.client = self.get_connection()
        if not self.test_connection():
            msg = "Can't connect to MongoDB"
            raise ValueError(msg)

        # Initialize rules and indexes
        self.init_entity_rules()

    def __enter__(self) -> 'MongoConnector':
        """Context manager entry.

        Returns:
            Self instance
        """
        return self

    def __del__(self) -> None:
        """Destructor that ensures connection cleanup."""
        self.client.close()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Context manager exit.

        Args:
            exc_type: Exception type if error occurred
            exc_val: Exception value if error occurred
            exc_tb: Exception traceback if error occurred
        """
        self.client.close()

    # Validation and unique rules

    def _check_required_is_applied(self) -> bool:
        """Check if required field validation rule is applied.

        Returns:
            True if validation exists, False otherwise
        """
        database = self.client[self.AGENT_MEMORY_DB]
        validation_info = database.command(
            'listCollections',
            filter={self.AGENT_MEMORY_INDEX_FIELD: self.ENTITY_COLLECTION},
        )
        schema = validation_info['cursor']['firstBatch'][0].get('options', {}).get('validator', {})
        return bool(schema)

    def _apply_required_rule(self) -> None:
        """Apply required field validation rule to entity collection."""
        database = self.client[self.AGENT_MEMORY_DB]
        database.command('collMod', self.ENTITY_COLLECTION, validator={
            '$jsonSchema': {
                'bsonType': 'object',
                'required': [self.AGENT_MEMORY_INDEX_FIELD],
                'properties': {
                    self.AGENT_MEMORY_INDEX_FIELD: {
                        'bsonType': 'string',
                        'description': 'Unique name of the entity - required field',
                    },
                },
            },
        })

    def _check_unique_is_applied(self) -> bool:
        """Check if unique index is applied on the index field.

        Returns:
            True if unique index exists, False otherwise
        """
        database = self.client[self.AGENT_MEMORY_DB]
        collection = database[self.ENTITY_COLLECTION]
        indexes = list(collection.list_indexes())
        return any(
            self.AGENT_MEMORY_INDEX_FIELD in index['key']
            and index.get('unique', False)
            for index in indexes
        )

    def _apply_unique_rule(self) -> None:
        """Apply unique index on the index field."""
        database = self.client[self.AGENT_MEMORY_DB]
        collection = database[self.ENTITY_COLLECTION]
        collection.create_index(self.AGENT_MEMORY_INDEX_FIELD, unique=True)

    def _validate_entity(self, entity: dict[str, Any]) -> bool:
        """Validate entity structure before insertion attempt.

        Args:
            entity: Entity data to validate

        Returns:
            True if validation passes, False otherwise

        Raises:
            ValueError: If required fields are missing or have invalid types
        """
        # Check required fields
        if self.AGENT_MEMORY_INDEX_FIELD not in entity:
            msg = f'Missing required field: {self.AGENT_MEMORY_INDEX_FIELD}'
            raise ValueError(msg)

        # Validate field types
        if not isinstance(entity[self.AGENT_MEMORY_INDEX_FIELD], str):
            msg = f'Field {self.AGENT_MEMORY_INDEX_FIELD} must be a string'
            raise TypeError(msg)

        return True

    def init_entity_rules(self) -> None:
        """Initialize validation rules and indexes for entities."""
        database = self.client[self.AGENT_MEMORY_DB]
        collection = database[self.ENTITY_COLLECTION]

        # Create unique index if it doesn't exist
        if not self._check_unique_is_applied():
            collection.create_index(self.AGENT_MEMORY_INDEX_FIELD, unique=True)

        # Apply validation rules if they don't exist
        if not self._check_required_is_applied():
            self._apply_required_rule()

    # end of validation and unique rules

    def get_memory_structure(self) -> dict[str, Any]:
        """Get memory structure from system database.

        Returns:
            Dictionary containing memory structure information
        """
        database = self.client[self.SYSTEM_MEMORY_DB]
        collection = database['sys']
        memory_structure = collection.find_one({'structure': True})
        memory_structure.pop('_id')
        memory_structure.pop('structure')
        return memory_structure

    def get_memory_structure_new(self) -> Iterator[dict[str, Any]]:
        """Get new memory structure based on existing entities.

        Returns:
            Iterator of field information dictionaries
        """
        database = self.client[self.AGENT_MEMORY_DB]
        collection = database[self.ENTITY_COLLECTION]
        excluded_fields = [
            '_id',
            self.AGENT_MEMORY_INDEX_FIELD,
            self.AGENT_MEMORY_DESCRIPTION_FIELD,
        ]
        pipeline = [
            {'$project': {'fields': {'$objectToArray': '$$ROOT'}}},
            {'$unwind': '$fields'},
            # Add field type
            {'$addFields': {
                'field_type': {'$type': '$fields.v'},
            }},
            # Filter out excluded fields and exclude date and object types
            {'$match': {
                'fields.k': {'$nin': excluded_fields},
                'field_type': {'$nin': ['date', 'object']},
            }},
            {'$group': {
                '_id': '$fields.k',
                'values': {'$addToSet': '$fields.v'},
            }},
            {'$sort': {'_id': 1}},
        ]

        return collection.aggregate(pipeline)

    def create_entities(self, entities: list[dict[str, Any]]) -> Mapping:
        """Create multiple entities in memory.

        Args:
            entities: List of entity dictionaries to create

        Returns:
            Operation result with success status and count or error
        """
        try:
            # Validate all entities first
            for entity in entities:
                if not self._validate_entity(entity):
                    return {
                        'success': False,
                        'error': f'Invalid entity structure: {entity}',
                    }

            database = self.client[self.AGENT_MEMORY_DB]
            collection = database[self.ENTITY_COLLECTION]

            # Add timestamps
            for entity in entities:
                entity['created_at'] = datetime.now()
                entity['updated_at'] = datetime.now()

            result = collection.insert_many(entities)
            return {
                'success': True,
                'created': len(result.inserted_ids),
            }
        except DuplicateKeyError as e:
            return {
                'success': False,
                'error': f'Duplicate key error: {e!s}',
            }
        except PyMongoError as e:
            return {
                'success': False,
                'error': str(e),
            }

    def create_relationship(
        self,
        from_entity: str,
        to_entity: str,
        relationship_type: str,
        properties: dict[str, Any] | None = None,
    ) -> Mapping:
        """Create a relationship between two entities.

        Args:
            from_entity: Source entity name
            to_entity: Target entity name
            relationship_type: Type of relationship
            properties: Optional properties for the relationship

        Returns:
            Operation result containing success details or error information

        Raises:
            ValueError: If any entity does not exist
            ValueError: If relationship_type format is invalid
            PyMongoError: If any MongoDB-related error occurs
        """
        # Validate entities exist
        if not self.get_entity(from_entity):
            msg = f"Source entity '{from_entity}' does not exist"
            raise ValueError(msg)
        if not self.get_entity(to_entity):
            msg = f"Target entity '{to_entity}' does not exist"
            raise ValueError(msg)

        # Parse relationship type and properties
        type_parts = relationship_type.split(':', 1)
        rel_type = type_parts[0]
        rel_properties = properties or {}

        if len(type_parts) > 1:
            try:
                for prop in type_parts[1].split(','):
                    key, value = prop.split('=')
                    rel_properties[key.strip()] = value.strip()
            except ValueError:
                msg = 'Invalid relationship_type format'
                raise ValueError(msg)

        database = self.client[self.AGENT_MEMORY_DB]
        collection = database['relationships']

        # Ensure indexes exist
        if not self._check_relationship_indexes():
            self._create_relationship_indexes(collection)

        relationship = {
            'from_entity': from_entity,  # Store as string
            'to_entity': to_entity,      # Store as string
            'type': rel_type,
            'properties': rel_properties,
            'created_at': datetime.now(),
        }

        try:
            result = collection.insert_one(relationship)
            return {
                'acknowledged': result.acknowledged,
                'inserted_id': str(result.inserted_id),
            }
        except PyMongoError as e:
            return {
                'error': str(e),
                'details': 'A MongoDB-related error occurred during relationship creation.',
            }

    def _check_relationship_indexes(self) -> bool:
        """Check if required relationship indexes exist.

        Returns:
            True if indexes exist, False otherwise
        """
        database = self.client[self.AGENT_MEMORY_DB]
        collection = database['relationships']
        indexes = list(collection.list_indexes())
        required_indexes = [
            ('from_entity', 1),
            ('to_entity', 1),
            ('type', 1),
            ('from_name', 1),
            ('to_name', 1),
        ]
        existing_keys = [
            next(iter(index['key'].items()))
            for index in indexes
            if index['key'] != {'_id': 1}
        ]
        return all(idx in existing_keys for idx in required_indexes)

    def _create_relationship_indexes(self, collection) -> None:
        """Create required indexes for relationships collection.

        Args:
            collection: MongoDB collection for relationships
        """
        # Create individual indexes
        collection.create_index([('from_entity', 1)])
        collection.create_index([('to_entity', 1)])
        collection.create_index([('type', 1)])
        collection.create_index([('from_name', 1)])
        collection.create_index([('to_name', 1)])
        # Create compound unique index
        collection.create_index(
            [('from_entity', 1), ('to_entity', 1), ('type', 1)],
            unique=True,
        )

    def get_entity(self, name: str) -> dict[str, Any] | None:
        """Get a single entity by its name.

        Args:
            name: Unique name of the entity to retrieve

        Returns:
            Entity dictionary if found, None otherwise

        Raises:
            PyMongoError: If any MongoDB-related error occurs
        """
        database = self.client[self.AGENT_MEMORY_DB]
        collection = database[self.ENTITY_COLLECTION]

        try:
            return collection.find_one({self.AGENT_MEMORY_INDEX_FIELD: name})
        except PyMongoError as e:
            error_message = f'Error retrieving entity: {e}'
            raise PyMongoError(error_message) from e

    def update_entity(
        self,
        name: str,
        update: dict[str, Any],
        upsert: bool = False,
    ) -> Mapping:
        """Update a single entity by its name.

        Args:
            name: Unique name of the entity to update
            update: MongoDB update dictionary
            upsert: If True, create entity if it doesn't exist

        Returns:
            Operation result with success status or error
        """
        try:
            database = self.client[self.AGENT_MEMORY_DB]
            collection = database[self.ENTITY_COLLECTION]

            # Add updated_at timestamp if not in update
            if '$set' not in update:
                update['$set'] = {}
            if 'updated_at' not in update['$set']:
                update['$set']['updated_at'] = datetime.now()

            result = collection.update_one(
                {self.AGENT_MEMORY_INDEX_FIELD: name},
                update,
                upsert=upsert,
            )

            if result.matched_count > 0 or (upsert and result.upserted_id):
                return {'success': True}
            return {
                'success': False,
                'error': 'Entity not found',
            }
        except PyMongoError as e:
            return {
                'success': False,
                'error': str(e),
            }

    def delete_entity(self, name: str) -> Mapping:
        """Delete a single entity by its name.

        Args:
            name: Unique name of the entity to delete

        Returns:
            Operation result with success status or error
        """
        try:
            database = self.client[self.AGENT_MEMORY_DB]
            collection = database[self.ENTITY_COLLECTION]

            result = collection.delete_one({self.AGENT_MEMORY_INDEX_FIELD: name})

            if result.deleted_count > 0:
                return {'success': True}
            return {
                'success': False,
                'error': 'Entity not found',
            }
        except PyMongoError as e:
            return {
                'success': False,
                'error': str(e),
            }

    def find_entities(self, query: dict[str, Any], limit: int = 10) -> list[dict[str, Any]]:
        """Find entities matching the query criteria.

        Args:
            query: MongoDB query dictionary. Must be a non-empty dictionary.
            limit: Maximum number of entities to return. Defaults to 10.

        Returns:
            List of matching entity dictionaries.

        Raises:
            ValueError: If query is empty or None
            TypeError: If query is not a dictionary
            PyMongoError: If any MongoDB-related error occurs
        """
        if query is None:
            msg = 'Query parameter cannot be None'
            raise ValueError(msg)
        if not isinstance(query, dict):
            msg = f'Query must be a dictionary, got {type(query)}'
            raise TypeError(msg)
        if not query:
            msg = 'Query dictionary cannot be empty'
            raise ValueError(msg)

        database = self.client[self.AGENT_MEMORY_DB]
        collection = database[self.ENTITY_COLLECTION]

        try:
            cursor = collection.find(query)
            return list(cursor.limit(limit))
        except PyMongoError as e:
            error_message = f'Error finding entities: {e}'
            raise PyMongoError(error_message) from e

    def get_relationships(
        self,
        query: Optional[dict[str, Any]] = None,
        limit: int = 10,
    ) -> Mapping[str, object]:
        """Get relationships matching the query criteria.

        Args:
            query (Optional[Dict]): MongoDB query dictionary for filtering relationships.
                Example: {"type": "imports"} - finds all import relationships
                Example: {"from_entity": "main_module"} - finds all relationships from main_module
                Default: None (returns all relationships)

            limit (int): Maximum number of relationships to return.
                Must be between 1 and 100.
                Default: 10

        Returns:
            Mapping[str, object]: Operation result containing:
                - relationships: List[Dict] - List of found relationships
                - total_count: int - Total number of matches (before limit)
                - page_info: Dict - Pagination information

        Raises:
            ValueError: If limit is not between 1 and 100
            TypeError: If query is provided but not a dictionary
            OperationError: If database operation fails
        """
        if not 1 <= limit <= 100:
            msg = 'Limit must be between 1 and 100'
            raise ValueError(msg)

        if query is not None and not isinstance(query, dict):
            msg = 'Query must be a dictionary'
            raise TypeError(msg)

        database = self.client[self.AGENT_MEMORY_DB]
        collection = database['relationships']

        try:
            # Get total count before applying limit
            total_count = collection.count_documents(query or {})

            # Get relationships with limit
            cursor = collection.find(query or {}).limit(limit + 1)
            relationships = list(cursor)

            # Check if there are more results
            has_next = len(relationships) > limit
            if has_next:
                relationships = relationships[:limit]

            # Convert ObjectId to string for entity references
            for rel in relationships:
                if '_id' in rel:
                    rel['_id'] = str(rel['_id'])

            return {
                'relationships': relationships,
                'total_count': total_count,
                'page_info': {
                    'has_next': has_next,
                    'next_cursor': str(relationships[-1]['_id']) if has_next and relationships else None,
                },
            }
        except PyMongoError as e:
            return {
                'error': f'Database operation failed: {e!s}',
                'relationships': [],
                'total_count': 0,
                'page_info': {'has_next': False, 'next_cursor': None},
            }

    def delete_relationship(
        self,
        from_entity: str,
        to_entity: str,
        relationship_type: str,
    ) -> Mapping[str, object]:
        """Delete a specific relationship between entities.

        Args:
            from_entity (str): Source entity name
            to_entity (str): Target entity name
            relationship_type (str): Type of relationship to delete

        Returns:
            Mapping[str, object]: Operation result containing:
                - acknowledged: bool - Whether operation was successful
                - deleted_count: int - Number of relationships deleted
                - error: Optional[str] - Error message if operation failed

        Raises:
            ValueError: If any entity does not exist
            ValueError: If relationship_type format is invalid
            OperationError: If database operation fails
        """
        # Validate entities exist
        if not self.get_entity(from_entity):
            msg = f"Source entity '{from_entity}' does not exist"
            raise ValueError(msg)
        if not self.get_entity(to_entity):
            msg = f"Target entity '{to_entity}' does not exist"
            raise ValueError(msg)

        # Parse relationship type and properties
        type_parts = relationship_type.split(':', 1)
        rel_type = type_parts[0]
        properties = {}

        if len(type_parts) > 1:
            try:
                for prop in type_parts[1].split(','):
                    key, value = prop.split('=')
                    properties[key.strip()] = value.strip()
            except ValueError:
                msg = 'Invalid relationship_type format'
                raise ValueError(msg)

        # Prepare query
        query = {
            'from_entity': from_entity,
            'to_entity': to_entity,
            'type': rel_type,
        }
        if properties:
            query['properties'] = properties  # Match exact properties object

        try:
            database = self.client[self.AGENT_MEMORY_DB]
            collection = database['relationships']
            result = collection.delete_one(query)

            return {
                'acknowledged': result.acknowledged,
                'deleted_count': result.deleted_count,
                'error': None,
            }
        except PyMongoError as e:
            return {
                'acknowledged': False,
                'deleted_count': 0,
                'error': str(e),
            }
