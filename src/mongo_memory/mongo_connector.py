"""MongoDB connector for agent memory operations."""

from datetime import UTC, datetime
import os
from types import TracebackType
from typing import Any

from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.errors import BulkWriteError, DuplicateKeyError, PyMongoError

from .response_utils import create_error_response, create_success_response

DUPLICATE_KEY_CODE = 11000


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

    def _is_configured(self) -> bool:
        """Check if MongoDB connector is properly configured.

        Returns:
            True if configured and connected, False otherwise
        """
        return self.config_error is None and self.client is not None

    def _get_configuration_status(self) -> dict[str, Any]:
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
        if not self._is_configured():
            return self._get_configuration_status()
        return None

    def get_connection(self) -> MongoClient:
        """Get MongoDB client connection.

        Returns:
            MongoDB client instance
        """
        return MongoClient(self.mongo_uri, serverSelectionTimeoutMS=5000)

    def __init__(self) -> None:
        """Initialize MongoDB connector with default settings and connection."""
        self.AGENT_MEMORY_DB = 'agent_memory'
        self.AGENT_MEMORY_INDEX_FIELD = 'name'
        self.AGENT_MEMORY_DESCRIPTION_FIELD = 'description'
        self.ENTITY_COLLECTION = 'entities'
        self.SYSTEM_MEMORY_DB = 'memory'
        self.MAX_RELATIONSHIPS_LIMIT = 100
        self.config_error = None
        self.client = None

        env_result = self._load_envs()
        if not env_result['success']:
            # Store configuration error for later retrieval
            self.config_error = env_result
            self.client = None
            return

        try:
            self.client = self.get_connection()
            # Honor the database selected in the URI; retain the historical default.
            self.AGENT_MEMORY_DB = self.client.get_default_database('agent_memory').name
            self.client.admin.command('ping')
            self.init_entity_rules()
            self._create_relationship_indexes(self.client[self.AGENT_MEMORY_DB]['relationships'])
        except PyMongoError:
            self.config_error = create_error_response(
                'MongoDB initialization failed',
                'Could not connect to MongoDB or initialize collections and indexes',
                'Check the URI, network access, database permissions and existing data/indexes',
            )

    def __enter__(self) -> 'MongoConnector':
        """Context manager entry.

        Returns:
            Self instance
        """
        return self

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
        collections = validation_info['cursor']['firstBatch']
        return bool(collections and collections[0].get('options', {}).get('validator'))

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

    def _validate_entity(self, entity: dict[str, Any]) -> None:
        """Validate entity structure before insertion attempt.

        Args:
            entity: Entity data to validate

        Raises:
            ValueError: If the required name field is missing
            TypeError: If the entity or its name has an invalid type
        """
        if not isinstance(entity, dict):
            msg = 'Each entity must be a dictionary'
            raise TypeError(msg)
        # Check required fields
        if self.AGENT_MEMORY_INDEX_FIELD not in entity:
            msg = f'Missing required field: {self.AGENT_MEMORY_INDEX_FIELD}'
            raise ValueError(msg)

        # Validate field types
        if not isinstance(entity[self.AGENT_MEMORY_INDEX_FIELD], str):
            msg = f'Field {self.AGENT_MEMORY_INDEX_FIELD} must be a string'
            raise TypeError(msg)

    def init_entity_rules(self) -> None:
        """Initialize validation rules and indexes for entities."""
        database = self.client[self.AGENT_MEMORY_DB]
        collection = database[self.ENTITY_COLLECTION]

        # create_index is idempotent and verifies the exact index specification.
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
        config_error = self._check_configuration()
        if config_error:
            return config_error

        try:
            collection = self.client[self.SYSTEM_MEMORY_DB]['sys']
            return collection.find_one({'structure': True}, {'_id': 0, 'structure': 0}) or {}
        except PyMongoError as e:
            return create_error_response(
                'Database error',
                f'Failed to retrieve memory structure: {e!s}',
                'Check MongoDB connection and try again',
            )

    def create_entities(self, entities: list[dict[str, Any]]) -> dict[str, Any]:
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
            if not isinstance(entities, list) or not entities:
                return create_error_response('Invalid entities', 'Provide a non-empty list of entity dictionaries', created=0)
            # Validate the entire batch before writing anything.
            for entity in entities:
                self._validate_entity(entity)

            collection = self.client[self.AGENT_MEMORY_DB][self.ENTITY_COLLECTION]
            now = datetime.now(UTC)
            documents = [{**entity, 'created_at': now, 'updated_at': now} for entity in entities]
            result = collection.insert_many(documents)
            return create_success_response(created=len(result.inserted_ids))
        except (ValueError, TypeError) as e:
            return create_error_response('Invalid entity structure', str(e), created=0)
        except BulkWriteError as e:
            errors = e.details.get('writeErrors', [])
            duplicate = bool(errors) and all(error['code'] == DUPLICATE_KEY_CODE for error in errors)
            return create_error_response(
                'Duplicate key error' if duplicate else 'Database error',
                'Batch insertion stopped; some entities may already have been inserted',
                'Inspect the inserted entities before retrying; batch insertion is not atomic',
                created=e.details.get('nInserted', 0),
            )
        except PyMongoError as e:
            return create_error_response(
                'Database error',
                f'Failed to create entities: {e!s}',
                'Check MongoDB connection and entity data format; insertion may be partial',
            )

    def create_relationship(
        self,
        from_entity: str,
        to_entity: str,
        relationship_type: str,
        properties: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create a relationship between two entities.

        Args:
            from_entity: Source entity name
            to_entity: Target entity name
            relationship_type: Type of relationship
            properties: Optional properties for the relationship

        Returns:
            Operation result containing success details or error information
        """
        # Check configuration first
        config_error = self._check_configuration()
        if config_error:
            return config_error

        try:
            rel_type, parsed_properties = self._parse_relationship_type(relationship_type)
            rel_properties = {**(properties or {}), **parsed_properties}
            for role, name in (('Source', from_entity), ('Target', to_entity)):
                if not self._get_entity_internal(name):
                    return create_error_response(f'{role} entity not found', f"Entity '{name}' does not exist")

            collection = self.client[self.AGENT_MEMORY_DB]['relationships']
            relationship = {
                'from_entity': from_entity,
                'to_entity': to_entity,
                'type': rel_type,
                'properties': rel_properties,
                'created_at': datetime.now(UTC),
            }
            result = collection.insert_one(relationship)
            return create_success_response(
                acknowledged=result.acknowledged,
                inserted_id=str(result.inserted_id),
            )
        except (ValueError, TypeError) as e:
            return create_error_response('Invalid relationship_type format', str(e))
        except DuplicateKeyError:
            return create_error_response('Duplicate key error', 'This relationship already exists')
        except PyMongoError as e:
            return create_error_response(
                'Database error',
                f'Failed to create relationship: {e!s}',
                'Check MongoDB connection and relationship data',
            )

    @staticmethod
    def _parse_relationship_type(relationship_type: str) -> tuple[str, dict[str, str]]:
        """Parse the shared create/delete format, rejecting malformed properties."""
        if not isinstance(relationship_type, str):
            msg = 'relationship_type must be a string'
            raise TypeError(msg)
        rel_type, _, text = relationship_type.partition(':')
        if not rel_type.strip():
            msg = 'Relationship type cannot be empty'
            raise ValueError(msg)
        properties = {}
        if text:
            for prop in text.split(','):
                key, separator, value = prop.partition('=')
                if not separator or not key.strip():
                    msg = 'Expected format: type:key1=value1,key2=value2'
                    raise ValueError(msg)
                properties[key.strip()] = value.strip()
        return rel_type.strip(), properties

    def _create_relationship_indexes(self, collection: Collection) -> None:
        """Create required indexes for relationships collection.

        Args:
            collection: MongoDB collection for relationships
        """
        # Create individual indexes
        collection.create_index([('from_entity', 1)])
        collection.create_index([('to_entity', 1)])
        collection.create_index([('type', 1)])
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
        if not self._is_configured():
            return None

        database = self.client[self.AGENT_MEMORY_DB]
        collection = database[self.ENTITY_COLLECTION]

        return collection.find_one({self.AGENT_MEMORY_INDEX_FIELD: name})

    def get_entity(self, name: str) -> dict[str, Any]:
        """Get a single entity by its name.

        Args:
            name: Unique name of the entity to retrieve

        Returns:
            Dictionary with entity data or error information
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
    ) -> dict[str, Any]:
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

            if (
                not isinstance(update, dict)
                or not update
                or any(not isinstance(key, str) or not key.startswith('$') for key in update)
                or not isinstance(update.get('$set', {}), dict)
            ):
                return create_error_response('Invalid update', 'Provide a non-empty operator update; $set must be a dictionary')
            # Copy before adding timestamps so callers can safely reuse their input.
            now = datetime.now(UTC)
            update = {**update, '$set': dict(update.get('$set', {}))}
            update['$set'].setdefault('updated_at', now)
            # Default creation time atomically on insert, without conflicting with caller operators.
            if upsert and not any(
                isinstance(fields, dict)
                and ('created_at' in fields or (operator == '$rename' and 'created_at' in fields.values()))
                for operator, fields in update.items()
            ):
                update['$setOnInsert'] = {**update.get('$setOnInsert', {}), 'created_at': now}

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
        except (TypeError, ValueError) as e:
            return create_error_response('Invalid update', str(e))
        except PyMongoError as e:
            return create_error_response(
                'Database error',
                f'Failed to update entity: {e!s}',
                'Check MongoDB connection and update data format',
            )

    def delete_entity(self, name: str) -> dict[str, Any]:
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
            limit: Positive maximum number of entities to return. Defaults to 10.

        Returns:
            Dictionary with entities list or error information
        """
        if type(limit) is not int or limit < 1:
            return create_error_response('Invalid limit value', 'Limit must be a positive integer', entities=[])
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
        query: dict[str, Any] | None = None,
        limit: int = 10,
    ) -> dict[str, Any]:
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
            dict: Relationships, total_count and informational page_info.
                No cursor argument is implemented yet.
        """
        if type(limit) is not int or not 1 <= limit <= self.MAX_RELATIONSHIPS_LIMIT:
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

            return create_success_response(
                relationships=relationships,
                total_count=total_count,
                page_info={
                    'has_next': has_next,
                    'next_cursor': str(relationships[-1]['_id']) if has_next and relationships else None,
                },
            )
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
    ) -> dict[str, Any]:
        """Delete a specific relationship between entities.

        Args:
            from_entity (str): Source entity name
            to_entity (str): Target entity name
            relationship_type (str): Type of relationship to delete

        Returns:
            dict: Success/acknowledgement and deletion count, or error information.
        """
        # Check configuration first
        config_error = self._check_configuration()
        if config_error:
            return config_error

        try:
            rel_type, properties = self._parse_relationship_type(relationship_type)
            for role, name in (('Source', from_entity), ('Target', to_entity)):
                if not self._get_entity_internal(name):
                    return create_error_response(
                        f'{role} entity not found', f"Entity '{name}' does not exist",
                        acknowledged=False, deleted_count=0,
                    )
            query = {
                'from_entity': from_entity,
                'to_entity': to_entity,
                'type': rel_type,
            }
            if properties:
                query['properties'] = properties  # Match exact properties object
            collection = self.client[self.AGENT_MEMORY_DB]['relationships']
            result = collection.delete_one(query)

            return create_success_response(
                acknowledged=result.acknowledged,
                deleted_count=result.deleted_count,
            )
        except (ValueError, TypeError) as e:
            return create_error_response('Invalid relationship_type format', str(e), acknowledged=False, deleted_count=0)
        except PyMongoError as e:
            return create_error_response(
                'Database error',
                f'Failed to delete relationship: {e!s}',
                'Check MongoDB connection and try again',
                acknowledged=False,
                deleted_count=0,
            )
