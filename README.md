# MCP Memory Graph Server

[//]: # ([![PyPI version]&#40;https://badge.fury.io/py/mongo-memory.svg&#41;]&#40;https://badge.fury.io/py/mongo-memory&#41;)
[//]: # ([![Python Version]&#40;https://img.shields.io/pypi/pyversions/mongo-memory.svg&#41;]&#40;https://pypi.org/project/mongo-memory/&#41;)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Overview

The Memory Graph Server provides a persistent storage layer for knowledge graphs, allowing for:

* Storage of entities and their properties
* Management of relationships between entities
* Querying and traversing the graph structure
* Real-time updates and modifications

## Features

* MongoDB-based persistent storage
* Graph operations (create, read, update, delete)
* Entity management
* Relationship handling
* Query capabilities
* Real-time updates

## Installation

### From PyPI

```bash
# Using uv (recommended)
uv pip install mongo-memory

# Using pip
pip install mongo-memory
```

### From Source

```bash
# Clone the repository
git clone https://github.com/yourusername/mongo-memory.git
cd mongo-memory

# Install with uv
uv pip install -e .

# Or with pip
pip install -e .
```

## Configuration

### Setting up a Free MongoDB Atlas Cluster (Quick Start)

If you do not already have a MongoDB instance running, you can spin up a **free** cloud cluster on MongoDB Atlas ([https://cloud.mongodb.com](https://cloud.mongodb.com)) in just a few minutes:

1. **Register / Sign in**
   Open [https://cloud.mongodb.com](https://cloud.mongodb.com) and create an account. You can register with e‑mail or sign in via **Google** or **GitHub**.
2. **Create a Project & Cluster**
   Create a new *Project* (e.g. `mcp-memory`) and choose **Create → Deployment → Create a cluster**.
   Select the **Free Shared (M0)** tier, pick the provider/region closest to you, give the cluster a name and click **Create**.
   Provisioning takes \~2‑3 minutes.
3. **Create a Database User**
   Navigate to **Database Access → Add New Database User**.
   – Choose *Password* authentication.
   – Enter a **Username** (e.g. `mcp_user`) and a strong **Password** (or autogenerate one).
   – For quick tests, give the user **Read and write to any database** privileges (you can tighten this later).
   – Click **Add User** and store the credentials somewhere safe.
4. **Allow Your IP Address**
   Go to **Network Access → Add IP Address** and whitelist the public IP address from which the server will connect.
   You can click **Add Current IP Address** or specify it manually.

   > For demos you may allow `0.0.0.0/0` (all IPs), but **this is not recommended for production**.
5. **Get the Connection String (URI)**
   On the **Database Deployments** screen click **Connect → Drivers**, choose *Python* and copy the URI, which looks like:

   ```
   mongodb+srv://<username>:<password>@<cluster>.mongodb.net/?retryWrites=true&w=majority
   ```

   Replace `<username>`/`<password>` with the credentials from step 3 and optionally append `/<database>` to select the default database, e.g. `/mcp_memory`.
6. **Configure the Memory Graph Server**
   Export the connection string via the environment variable expected by the server:

   ```bash
   export MCP_NONGO_MEMORY_CONNECTION="mongodb+srv://mcp_user:<password>@cluster0.mongodb.net/mcp_memory?retryWrites=true&w=majority"
   ```

   Keep the quotes around the URI so that special characters are preserved, and **never commit this string to version control**.

Now you can launch the server as shown in the [Usage](#usage) section.

### Using Environment Variables Directly

Alternatively, you can set the required environment variable directly:

```
MCP_NONGO_MEMORY_CONNECTION=mongodb://username:password@host:port/database
```

## Usage

### Running as a Standalone Server

```bash
# Using the installed package
mcp-mongo-memory

# Or from the source directory
python -m mongo_memory.cli
```

### Using as MCP Service

Add the following configuration to your `~/.cursor/mcp.json`:

```json
{
  "MongoMemory": {
    "command": "/path/to/.local/bin/uv",
    "args": [
        "--directory",
        "/path/to/working/directory",
        "run",
        "mcp-mongo-memory"
    ],
    "env": {
      "MCP_NONGO_MEMORY_CONNECTION": "mongodb://username:password@host:port/database"
    }
  }
}
```

Replace `/path/to/` with your actual paths.

### Available Operations

Currently implemented operations:

* `create_entities`: Create new entities in the graph. Requires `name` field to be unique.
* `get_entity`: Retrieve a single entity by its name.
* `update_entity`: Update an existing entity by its name.
* `delete_entity`: Delete an entity by its name.
* `find_entities`: Find entities matching query criteria. Requires non-empty query dictionary, returns up to 10 matches by default.
* `create_relationship`: Create a relationship between two entities with optional properties.
* `get_relationships`: Find relationships matching query criteria with pagination support.
* `delete_relationship`: Delete a specific relationship between entities.

Example usage in Python with MCP client:

```python
from mcp.client import MCPClient

client = MCPClient()
memory = client.get_service("MongoMemory")

# Create entities
result = memory.create_entities([
    {"name": "Entity1", "type": "Person", "properties": {"age": 30}},
    {"name": "Entity2", "type": "Location", "properties": {"country": "USA"}}
])

# Create relationship
result = memory.create_relationship(
    from_entity="Entity1",
    to_entity="Entity2",
    relationship_type="lives_in:since=2020"
)

# Find relationships
relationships = memory.get_relationships(limit=5)

# Delete relationship
result = memory.delete_relationship(
    from_entity="Entity1",
    to_entity="Entity2",
    relationship_type="lives_in:since=2020"
)

# Get single entity
entity = memory.get_entity("Entity1")

# Find entities by type (returns up to 10 matches)
entities = memory.find_entities({"type": "Person"})

# Find entities with custom limit
entities = memory.find_entities({"properties.country": "USA"}, limit=5)

# Update entity
result = memory.update_entity(
    "Entity1",
    {"$set": {"properties.age": 31}},
)

# Delete entity
result = memory.delete_entity("Entity2")
```

## Development

See [DEVELOPMENT.md](DEVELOPMENT.md) for development setup and guidelines.

## Architecture

The system consists of several key components:

* MongoDB Connector: Handles all database operations
* Graph Operations: Manages graph structure and operations
* API Layer: Provides interface for client interactions

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
