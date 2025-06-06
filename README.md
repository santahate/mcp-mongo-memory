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

## Configuration

### Setting up a Free MongoDB Atlas Cluster (Quick Start)

If you do not already have a MongoDB instance running, you can spin up a **free** cloud cluster on MongoDB Atlas ([https://cloud.mongodb.com](https://cloud.mongodb.com)) in just a few minutes:

1. **Register / Sign in**
   Open [https://cloud.mongodb.com](https://cloud.mongodb.com) and create an account. You can register with e‑mail or sign in via **Google** or **GitHub**.
2. **Create a Project & Cluster**
   Create a new *Project* (e.g. `mcp-memory`) and choose **Create → Deployment → Create a cluster**.
   Select the **Free Shared (M0)** tier, pick the provider/region closest to you, give the cluster a name and click **Create**.
   Provisioning takes \~2‑3 minutes.
3. **Create a Database User**
   Navigate to **Database Access → Add New Database User**.
   – Choose *Password* authentication.
   – Enter a **Username** (e.g. `mcp_user`) and a strong **Password** (or autogenerate one).
   – For quick tests, give the user **Read and write to any database** privileges (you can tighten this later).
   – Click **Add User** and store the credentials somewhere safe.
4. **Allow Your IP Address**
   Go to **Network Access → Add IP Address** and whitelist the public IP address from which the server will connect.
   You can click **Add Current IP Address** or specify it manually.

5. **Get the Connection String (URI)**
   On the **Database Deployments** screen click **Connect → Drivers**, choose *Python* and copy the URI, which looks like:

   ```
   mongodb+srv://<username>:<password>@<cluster>.mongodb.net/?retryWrites=true&w=majority
   ```

   Replace `<username>`/`<password>` with the credentials from step 3 and optionally append `/<database>` to select the default database, e.g. `/mcp_memory`.
6. **Configure the Memory Graph Server**
   Export the connection string via the environment variable expected by the server:

   ```bash
   export MCP_MONGO_MEMORY_CONNECTION="mongodb+srv://mcp_user:<password>@cluster0.mongodb.net/mcp_memory?retryWrites=true&w=majority"
   ```

   Keep the quotes around the URI so that special characters are preserved, and **never commit this string to version control**.

Now you can launch the server as shown in the [Usage](##Using MCP Server) section.

### Using Environment Variables Directly

Alternatively, you can set the required environment variable directly:

```
MCP_MONGO_MEMORY_CONNECTION=mongodb://username:password@host:port/database
```

## Installation and Setup

### Prerequisites

1. Install uvx (if not already installed):
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. Set up MongoDB connection (see Configuration section below)

### MCP Server Configuration

Add the snippet below to your mcp configuration:

```json
{
  "mcpServers": {
    "Memory": {
      "command": "/path/to/local/bin/uvx",
      "args": [
        "mongo-memory"
      ],
      "env": {
        "MCP_MONGO_MEMORY_CONNECTION": "mongodb://username:password@host:port/database"
      }
    }
  }
}
```

Replace `/path/to/local/bin/` with your actual path to uvx.
Replace the connection string with your actual MongoDB credentials.

### Available Operations

The server provides the following operations for AI agents:

**Entity Management:**
* `create_entities` - Create new entities with unique names
* `get_entity` - Retrieve a single entity by name
* `update_entity` - Update existing entity data
* `delete_entity` - Remove an entity
* `find_entities` - Search entities with query criteria

**Relationship Management:**
* `create_relationship` - Create relationships between entities
* `get_relationships` - Retrieve relationships with filtering
* `delete_relationship` - Remove specific relationships

**Memory Structure:**
* `get_memory_structure` - Get current memory organization
* `get_usage_guide` - Get comprehensive usage examples and best practices

For detailed usage examples, patterns, and best practices, AI agents should call `get_usage_guide()`.

## Development

See [DEVELOPMENT.md](DEVELOPMENT.md) for development setup and guidelines.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
