"""MongoDB connector for agent memory operations."""

from collections.abc import Iterator, Mapping
from datetime import datetime, timezone
import os
from types import TracebackType
from typing import Any, Optional

from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.errors import DuplicateKeyError, PyMongoError, ServerSelectionTimeoutError

from .response_utils import create_error_response, create_success_response


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
        MAX_RELATIONSHIPS_LIMIT (int): Maximum number of relationships that can be retrieved at once
    """

    def _load_envs(self) -> dict[str, Any]:
        """Load MongoDB connection string from environment variables.

        Returns:
            Dictionary with success status and connection details or error information
        """
        # Get connection string from environment variable
        self.mongo_uri = os.getenv('MCP_MONGO_MEMORY_CONNECTION')
        if not self.mongo_uri:
            return create_error_response(
                'MCP_MONGO_MEMORY_CONNECTION environment variable not set',
                'The mongo-memory MCP server requires a MongoDB connection string',
                'Set the environment variable in your MCP configuration',
                setup_instructions={
                    'step_1': 'Set the environment variable in your MCP configuration',
                    'step_2': 'Add this to your MCP server config:',
                    'example': {
                        'env': {
                            'MCP_MONGO_MEMORY_CONNECTION': 'mongodb://username:password@host:port/database',
                        },
                    },
                    'mongodb_atlas': 'For free MongoDB Atlas setup, see: https://github.com/santahate/mcp-mongo-memory#configuration',
                },
            )
        return {'success': True, 'connection_string': self.mongo_uri}

    def is_configured(self) -> bool:
        """Check if MongoDB connector is properly configured.

        Returns:
            True if configured and connected, False otherwise
        """
        return self.config_error is None and self.client is not None

    def get_configuration_status(self) -> dict[str, Any]:
        """Get current configuration status and any error details.

        Returns:
            Dictionary with configuration status and error details if any
        """
        if self.config_error:
            return self.config_error
        return {'success': True, 'status': 'MongoDB connection configured and working'}

    def _check_configuration(self) -> dict[str, Any] | None:
        """Check if MongoDB is properly configured.

        Returns:
            Error dictionary if not configured, None if configured properly
        """
        if not self.is_configured():
            return self.get_configuration_status()
        return None

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
        self.MAX_RELATIONSHIPS_LIMIT = 100
        self.config_error = None

        env_result = self._load_envs()
        if not env_result['success']:
            # Store configuration error for later retrieval
            self.config_error = env_result
            self.client = None
            return

        self.client = self.get_connection()
        if not self.test_connection():
            self.config_error = create_error_response(
                "Can't connect to MongoDB",
                'Connection string is set but MongoDB server is not reachable',
                'Check MongoDB server status and connection settings',
                troubleshooting={
                    'check_1': 'Verify MongoDB server is running',
                    'check_2': 'Check connection string format',
                    'check_3': 'Verify network connectivity',
                    'check_4': 'Check MongoDB Atlas IP whitelist if using Atlas',
                },
            )
            return

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
        if hasattr(self, 'client') and self.client is not None:
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
        if hasattr(self, 'client') and self.client is not None:
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
        # Check configuration first
        config_error = self._check_configuration()
        if config_error:
            return config_error

        try:
            # Validate all entities first
            for entity in entities:
                if not self._validate_entity(entity):
                    return create_error_response(
                        'Invalid entity structure',
                        f'Entity validation failed: {entity}',
                        'Ensure entity has required "name" field and valid structure',
                    )

            database = self.client[self.AGENT_MEMORY_DB]
            collection = database[self.ENTITY_COLLECTION]

            # Add timestamps
            for entity in entities:
                entity['created_at'] = datetime.now(timezone.utc)
                entity['updated_at'] = datetime.now(timezone.utc)

            result = collection.insert_many(entities)
            return create_success_response(created=len(result.inserted_ids))
        except DuplicateKeyError as e:
            return create_error_response(
                'Duplicate key error',
                f'Entity with this name already exists: {e!s}',
                'Use update_entity to modify existing entities or choose a different name',
            )
        except PyMongoError as e:
            return create_error_response(
                'Database error',
                f'Failed to create entities: {e!s}',
                'Check MongoDB connection and entity data format',
            )

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
        # Check configuration first
        config_error = self._check_configuration()
        if config_error:
            return config_error

        # Validate entities exist
        if not self._get_entity_internal(from_entity):
            msg = f"Source entity '{from_entity}' does not exist"
            raise ValueError(msg)
        if not self._get_entity_internal(to_entity):
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
                return create_error_response(
                    'Invalid relationship_type format',
                    f'Expected format: "type:key1=value1,key2=value2", got: "{relationship_type}"',
                    'Use format like "works_at:position=developer,department=RnD"',
                    example='works_at:position=developer,department=RnD',
                )

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
            'created_at': datetime.now(timezone.utc),
        }

        try:
            result = collection.insert_one(relationship)
            return {
                'acknowledged': result.acknowledged,
                'inserted_id': str(result.inserted_id),
            }
        except PyMongoError as e:
            return create_error_response(
                'Database error',
                f'Failed to create relationship: {e!s}',
                'Check MongoDB connection and relationship data',
            )

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

    def _create_relationship_indexes(self, collection: Collection) -> None:
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

    def _get_entity_internal(self, name: str) -> dict[str, Any] | None:
        """Internal method to get entity without configuration error handling.

        Used by other methods that need to check entity existence.

        Args:
            name: Unique name of the entity to retrieve

        Returns:
            Entity dictionary if found, None otherwise
        """
        if not self.is_configured():
            return None

        database = self.client[self.AGENT_MEMORY_DB]
        collection = database[self.ENTITY_COLLECTION]

        try:
            return collection.find_one({self.AGENT_MEMORY_INDEX_FIELD: name})
        except PyMongoError:
            return None

    def get_entity(self, name: str) -> dict[str, Any]:
        """Get a single entity by its name.

        Args:
            name: Unique name of the entity to retrieve

        Returns:
            Dictionary with entity data or error information

        Raises:
            PyMongoError: If any MongoDB-related error occurs
        """
        # Check configuration first
        config_error = self._check_configuration()
        if config_error:
            return config_error

        database = self.client[self.AGENT_MEMORY_DB]
        collection = database[self.ENTITY_COLLECTION]

        try:
            entity = collection.find_one({self.AGENT_MEMORY_INDEX_FIELD: name})
            if entity:
                return entity
            return create_error_response(
                'Entity not found',
                f"No entity with name '{name}' exists",
                'Check entity name spelling or create the entity first',
            )
        except PyMongoError as e:
            return create_error_response(
                'Database error',
                f'Failed to retrieve entity: {e!s}',
                'Check MongoDB connection and try again',
            )

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
        # Check configuration first
        config_error = self._check_configuration()
        if config_error:
            return config_error

        try:
            database = self.client[self.AGENT_MEMORY_DB]
            collection = database[self.ENTITY_COLLECTION]

            # Add updated_at timestamp if not in update
            if '$set' not in update:
                update['$set'] = {}
            if 'updated_at' not in update['$set']:
                update['$set']['updated_at'] = datetime.now(timezone.utc)

            result = collection.update_one(
                {self.AGENT_MEMORY_INDEX_FIELD: name},
                update,
                upsert=upsert,
            )

            if result.matched_count > 0 or (upsert and result.upserted_id):
                return create_success_response()
            return create_error_response(
                'Entity not found',
                f"No entity with name '{name}' exists",
                'Check entity name or use upsert=True to create if not exists',
            )
        except PyMongoError as e:
            return create_error_response(
                'Database error',
                f'Failed to update entity: {e!s}',
                'Check MongoDB connection and update data format',
            )

    def delete_entity(self, name: str) -> Mapping:
        """Delete a single entity by its name.

        Args:
            name: Unique name of the entity to delete

        Returns:
            Operation result with success status or error
        """
        # Check configuration first
        config_error = self._check_configuration()
        if config_error:
            return config_error

        try:
            database = self.client[self.AGENT_MEMORY_DB]
            collection = database[self.ENTITY_COLLECTION]

            result = collection.delete_one({self.AGENT_MEMORY_INDEX_FIELD: name})

            if result.deleted_count > 0:
                return create_success_response()
            return create_error_response(
                'Entity not found',
                f"No entity with name '{name}' exists",
                'Check entity name spelling',
            )
        except PyMongoError as e:
            return create_error_response(
                'Database error',
                f'Failed to delete entity: {e!s}',
                'Check MongoDB connection and try again',
            )

    def find_entities(self, query: dict[str, Any], limit: int = 10) -> dict[str, Any]:
        """Find entities matching the query criteria.

        Args:
            query: MongoDB query dictionary. Must be a non-empty dictionary.
            limit: Maximum number of entities to return. Defaults to 10.

        Returns:
            Dictionary with entities list or error information

        Raises:
            ValueError: If query is empty or None
            TypeError: If query is not a dictionary
        """
        if not query:
            return create_error_response(
                'Query dictionary cannot be empty',
                'Provide a non-empty query dictionary to search entities',
                'Example: {"type": "user"} or {"name": "entity_name"}',
                entities=[],
            )
        if not isinstance(query, dict):
            return create_error_response(
                'Invalid query type',
                f'Query must be a dictionary, got {type(query).__name__}',
                'Provide a dictionary with search criteria',
                entities=[],
            )

        # Check configuration first
        config_error = self._check_configuration()
        if config_error:
            return config_error

        database = self.client[self.AGENT_MEMORY_DB]
        collection = database[self.ENTITY_COLLECTION]

        try:
            cursor = collection.find(query)
            entities = list(cursor.limit(limit))
        except PyMongoError as e:
            return create_error_response(
                'Database error',
                f'Failed to find entities: {e!s}',
                'Check MongoDB connection and query format',
                entities=[],
            )
        return create_success_response(
            entities=entities,
            count=len(entities),
        )

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
        if not 1 <= limit <= self.MAX_RELATIONSHIPS_LIMIT:
            return create_error_response(
                'Invalid limit value',
                f'Limit must be between 1 and {self.MAX_RELATIONSHIPS_LIMIT}, got {limit}',
                f'Use a value between 1 and {self.MAX_RELATIONSHIPS_LIMIT}',
                relationships=[],
                total_count=0,
                page_info={'has_next': False, 'next_cursor': None},
            )

        if query is not None and not isinstance(query, dict):
            return create_error_response(
                'Invalid query type',
                f'Query must be a dictionary, got {type(query).__name__}',
                'Provide a dictionary with search criteria or None for all relationships',
                relationships=[],
                total_count=0,
                page_info={'has_next': False, 'next_cursor': None},
            )

        # Check configuration first
        config_error = self._check_configuration()
        if config_error:
            return config_error

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
            return create_error_response(
                'Database error',
                f'Failed to get relationships: {e!s}',
                'Check MongoDB connection and try again',
                relationships=[],
                total_count=0,
                page_info={'has_next': False, 'next_cursor': None},
            )

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
        # Check configuration first
        config_error = self._check_configuration()
        if config_error:
            return config_error

        # Validate entities exist
        if not self._get_entity_internal(from_entity):
            return create_error_response(
                'Source entity not found',
                f"Entity '{from_entity}' does not exist",
                'Check entity name spelling or create the entity first',
                acknowledged=False,
                deleted_count=0,
            )
        if not self._get_entity_internal(to_entity):
            return create_error_response(
                'Target entity not found',
                f"Entity '{to_entity}' does not exist",
                'Check entity name spelling or create the entity first',
                acknowledged=False,
                deleted_count=0,
            )

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
                return create_error_response(
                    'Invalid relationship_type format',
                    f'Expected format: "type:key1=value1,key2=value2", got: "{relationship_type}"',
                    'Use format like "works_at:position=developer,department=RnD"',
                    acknowledged=False,
                    deleted_count=0,
                    example='works_at:position=developer,department=RnD',
                )

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
            return create_error_response(
                'Database error',
                f'Failed to delete relationship: {e!s}',
                'Check MongoDB connection and try again',
                acknowledged=False,
                deleted_count=0,
            )
