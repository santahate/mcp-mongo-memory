# Development Guide

## Project Structure

```
.
├── main.py              # Main application entry point
├── mongo_connector.py   # MongoDB connection and operations
├── requirements.txt     # Project dependencies
├── pyproject.toml      # Project metadata and core dependencies
├── uv.lock            # Locked dependencies versions
└── .env                # Environment configuration
```

## Development Environment Setup

1. Install uv:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

2. Create and activate virtual environment:
```bash
uv venv
source .venv/bin/activate  # On Unix-like systems
# or
.venv\Scripts\activate     # On Windows
```

3. Install dependencies:
```bash
uv pip install -r requirements.txt
```

4. Install development dependencies:
```bash
uv pip install pytest pytest-cov black mypy ruff
```

## MCP Service Development

### Running as MCP Service

The server can be run as an MCP service using the following command:
```bash
uv run --with mcp[cli] --with pymongo mcp run main.py
```

### Adding New Operations

1. Define new operation in `main.py`:
```python
@mcp.tool()
def operation_name(param1: type1, param2: type2) -> return_type:
    """Operation description"""
    return db.operation_name(param1, param2)
```

2. Implement operation in `mongo_connector.py`:
```python
def operation_name(self, param1: type1, param2: type2) -> return_type:
    """Implementation details"""
    # Implementation
```

3. Add tests for both the MCP interface and MongoDB implementation

4. Update documentation with new operation details

## Development Plan

### Phase 1: Core Infrastructure (Current)
- [x] Basic MongoDB connection
- [x] Environment configuration
- [x] Basic entity operations
- [x] Memory usage guidelines
- [ ] Basic relationship operations
- [ ] Unit tests setup

### Phase 2: Graph Operations
- [ ] Advanced entity operations
  - [ ] Batch operations
  - [ ] Complex queries
  - [ ] Validation
- [ ] Advanced relationship operations
  - [ ] Bidirectional relationships
  - [ ] Relationship properties
  - [ ] Relationship validation
- [ ] Graph traversal operations
  - [ ] Path finding
  - [ ] Subgraph extraction
  - [ ] Graph analytics

### Phase 3: API and Integration
- [ ] REST API implementation
- [ ] WebSocket support for real-time updates
- [ ] Authentication and authorization
- [ ] Rate limiting
- [ ] API documentation
- [ ] Integration tests

### Phase 4: Performance and Scaling
- [ ] Caching layer
- [ ] Query optimization
- [ ] Index optimization
- [ ] Bulk operations
- [ ] Sharding strategy
- [ ] Performance monitoring

### Phase 5: Additional Features
- [ ] Graph versioning
- [ ] Audit logging
- [ ] Data export/import
- [ ] Backup/restore functionality
- [ ] Admin interface
- [ ] Memory analytics dashboard

## Memory Management Guidelines

### Entity Structure Best Practices

1. **Consistent Naming**
   - Use descriptive prefixes for entity types
   - Follow consistent naming patterns
   - Include relevant identifiers

2. **Temporal Tracking**
   - Always include creation timestamps
   - Track last modification time
   - Maintain update history when relevant

3. **Contextual Information**
   - Store relevant context with entities
   - Include source of information
   - Track confidence levels

4. **Relationship Management**
   - Use explicit relationship entities
   - Track relationship types
   - Include relationship metadata

### Memory Usage Patterns

1. **Information Storage**
```python
def store_observation(observation_type: str, data: dict):
    """Store new observation with context."""
    return db.create_entities([{
        "name": f"obs_{observation_type}_{uuid.uuid4()}",
        "type": "observation",
        "data": {
            **data,
            "observed_at": datetime.now(),
            "confidence": calculate_confidence(data)
        }
    }])
```

2. **Context Retrieval**
```python
def get_relevant_context(query: dict) -> list[dict]:
    """Get context-relevant information."""
    return db.find_entities({
        **query,
        "data.created_at": {
            "$gte": datetime.now() - timedelta(days=7)
        }
    })
```

3. **Relationship Tracking**
```python
def track_relationship(
    from_entity: str,
    to_entity: str,
    rel_type: str,
    metadata: dict
):
    """Track relationship between entities."""
    return db.create_entities([{
        "name": f"rel_{from_entity}_{to_entity}_{rel_type}",
        "type": "relationship",
        "data": {
            "from": from_entity,
            "to": to_entity,
            "type": rel_type,
            "metadata": metadata,
            "created_at": datetime.now()
        }
    }])
```

### Memory Maintenance

1. **Regular Cleanup**
   - Archive old data
   - Remove obsolete relationships
   - Update confidence scores

2. **Consistency Checks**
   - Validate relationship integrity
   - Check for orphaned entities
   - Ensure temporal consistency

3. **Performance Optimization**
   - Index frequently queried fields
   - Optimize query patterns
   - Monitor memory usage

## MongoDB Optimization Principles

### Offloading Operations to MongoDB
The project follows a key principle of maximizing the use of MongoDB's native capabilities to minimize computational load on the AI agent:

1. **Query Operations**
   - Use MongoDB aggregation pipeline for complex queries
   - Implement server-side filtering and sorting
   - Utilize MongoDB's text search capabilities
   - Apply proper indexing strategies

2. **Data Processing**
   - Perform data aggregation on MongoDB level
   - Use MongoDB's built-in operators for calculations
   - Implement pagination on database level
   - Utilize MongoDB's projection to return only necessary fields

3. **Benefits**
   - Reduced context window usage for AI agent
   - Minimized memory footprint
   - Improved query performance
   - Better scalability
   - Reduced network traffic

### Implementation Guidelines
```python
# Instead of:
def get_filtered_entities(self, criteria: dict) -> List[Entity]:
    """Bad: Fetches all entities and filters in Python"""
    entities = self.db.entities.find({})
    return [e for e in entities if self._matches_criteria(e, criteria)]

# Do this:
def get_filtered_entities(self, criteria: dict) -> List[Entity]:
    """Good: Filters directly in MongoDB"""
    return list(self.db.entities.find(criteria))
```

## Technical Specifications

### Entity Structure
```python
{
    "_id": ObjectId,
    "name": str,
    "type": str,
    "properties": dict,
    "created_at": datetime,
    "updated_at": datetime,
    "searchable_text": str,  # For text search optimization
    "metadata": {
        "last_accessed": datetime,
        "access_count": int,
        "version": int
    }
}
```

### Relationship Structure
```python
{
    "_id": ObjectId,
    "from_entity": ObjectId,
    "to_entity": ObjectId,
    "type": str,
    "properties": dict,
    "created_at": datetime,
    "updated_at": datetime
}
```

### Indexes
- `entities`: 
  - `name` (unique)
  - `type`
  - `searchable_text` (text index)
  - `properties.key` (for frequently queried properties)
  - `created_at`
- `relationships`:
  - `(from_entity, to_entity, type)` (unique compound)
  - `from_entity`
  - `to_entity`
  - `type`
  - `properties.key` (for frequently queried properties)

### Query Optimization Examples
```python
# Example of optimized aggregation pipeline
def get_entity_statistics(self, entity_type: str) -> Dict:
    """Gets entity statistics using MongoDB aggregation"""
    return self.db.entities.aggregate([
        {"$match": {"type": entity_type}},
        {"$group": {
            "_id": None,
            "count": {"$sum": 1},
            "avg_connections": {"$avg": "$metadata.connections_count"},
            "latest_update": {"$max": "$updated_at"}
        }}
    ]).next()
```

## Database Design

### Collections
- `entities`: Stores all entities
- `relationships`: Stores all relationships
- `metadata`: Stores graph metadata and configuration

## Testing Strategy

1. Unit Tests
   - Entity operations
   - Relationship operations
   - Graph operations
   - Validation logic

2. Integration Tests
   - API endpoints
   - Database operations
   - Real-time updates

3. Performance Tests
   - Load testing
   - Stress testing
   - Scalability testing

## Development Workflow

1. Create a new branch for your feature
2. Write tests first (TDD approach)
3. Implement the feature
4. Run tests:
```bash
pytest
```

5. Run linters and type checks:
```bash
ruff check .
black .
mypy .
```

6. Update documentation if needed
7. Submit pull request

## Code Style

- Follow PEP 8
- Use type hints
- Document all public functions and classes
- Keep functions small and focused
- Write meaningful commit messages

## Common Development Tasks

### Adding New Dependencies

```bash
uv pip install package_name
uv pip freeze > requirements.txt
```

### Running Tests with Coverage

```bash
pytest --cov=src tests/
```

### Formatting Code

```bash
black .
```

### Type Checking

```bash
mypy .
```

### Linting

```bash
ruff check .
```