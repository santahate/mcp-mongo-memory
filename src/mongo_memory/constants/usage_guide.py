user_guide = """# MongoDB Memory MCP Service Quick Start Guide
## Getting started with memory structure

### Obtaining memory structure

`get_memory_structure` reads optional conventions from the historical `memory.sys`
structure document. It is not a graph inventory or an enforced entity schema.
An absent structure document does not mean that entities or relationships are absent.
Check stored entities and relationships using their respective read tools.

```python
# First I'll learn the memory structure
memory_structure = get_memory_structure()
# {} means no structure document, not an empty graph.
# Entities and relationships may already exist; do not overwrite or ignore them.
# Configuration/database failures return a dictionary with success=False.

# Use any saved conventions when building queries.
# These are suggested entity types, not a list of stored entities.
entity_types = memory_structure.get("entity_types", [])
```

### Importance of memory structure

- Always check the memory structure before starting work
- Learn available entity types
- Study supported programming languages
- Check possible entity roles
- Use knowledge of the structure for correct query building
- Ensure that the entity type corresponds to the structure
- Use correct values for fields
- Build queries based on known structure

## Agent Memory Guidelines

### Key Principles
1. **Always Store Important Information**
   - Record all significant user interactions
   - Save discovered facts and relationships
   - Track user preferences and patterns
   - Store context of conversations

2. **Check Memory Before Acting**
   - Review past interactions with user
   - Consider user preferences
   - Look for relevant context
   - Verify existing relationships

3. **Maintain Memory Structure**
   - Use consistent naming patterns
   - Include categorization markers (time/task/topic)
   - Track relationships between entities
   - Store confidence levels when applicable

4. **Always Clarify Context**
   - Ask user about categorization preference
   - Verify current task/context is still active
   - Use provided context if available
   - Maintain context consistency

### Important Notes for Agents

1. **Context Verification**
   - ALWAYS ask user how to categorize information unless context is provided
   - Example questions:
     - "How would you like me to categorize this information? By time, task number, topic, or something else?"
     - "Should I associate this with the current task #734?"
     - "Would you like me to group this with other observations about X?"

2. **Context Awareness**
   - If context is provided in memory, DO NOT ask for categorization
   - Example context structure:
     ```python
     context = {
         "task_id": "734",
         "topic": "memory_management",
         "categorization": "by_task"  # Tells agent how to categorize
     }
     ```
   - When context exists, use it automatically
   - Only ask if context is missing or unclear

### Memory Usage Examples

```python
# Store user interaction with context verification
# ask_user_for_categorization() is a host-agent callback, not an MCP tool.
# The application must implement it to ask the user and return a category string.
def remember_interaction(user_id: str, interaction_data: dict, context: dict | None = None):
    context = context or {}
    category_marker = (
        context.get("category_marker")
        or context.get("task_id")
        or context.get("topic")
        or context.get("categorization")
        or ask_user_for_categorization()
    )

    memory.update_entity(
        f"interaction_{user_id}_{category_marker}",
        {"$set": {
            "type": "user_interaction",
            "data": {
                **interaction_data,
                "category": category_marker,
                "context": context
            }
        }},
        upsert=True
    )

# Store observation with custom categorization
def remember_observation(observation: dict, category_type: str, category_value: str):
    memory.create_entities([{
        "name": f"obs_{category_type}_{category_value}_{hash(str(observation))}",
        "type": "observation",
        "data": {
            **observation,
            "category_type": category_type,    # e.g. "task", "topic", "time"
            "category_value": category_value,   # e.g. "734", "memory_mgmt", "2024-03-20"
        }
    }])

# Get observations by category
def get_observations_by_category(category_type: str, category_value: str) -> list:
    result = memory.find_entities({
        "type": "observation",
        "data.category_type": category_type,
        "data.category_value": category_value
    })
    return result.get("entities", [])

# Store fact with context awareness
def remember_fact(topic: str, fact: str, source: str, context: dict | None = None):
    context = context or {}
    category = (
        context.get("category_marker")
        or context.get("task_id")
        or context.get("topic")
        or context.get("categorization")
        or ask_user_for_categorization()  # Host-agent callback described above
    )

    memory.create_entities([{
        "name": f"fact_{category}_{hash(fact)}",
        "type": "fact",
        "data": {
            "topic": topic,
            "content": fact,
            "source": source,
            "category": category
        }
    }])
```

## Basic Operations

Missing entities and invalid inputs return `{"success": false, "error": ..., "message": ...}`.
Entity reads contain BSON values encoded as Extended JSON, e.g. `{"$oid": "..."}`
and `{"$date": "..."}`. Batch insertion is not atomic; a bulk-write failure
includes `created`, the number already inserted. Inspect the data before retrying.

### Create Entities
```python
# Create single entity
result = memory.create_entities([{
    "name": "user1",  # Required, must be unique
    "type": "user",   # Optional, useful for filtering
    "data": {         # Any custom data
        "age": 25,
        "city": "New York"
    }
}])

# Create multiple entities
result = memory.create_entities([
    {
        "name": "user2",
        "type": "user",
        "data": {"age": 30, "city": "London"}
    },
    {
        "name": "company1",
        "type": "company",
        "data": {"employees": 100}
    }
])
```

### Get Entity
```python
# Get entity by name
entity = memory.get_entity("user1")
```

### Update Entity
```python
# Update entity fields
result = memory.update_entity(
    "user1",
    {"$set": {"data.age": 26}}
)

# Add new fields
result = memory.update_entity(
    "user1",
    {"$set": {"data.skills": ["Python", "MongoDB"]}}
)

# Update with upsert (create if not exists)
result = memory.update_entity(
    "new_user",
    {"$set": {"type": "user", "data": {"age": 20}}},
    upsert=True
)
```

### Find Entities
```python
# Find by type (the result is an envelope, not a bare list)
result = memory.find_entities({"type": "user"})
users = result.get("entities", [])

# Find by field value
young_users = memory.find_entities({
    "type": "user",
    "data.age": {"$lt": 25}
})

# Find with custom limit
companies = memory.find_entities(
    {"type": "company"},
    limit=5
)
```

### Relationships

Entities and relationships are stored in separate collections. `find_entities`
searches only entities: even filtering by `type="relationship"` does not retrieve
edges created with `create_relationship`. Use the relationship tools instead.
Both endpoint entities must exist when creating or deleting a relationship.

```python
# user1 and company1 must already exist.
result = memory.create_relationship(
    "user1", "company1", "works_at:position=developer"
)

# MCP accepts only limit (1..100), not a query or cursor.
result = memory.get_relationships(limit=100)
relations = result.get("relationships", [])
user1_relations = [
    rel for rel in relations
    if "user1" in (rel["from_entity"], rel["to_entity"])
]

# Use the same type and properties to remove this edge.
result = memory.delete_relationship(
    "user1", "company1", "works_at:position=developer"
)
```

Filtering this bounded list is not a complete graph traversal. If `total_count`
is greater than the returned list length, the list is incomplete. Do not claim
that all incident edges have been found. There is no supported cursor argument.

### Delete Entity

`delete_entity` deletes only the entity. It does **not** cascade to incoming or
outgoing relationships. Remaining edges reference a missing endpoint, and
`delete_relationship` rejects missing endpoints. For clean removal, delete
incident relationships **before** deleting their endpoint entities, and verify
the results. A bounded relationship listing cannot prove complete cleanup when
some relationships were not returned.

```python
# Only after relevant relationships have been removed and checked:
result = memory.delete_entity("user1")
# Existing entity: {"success": True}; missing entity: success=False.
# This response does not include deleted_count.
```

## Memory Organization Tips

1. **Entity Naming**
   - Use descriptive entity prefixes (user_, fact_, decision_, constraint_)
   - Include category markers in names
   - Keep names unique but readable
   - Use consistent categorization format

2. **Data Structure**
   - Store core data in 'data' field
   - Include categorization information
   - Use consistent field names
   - Add type field for filtering

3. **Categorization**
   - Support multiple categorization types:
     - By time (default if nothing specified)
     - By task number
     - By topic
     - By user-defined category
   - Always include category in metadata
   - Make categories searchable
   - Allow multiple categories if needed

4. **Context Management**
   - Store active context with each entity
   - Update context when user indicates changes
   - Use context for automatic categorization
   - Maintain context history

5. **Relationships**
   - Create explicit edges with create_relationship, not duplicate relationship entities
   - Read edges with get_relationships and remove them with delete_relationship
   - Each edge is directed; create a reverse edge only when it has useful meaning
   - Include supported metadata as type:key=value properties
   - Remove incident edges before deleting or renaming their endpoint entities

6. **Memory Maintenance**
   - Update outdated information
   - Remove obsolete relationships
   - Keep context current
   - Maintain reasonable history depth

7. **Best Practices**
   - Always check memory before responding
   - Store context with every interaction
   - Track confidence levels
   - Include data sources
   - Maintain temporal information

## Common Patterns
```python
# Ensure entity exists
def ensure_entity(name: str, data: dict):
    return memory.update_entity(
        name,
        {"$set": data},
        upsert=True
    )

# Process entities in batches
def process_entities(entity_type: str):
    result = memory.find_entities({"type": entity_type})
    for entity in result.get("entities", []):
        # Process each entity
        pass

# Get bounded context (not a complete graph traversal)
def get_bounded_context(entity_name: str) -> dict:
    # Get entity
    entity = memory.get_entity(entity_name)

    # MCP exposes only a bounded relationship listing, not a query or cursor.
    # This example may be incomplete when there are more than 100 relationships.
    result = memory.get_relationships(limit=100)
    relations = [
        rel for rel in result.get("relationships", [])
        if entity_name in (rel["from_entity"], rel["to_entity"])
    ]

    # Get related entities
    related = []
    for rel in relations:
        if rel["from_entity"] == entity_name:
            related.append(memory.get_entity(rel["to_entity"]))
        else:
            related.append(memory.get_entity(rel["from_entity"]))

    return {
        "entity": entity,
        "relationships": relations,
        "related_entities": related
    }
```
"""
