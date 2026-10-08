import copy

import pytest

from app.services.protocol_conversion import convert_request


@pytest.mark.parametrize('content', ['Permission denied', [{'type': 'text', 'text': 'Permission denied'}], ''])
@pytest.mark.parametrize('target', ['chat', 'responses', 'anthropic'])
def test_anthropic_failed_tool_result_preserves_failure(content, target):
    body = {'model': 'm', 'messages': [
        {'role': 'assistant', 'content': [{'type': 'tool_use', 'id': 'call_1', 'name': 'read', 'input': {}}]},
        {'role': 'user', 'content': [{'type': 'tool_result', 'tool_use_id': 'call_1',
                                     'is_error': True, 'content': content}]},
    ]}
    original = copy.deepcopy(body)
    result = convert_request(body, 'anthropic', target)
    assert body == original
    if target == 'anthropic':
        assert result == body
        return
    if target == 'chat':
        tool = result['messages'][-1]
        assert tool['tool_call_id'] == 'call_1'
        output = tool['content']
    else:
        tool = result['input'][-1]
        assert tool['type'] == 'function_call_output'
        assert tool['call_id'] == 'call_1'
        output = tool['output']
    text = output if isinstance(output, str) else '\n'.join(part['text'] for part in output)
    assert text.startswith('Tool execution failed:')
    if content:
        assert 'Permission denied' in text
