# MCP Memory Graph Server

[![PyPI - Version](https://img.shields.io/pypi/v/mongo-memory?color=green)](https://pypi.org/project/mongo-memory/)
[![Python Version](https://img.shields.io/pypi/pyversions/mongo-memory.svg)](https://pypi.org/project/mongo-memory/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Overview

**mongo-memory is a persistent structured knowledge graph for AI agents, backed by MongoDB.**
It exposes MCP tools for storing and querying entities, their properties, and
explicit relationships across agent sessions.

This is a storage and retrieval tool, not an autonomous "smart memory" system.
The agent decides what to record, how to relate it, and when to retrieve or update
it. The server does not infer relationships or keep stored knowledge synchronized
with a changing codebase.

### What is worth storing?

There is little value in copying into MongoDB what an agent can retrieve again
from the current source code. The useful knowledge is the context that the code
does not explicitly capture:

* **Architectural rationale** — why a particular approach was chosen and which
  alternatives were rejected.
* **Logical connections** — modules that are related conceptually or operationally,
  even when there are no direct code dependencies between them.
* **Investigation findings** — implementation details and behavior that have
  already been explored, so another session does not have to repeat the work.
* **Non-obvious constraints and problems** — limitations, edge cases, and known
  issues discovered during development or operation.

Store the conclusions and their context, not a duplicate of the code. References
to relevant files, commits, or issues help an agent verify whether a finding is
still applicable. Current source code remains the source of truth for how the
system works today; stored findings may need to be reviewed as it changes.

## Features

* MongoDB-backed persistence across agent sessions
* Entity CRUD with unique names and free-form properties
* Explicit, typed relationships between named entities
* Entity lookup and filtering through MongoDB queries
* MCP tools for agents to read and maintain the stored graph

Automatic code indexing, semantic search, and graph traversal tools are not
provided.

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

Now you can launch the server as shown in the [MCP Server Configuration](#mcp-server-configuration) section.

### Using Environment Variables Directly

Alternatively, you can set the required environment variable directly:

```
MCP_MONGO_MEMORY_CONNECTION=mongodb://username:password@host:port/database
```

## Installation and Setup

### Prerequisites

Python **3.12+**. The server uses the official **Python MCP SDK 2.x**
(`mcp[cli]>=2.3.0,<3`); SDK 1.x is no longer supported by this source tree.
The stdio transport and existing tool names are unchanged. See
[DEVELOPMENT.md](DEVELOPMENT.md) for local development without publishing a package.

1. Install uvx (if not already installed):
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. Set up MongoDB connection (see Configuration above)

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
* `get_relationships` - Retrieve up to 100 relationships (MCP accepts only `limit`, no filtering or cursor)
* `delete_relationship` - Remove specific relationships

**Memory Structure:**
* `get_memory_structure` - Get current memory organization
* `get_usage_guide` - Get comprehensive usage examples and best practices

For detailed usage examples, patterns, and best practices, AI agents should call `get_usage_guide()`.

### Database selection and response format

The URI database now selects where entities and relationships are stored; without
one, the default is `agent_memory`. **Older versions ignored the URI database**:
if an existing URI named another database, change it to `/agent_memory` to continue
using the old data. No data is moved automatically. The legacy memory structure
is still read from `memory.sys`; if absent, `get_memory_structure` returns `{}`.

`find_entities` returns `{ "success": true, "entities": [...], "count": N }`.
Missing entities and invalid inputs return `{ "success": false, "error": ..., "message": ... }`.
BSON values in MCP read responses use MongoDB Extended JSON (for example,
`{ "$oid": "..." }` and `{ "$date": "..." }`), not Python object representations.

Entity batches are validated before writing, but insertion is **not atomic**.
A bulk-write failure reports `created`, the number already inserted; inspect the
data before retrying. One relationship is allowed per source/target/type,
regardless of its properties.

## Development

See [DEVELOPMENT.md](DEVELOPMENT.md) for development setup and guidelines.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
