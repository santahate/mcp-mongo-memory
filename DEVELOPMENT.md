# Development Guide

## Scope and workflow

Work on `dev`. Local development and the test workflow do not publish packages
or change the project version. The existing `release.yml` remains a separate
release workflow: merging `dev` into `master` triggers versioning and publication
to TestPyPI and PyPI. Do not merge that PR during this maintenance work.

## Project layout

```text
src/mongo_memory/
  main.py                 MCPServer tools and server entry point
  cli.py                  python -m mongo_memory.cli entry point
  mongo_connector.py      MongoDB operations, validation and indexes
  response_utils.py       Success/error responses and MCP JSON serialization
  constants/              Server instructions and usage guide
tests/
  conftest.py             Guarded, isolated MongoDB fixture
  test_entities.py        Entity CRUD and batch validation
  test_relationships.py   Relationship CRUD, parsing and indexes
  test_configuration.py   Configuration, structure and database failures
  test_mcp.py             Real MCP client/server round trip over stdio
.github/workflows/
  tests.yml               Tests and lint, no publication
  release.yml             Existing release automation
```

Python >=3.12 and `uv` are required. `pyproject.toml` defines runtime and development
dependencies; `uv.lock` records their resolved versions.

```bash
uv sync --locked
```

## Local test database

Tests require a real MongoDB. Start a disposable instance bound to loopback only:

```bash
docker run -d --rm --name mcp-mongo-memory-test \
  -p 127.0.0.1:27017:27017 mongo:7
```

Once MongoDB is ready:

```bash
uv run --locked pytest -q
uv run --locked ruff check .
```

Tests use `mongodb://127.0.0.1:27017/mongo_memory_test` by default, **never** the
application's `MCP_MONGO_MEMORY_CONNECTION`. To select another disposable database:

```bash
export MCP_MONGO_MEMORY_TEST_CONNECTION='mongodb://127.0.0.1:27017/mongo_memory_test_local'
uv run --locked pytest -q
```

**The fixture drops the test database before and after every integration test.**
It refuses database names not starting with `mongo_memory_test`. Never point it
at valuable data. Run suites serially or use distinct test databases for concurrent
runs. Structure tests also use this isolated database, not the normal `memory.sys`.

Stop and remove the disposable instance when finished:

```bash
docker stop mcp-mongo-memory-test
```

## Run the local MCP server

```bash
MCP_MONGO_MEMORY_CONNECTION='mongodb://127.0.0.1:27017/agent_memory' \
  uv run --locked mongo-memory
```

The default transport is stdio; connect an MCP client rather than typing commands
into the process. `uv run --locked python -m mongo_memory.cli` is equivalent.
`tests/test_mcp.py` launches this entry point and verifies tool discovery, entity
creation/retrieval and relationship parsing through the actual MCP protocol.

## Official MCP SDK v2 migration

The runtime dependency is `mcp[cli]>=2.3.0,<3`, with 2.3.0 resolved in `uv.lock`.
The server now imports `MCPServer` from `mcp.server` instead of `FastMCP` and
reports the application's version explicitly. Tool names, arguments and the
stdio transport are unchanged; synchronous handlers run in SDK worker threads,
which the shared PyMongo client supports.

Client tests use v2's snake_case fields (`is_error`, `structured_content`,
`input_schema`, etc.) and exercise all ten tools through both the legacy
`initialize` handshake and the modern `discover` handshake. BSON serialization
is handled before SDK output validation. No v1 import fallback or dependency
on the separate third-party `fastmcp` package is introduced.

Reference: [official v1→v2 migration guide](https://py.sdk.modelcontextprotocol.io/migration/).

## Data and response contracts

- The database in the connection URI stores `entities` and `relationships`.
  If the URI omits a database, the historical `agent_memory` default is used.
  **Previously the URI database was ignored.** Existing installations with a
  different database in their URI must explicitly select `agent_memory` to keep
  reading their existing data; no automatic migration is performed.
- Entities require a unique string `name`. Other fields remain free-form.
  Creation adds UTC `created_at` and `updated_at`. Updates accept MongoDB
  operator dictionaries, such as `{"$set": {"data.value": 1}}`.
- Entity creation and update do not mutate caller-owned dictionaries.
- `create_entities` validates the entire batch before insertion. MongoDB's ordered
  `insert_many` is **not atomic**: a database error can leave an inserted prefix.
  Bulk-write error responses include `created` (`nInserted`). Other database
  failures may leave the outcome uncertain; inspect the data before retrying.
- Missing entities and invalid inputs return error dictionaries rather than
  raising application validation exceptions. Success responses use
  `{"success": true, ...}`; errors use `{"success": false, "error": ..., "message": ...}`.
- `get_entity` returns the entity document on success. `find_entities` returns
  `{"success": true, "entities": [...], "count": N}`. Its limit must be a positive
  integer; its query must be a non-empty dictionary.
- Relationships store source/target **names**, a type, properties and a creation
  timestamp. The unique `(from_entity, to_entity, type)` index allows one edge per
  pair/type, regardless of properties. That constraint is unchanged.
- Create and delete share one parser for `type:key=value,key2=value2`.
  `knows` and `knows:` are valid; malformed properties are rejected. Values may
  contain `=`, but not commas (there is no escaping syntax).
- Index creation is idempotent at startup. Legacy `from_name`/`to_name` indexes are
  no longer created; existing legacy indexes are not automatically dropped.
- `get_memory_structure` reads the historical `memory.sys` document matching
  `{"structure": true}`. A missing document returns `{}`. Configuration and read
  failures return error responses. It does not infer a schema from entities.
- Read tools encode BSON values as MongoDB Extended JSON at the MCP boundary,
  e.g. `{"$oid": "..."}` and `{"$date": "..."}`. The connector itself returns
  native MongoDB values to Python callers.

## Deliberately deferred

No new tools, cursor pagination, relationship-query parameters or transaction
requirements are introduced. `get_relationships` still exposes only `limit`
(1–100) over MCP. Its existing `page_info` is informational: there is no accepted
cursor argument, so callers cannot request the next page. The connector's
existing Python query argument remains available.

Entity deletion/renaming does not cascade to relationships. Delete incident
edges first while both endpoints exist; `delete_relationship` rejects missing
endpoints and cannot remove an already dangling edge. The relationship tests
cover incoming/outgoing edges, an unrelated edge, and both deletion orders.
Graph lifecycle changes still need a separate decision; no cascade is introduced.

## CI

`tests.yml` runs `uv sync --locked`, Ruff and pytest with MongoDB 7 on Python
3.12/3.13 for pushes to `dev` and PRs targeting `dev`/`master`. It has read-only
repository permissions and no publication steps or package tokens.
