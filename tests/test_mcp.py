"""Exercise the installed entry point through the real MCP stdio protocol."""

import asyncio
import json
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import pytest

from mongo_memory import __version__


@pytest.mark.parametrize('handshake', ['initialize', 'discover'])
def test_stdio_tools(mongo_connector, handshake):
    async def run():
        parameters = StdioServerParameters(
            command=sys.executable,
            args=['-m', 'mongo_memory.cli'],
            env={'MCP_MONGO_MEMORY_CONNECTION': os.environ['MCP_MONGO_MEMORY_CONNECTION']},
        )
        async with asyncio.timeout(30), stdio_client(parameters) as (read, write), ClientSession(read, write) as session:
            await getattr(session, handshake)()
            assert session.server_info.name == 'mongo-memory'
            assert session.server_info.version == __version__
            assert 'MongoDB Memory Database' in session.instructions
            tools = await session.list_tools()
            assert len(tools.tools) == 10
            assert all(tool.input_schema['type'] == 'object' for tool in tools.tools)
            created = await session.call_tool('create_entities', {'entities': [{'name': 'stdio_entity'}]})
            assert not created.is_error
            assert json.loads(created.content[0].text)['created'] == 1
            found = await session.call_tool('get_entity', {'name': 'stdio_entity'})
            assert not found.is_error
            entity = json.loads(found.content[0].text)
            assert entity['name'] == 'stdio_entity'
            assert '$oid' in entity['_id']
            assert '$date' in entity['created_at']
            assert found.structured_content == entity
            for relationship_type, success in [('knows:key=a=b', True), ('knows:invalid', False)]:
                result = await session.call_tool('create_relationship', {
                    'from_entity': 'stdio_entity',
                    'to_entity': 'stdio_entity',
                    'relationship_type': relationship_type,
                })
                assert not result.is_error
                assert json.loads(result.content[0].text)['success'] is success
            updated = await session.call_tool('update_entity', {
                'name': 'stdio_entity', 'update': {'$set': {'type': 'stdio_test'}},
            })
            assert updated.structured_content['success'] is True
            matches = await session.call_tool('find_entities', {'query': {'type': 'stdio_test'}})
            assert matches.structured_content['count'] == 1
            assert matches.structured_content['entities'][0]['name'] == 'stdio_entity'
            relationships = await session.call_tool('get_relationships', {'limit': 10})
            assert relationships.structured_content['total_count'] == 1
            removed = await session.call_tool('delete_relationship', {
                'from_entity': 'stdio_entity', 'to_entity': 'stdio_entity', 'relationship_type': 'knows:key=a=b',
            })
            assert removed.structured_content['deleted_count'] == 1
            structure = await session.call_tool('get_memory_structure', {})
            assert not structure.is_error
            assert isinstance(structure.structured_content, dict)
            guide = await session.call_tool('get_usage_guide', {})
            assert not guide.is_error
            assert 'Quick Start Guide' in guide.content[0].text
            deleted = await session.call_tool('delete_entity', {'name': 'stdio_entity'})
            assert deleted.structured_content['success'] is True
            missing = await session.call_tool('get_entity', {'name': 'stdio_entity'})
            assert missing.structured_content['success'] is False
            assert missing.structured_content['error'] == 'Entity not found'

    asyncio.run(run())
