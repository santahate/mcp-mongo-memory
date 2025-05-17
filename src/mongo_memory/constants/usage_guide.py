user_guide = """# MongoDB Memory MCP Service Quick Start Guide
## Getting started with memory structure

### Obtaining memory structure

Before working with memory, it's necessary to get and study its structure:

```python
# First I'll learn the memory structure
memory_structure = get_memory_structure()

# Now I know the memory structure and can build queries based on it
# For example, I can determine which entity types are supported
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
def remember_interaction(user_id: str, interaction_data: dict, context: dict = None):
    # If no context provided, agent should ask user:
    # "How would you like me to categorize this interaction?"
    
    category_marker = (
        context.get("category_marker")  # Use existing context if available
        or "task_123"                   # Or use what user specified
        or "time_" + current_time       # Or default to timestamp
    )
    
    memory.update_entity(
        f"interaction_{user_id}_{category_marker}",
        {"$set": {
            "type": "user_interaction",
            "data": {
                **interaction_data,
                "category": category_marker,
                "context": context or "current_context"
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
    return memory.find_entities({
        "type": "observation",
        "data.category_type": category_type,
        "data.category_value": category_value
    })

# Store fact with context awareness
def remember_fact(topic: str, fact: str, source: str, context: dict = None):
    category = (
        context.get("categorization")
        or ask_user_for_categorization()  # Agent should implement this
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
# Find by type
users = memory.find_entities({"type": "user"})

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

### Delete Entity
```python
# Delete by name
result = memory.delete_entity("user1")
```

## Memory Organization Tips

1. **Entity Naming**
   - Use descriptive prefixes (user_, fact_, rel_)
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
   - Create explicit relationship entities
   - Use bidirectional relationships when needed
   - Include relationship metadata
   - Track relationship discovery context

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
    entities = memory.find_entities({"type": entity_type})
    for entity in entities:
        # Process each entity
        pass

# Get full context
def get_full_context(entity_name: str) -> dict:
    # Get entity
    entity = memory.get_entity(entity_name)
    
    # Get relationships
    relations = memory.find_entities({
        "type": "relationship",
        "$or": [
            {"data.from": entity_name},
            {"data.to": entity_name}
        ]
    })
    
    # Get related entities
    related = []
    for rel in relations:
        if rel["data"]["from"] == entity_name:
            related.append(memory.get_entity(rel["data"]["to"]))
        else:
            related.append(memory.get_entity(rel["data"]["from"]))
    
    return {
        "entity": entity,
        "relationships": relations,
        "related_entities": related
    }
```
"""
