"""Integration fixtures: never use the application's MongoDB connection."""

import os

from pymongo import MongoClient
from pymongo.errors import PyMongoError
import pytest

from mongo_memory.mongo_connector import MongoConnector


@pytest.fixture
def mongo_connector(monkeypatch):
    """Use only a dedicated database, with an explicit guard before any deletion."""
    uri = os.getenv('MCP_MONGO_MEMORY_TEST_CONNECTION', 'mongodb://127.0.0.1:27017/mongo_memory_test')
    with MongoClient(uri, serverSelectionTimeoutMS=2000) as client:
        database = client.get_default_database()
        if not database.name.startswith('mongo_memory_test'):
            pytest.fail('Test database name must start with mongo_memory_test; refusing to delete data')
        try:
            client.admin.command('ping')
        except PyMongoError:
            pytest.fail('Test MongoDB unavailable; see DEVELOPMENT.md for the local Docker command')
        client.drop_database(database.name)
        monkeypatch.setenv('MCP_MONGO_MEMORY_CONNECTION', uri)
        with MongoConnector() as connector:
            # Structure tests must not touch the historical memory.sys database either.
            connector.SYSTEM_MEMORY_DB = database.name
            try:
                assert connector.config_error is None, connector.config_error
                yield connector
            finally:
                client.drop_database(database.name)
