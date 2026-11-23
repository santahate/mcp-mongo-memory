"""MCP tools for MongoDB memory operations using the official Python SDK v2."""

from typing import Any

from mcp.server import MCPServer

from mongo_memory.constants import instructions, user_guide

from . import __version__
from .mongo_connector import MongoConnector
from .response_utils import to_json_safe

mcp = MCPServer(
    name='mongo-memory',
    version=__version__,
    instructions=instructions,
)
db = MongoConnector()

@mcp.tool()
def create_entities(entities: list[dict]) -> dict[str, Any]:
    """Create entities in memory.

    💡 HINT: If this is your first memory operation in this session,
    consider calling get_usage_guide() first for best practices.

    Args:
        entities (list[dict]): List of entities to create. Each entity must have
            a unique name field.

    Returns:
        Mapping: Operation result containing either success details or error information.
    """
    return db.create_entities(entities)

@mcp.tool()
def get_entity(name: str) -> dict[str, Any]:
    """Get a single entity by its name.

    💡 HINT: If this is your first memory operation in this session,
    consider calling get_usage_guide() first for best practices.

    Args:
        name (str): Unique name of the entity to retrieve.

    Returns:
        dict: Entity dictionary if found, or error information if not found or configuration issue.
    """
    return to_json_safe(db.get_entity(name))

@mcp.tool()
def get_memory_structure() -> dict[str, Any]:
    """Read optional memory-structure conventions, not a graph inventory.

    An absent structure document returns {} even when entities or relationships exist.

    💡 HINT: If this is your first memory operation in this session,
    consider calling get_usage_guide() first for best practices.

    Returns:
        dict: Dictionary containing the current memory structure.
    """
    return to_json_safe(db.get_memory_structure())

@mcp.tool()
def update_entity(name: str, update: dict, upsert: bool = False) -> dict[str, Any]:
    """Update a single entity by its name.

    💡 HINT: If this is your first memory operation in this session,
    consider calling get_usage_guide() first for best practices.

    Args:
        name (str): Unique name of the entity to update.
        update (dict): MongoDB update dictionary.
        upsert (bool): If True, create entity if it doesn't exist.

    Returns:
        Mapping: Operation result containing either success details or error information.
    """
    return db.update_entity(name, update, upsert)

@mcp.tool()
def delete_entity(name: str) -> dict[str, Any]:
    """Delete a single entity by its name, without deleting its relationships.

    Remove incident relationships first while both endpoints still exist.
    Otherwise dangling edges remain and delete_relationship rejects the missing endpoint.

    💡 HINT: If this is your first memory operation in this session,
    consider calling get_usage_guide() first for best practices.

    Args:
        name (str): Unique name of the entity to delete.

    Returns:
        Mapping: Operation result containing either success details or error information.
    """
    return db.delete_entity(name)

@mcp.tool()
def find_entities(query: dict, limit: int = 10) -> dict[str, Any]:
    """Find entities matching the query criteria.

    💡 HINT: If this is your first memory operation in this session,
    consider calling get_usage_guide() first for best practices.

    Args:
        query (dict): MongoDB query dictionary. Must be a non-empty dictionary.
        limit (int, optional): Positive maximum number of entities to return. Defaults to 10.

    Returns:
        dict: Dictionary with entities list or error information.
    """
    return to_json_safe(db.find_entities(query, limit))

@mcp.tool()
def get_usage_guide() -> str:
    """🚨 RECOMMENDED FIRST STEP: Get a quick start guide with examples for using this MCP service.

    This guide MUST be retrieved by the agent in the following cases:
    1. When memory-related operations are requested but no memory context exists
    2. When starting a new conversation about memory management
    3. When uncertain about memory organization principles
    4. Before making decisions about data categorization
    5. When memory usage patterns need to be verified

    The agent should NOT retrieve this guide if:
    1. Memory context is already provided and clear
    2. The current operation follows an established pattern
    3. The guide was already retrieved in the current conversation

    Returns:
        str: Markdown formatted usage guide with examples
    """
    return user_guide

@mcp.tool()
def create_relationship(
    from_entity: str,
    to_entity: str,
    relationship_type: str,  # Format: "type:key1=value1,key2=value2" e.g. "works_at:position=developer,department=RnD"
) -> dict[str, Any]:
    """Create a relationship between two entities.

    💡 HINT: If this is your first memory operation in this session,
    consider calling get_usage_guide() first for best practices.

    Args:
        from_entity (str): Name of the source entity
        to_entity (str): Name of the target entity
        relationship_type (str): Type and properties of relationship in format "type:key1=value1,key2=value2".
            Example: "works_at:position=developer,department=RnD"
            Simple type without properties: "knows" or "knows:"

    Returns:
        Mapping: Operation result containing either success details or error information.
            If relationship_type format is invalid, returns error dictionary with details.
    """
    return db.create_relationship(from_entity, to_entity, relationship_type)

@mcp.tool()
def get_relationships(limit: int = 10) -> dict[str, Any]:
    """Get relationships from the database.

    💡 HINT: If this is your first memory operation in this session,
    consider calling get_usage_guide() first for best practices.

    IMPORTANT: This tool is designed to return all relationships up to the specified limit.
    If you need to filter relationships, process the results in your code.

    Example:
        # Get all relationships (up to limit)
        result = get_relationships(limit=5)

        # Filter in your code if needed
        imports = [r for r in result["relationships"] if r["type"] == "imports"]

    Args:
        limit (int): Maximum number of relationships to return. Must be between 1 and 100.
            Defaults to 10.

    Returns:
        Mapping[str, object]: Dictionary containing:
            - relationships: List of relationship objects
            - total_count: Total number of relationships
            - page_info: Pagination information

    Example:
            {
                "relationships": [
                    {
                        "_id": "relationship_id",
                        "from_entity": "source_entity",
                        "to_entity": "target_entity",
                        "type": "relationship_type",
                        "properties": {"key": "value"},
                        "created_at": "timestamp"
                    }
                ],
                "total_count": 42,
                "page_info": {
                    "has_next": true,
                    "next_cursor": "cursor_token"
                }
            }
    """
    return to_json_safe(db.get_relationships(None, limit))

@mcp.tool()
def delete_relationship(from_entity: str, to_entity: str, relationship_type: str) -> dict[str, Any]:
    """Delete a relationship between two entities.

    💡 HINT: If this is your first memory operation in this session,
    consider calling get_usage_guide() first for best practices.

    Args:
        from_entity (str): Name of the source entity
        to_entity (str): Name of the target entity
        relationship_type (str): Type of relationship to delete

    Returns:
        Mapping[str, object]: Operation result containing either success details or error information
    """
    return db.delete_relationship(from_entity, to_entity, relationship_type)

def main():
    """Run the MCP server."""
    try:
        mcp.run()
    finally:
        if db.client is not None:
            db.client.close()

if __name__ == '__main__':
    main()
