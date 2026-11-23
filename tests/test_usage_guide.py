"""Execute documented helpers, rather than only checking that the guide exists."""

import ast
from copy import deepcopy
import re
from textwrap import dedent
from unittest.mock import MagicMock

import pytest

from mongo_memory.constants.usage_guide import user_guide


@pytest.fixture
def examples():
    functions = []
    for block in re.findall(r'```python\n(.*?)```', user_guide, re.DOTALL):
        tree = ast.parse(dedent(block))
        functions.extend(node for node in tree.body if isinstance(node, ast.FunctionDef))
    namespace = {'memory': MagicMock(), 'ask_user_for_categorization': MagicMock(return_value='task_42')}
    exec(compile(ast.Module(body=functions, type_ignores=[]), '<usage_guide>', 'exec'), namespace)  # noqa: S102
    return namespace


@pytest.mark.parametrize('helper', ['remember_interaction', 'remember_fact'])
@pytest.mark.parametrize('context', [None, {}, {'category_marker': 'task_7'}, {'task_id': 'task_7'}])
def test_remember_examples_handle_optional_context(examples, helper, context):
    original = deepcopy(context)
    if helper == 'remember_interaction':
        examples[helper]('user', {'finding': 'use outbox'}, context)
        call = examples['memory'].update_entity.call_args
        stored = call.args[1]['$set']['data']
        assert call.kwargs['upsert'] is True
    else:
        examples[helper]('delivery', 'use outbox', 'review', context)
        stored = examples['memory'].create_entities.call_args.args[0][0]['data']
    assert context == original
    if context:
        assert stored['category'] == 'task_7'
        examples['ask_user_for_categorization'].assert_not_called()
    else:
        assert stored['category'] == 'task_42'
        examples['ask_user_for_categorization'].assert_called_once_with()


def test_relationship_example_uses_relationship_tools():
    section = user_guide.split('### Relationships\n', 1)[1].split('### Delete Entity', 1)[0]
    block = re.search(r'```python\n(.*?)```', section, re.DOTALL).group(1)
    memory = MagicMock()
    memory.get_relationships.return_value = {'relationships': [
        {'from_entity': 'user1', 'to_entity': 'company1'},
        {'from_entity': 'other', 'to_entity': 'company2'},
    ]}
    namespace = {'memory': memory}
    exec(compile(dedent(block), '<usage_guide_relationships>', 'exec'), namespace)  # noqa: S102
    memory.create_relationship.assert_called_once_with('user1', 'company1', 'works_at:position=developer')
    memory.delete_relationship.assert_called_once_with('user1', 'company1', 'works_at:position=developer')
    memory.get_relationships.assert_called_once_with(limit=100)
    memory.find_entities.assert_not_called()
    assert namespace['user1_relations'] == [{'from_entity': 'user1', 'to_entity': 'company1'}]


def test_bounded_context_reads_real_relationships(examples):
    memory = examples['memory']
    memory.get_entity.side_effect = lambda name: {'name': name}
    memory.get_relationships.return_value = {'relationships': [
        {'from_entity': 'a', 'to_entity': 'b'},
        {'from_entity': 'c', 'to_entity': 'a'},
        {'from_entity': 'c', 'to_entity': 'd'},
    ]}
    result = examples['get_bounded_context']('a')
    memory.get_relationships.assert_called_once_with(limit=100)
    memory.find_entities.assert_not_called()
    assert result['entity'] == {'name': 'a'}
    assert result['related_entities'] == [{'name': 'b'}, {'name': 'c'}]
    assert len(result['relationships']) == 2
