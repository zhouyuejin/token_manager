"""Protocol output boundaries must keep reasoning out of visible replies."""
import copy
import json
import unittest

from app.services.protocol_conversion import convert_response
from app.services.protocol_stream import ProtocolStream


FORMATS = ('chat', 'anthropic', 'responses')
TEXT = 'before<think>private</think>after'
ARGUMENTS = '{"text":"<think>tool data</think>"}'


def response(protocol):
    usage = {'prompt_tokens': 11, 'completion_tokens': 17, 'total_tokens': 28}
    if protocol == 'chat':
        return {'id': 'r', 'choices': [{'message': {'role': 'assistant', 'content': TEXT,
                'reasoning_content': 'private', 'tool_calls': [{'id': 'c', 'type': 'function',
                'function': {'name': 'echo', 'arguments': ARGUMENTS}}]}, 'finish_reason': 'tool_calls'}], 'usage': usage}
    usage = {'input_tokens': 11, 'output_tokens': 17}
    if protocol == 'anthropic':
        return {'id': 'r', 'content': [{'type': 'thinking', 'thinking': 'private', 'signature': 's'},
                {'type': 'redacted_thinking', 'data': 'private'}, {'type': 'text', 'text': TEXT},
                {'type': 'tool_use', 'id': 'c', 'name': 'echo', 'input': json.loads(ARGUMENTS)}],
                'stop_reason': 'tool_use', 'usage': usage}
    return {'id': 'r', 'status': 'completed', 'output': [{'type': 'reasoning', 'id': 'rs',
            'summary': [{'type': 'summary_text', 'text': 'private'}]},
            {'type': 'message', 'role': 'assistant', 'id': 'm', 'content': [{'type': 'output_text', 'text': TEXT}]},
            {'type': 'function_call', 'id': 'f', 'call_id': 'c', 'name': 'echo', 'arguments': ARGUMENTS}], 'usage': usage}


def events(protocol, chunks):
    if protocol == 'chat':
        yield '', {'choices': [{'index': 0, 'delta': {'reasoning_content': 'private'}}]}
        for chunk in chunks:
            yield '', {'choices': [{'index': 0, 'delta': {'content': chunk}}]}
        yield '', {'choices': [{'index': 0, 'delta': {}, 'finish_reason': 'stop'}],
                   'usage': {'prompt_tokens': 11, 'completion_tokens': 17}}
        yield '', '[DONE]'
    elif protocol == 'anthropic':
        yield 'message_start', {'message': {'id': 'r', 'content': [], 'usage': {'input_tokens': 11, 'output_tokens': 0}}}
        yield 'content_block_start', {'index': 0, 'content_block': {'type': 'thinking', 'thinking': ''}}
        yield 'content_block_delta', {'index': 0, 'delta': {'type': 'thinking_delta', 'thinking': 'private'}}
        yield 'content_block_delta', {'index': 0, 'delta': {'type': 'signature_delta', 'signature': 's'}}
        yield 'content_block_stop', {'index': 0}
        yield 'content_block_start', {'index': 1, 'content_block': {'type': 'text', 'text': ''}}
        for chunk in chunks:
            yield 'content_block_delta', {'index': 1, 'delta': {'type': 'text_delta', 'text': chunk}}
        yield 'content_block_stop', {'index': 1}
        yield 'message_delta', {'delta': {'stop_reason': 'end_turn'}, 'usage': {'output_tokens': 17}}
        yield 'message_stop', {}
    else:
        yield 'response.created', {'response': {'id': 'r', 'status': 'in_progress', 'output': []}}
        yield 'response.output_item.added', {'output_index': 0, 'item': {'type': 'reasoning', 'id': 'rs', 'summary': []}}
        yield 'response.reasoning_summary_text.delta', {'output_index': 0, 'delta': 'private'}
        yield 'response.output_item.done', {'output_index': 0, 'item': {'type': 'reasoning', 'id': 'rs', 'summary': []}}
        yield 'response.output_item.added', {'output_index': 1, 'item': {'type': 'message', 'id': 'm', 'role': 'assistant', 'content': []}}
        yield 'response.content_part.added', {'output_index': 1, 'content_index': 0, 'part': {'type': 'output_text', 'text': ''}}
        for chunk in chunks:
            yield 'response.output_text.delta', {'output_index': 1, 'content_index': 0, 'delta': chunk}
        yield 'response.output_text.done', {'output_index': 1, 'content_index': 0, 'text': ''.join(chunks)}
        yield 'response.content_part.done', {'output_index': 1, 'content_index': 0, 'part': {'type': 'output_text', 'text': ''.join(chunks)}}
        item = {'type': 'message', 'id': 'm', 'role': 'assistant', 'content': [{'type': 'output_text', 'text': ''.join(chunks)}]}
        yield 'response.output_item.done', {'output_index': 1, 'item': item}
        yield 'response.completed', {'response': {'id': 'r', 'status': 'completed', 'output': [item], 'usage': {'input_tokens': 11, 'output_tokens': 17}}}


class ReasoningTests(unittest.TestCase):
    def test_responses_all_protocol_pairs(self):
        for source in FORMATS:
            original = response(source)
            before = copy.deepcopy(original)
            for target in FORMATS:
                with self.subTest(source=source, target=target):
                    result = convert_response(original, source, target)
                    encoded = json.dumps(result)
                    self.assertNotIn('private', encoded)
                    self.assertIn('beforeafter', encoded)
                    self.assertIn('tool data', encoded)
                    canonical = convert_response(result, target, 'chat')
                    call = canonical['choices'][0]['message']['tool_calls'][0]
                    self.assertEqual(call['id'], 'c')
                    self.assertEqual(json.loads(call['function']['arguments']), json.loads(ARGUMENTS))
                    self.assertEqual(result['usage'].get('completion_tokens', result['usage'].get('output_tokens')), 17)
            self.assertEqual(original, before)

    def test_streams_all_protocol_pairs_and_tag_splits(self):
        for source in FORMATS:
            for target in FORMATS:
                for split in range(len(TEXT) + 1):
                    with self.subTest(source=source, target=target, split=split):
                        stream = ProtocolStream(source, target, 'model')
                        frames = []
                        for event, body in events(source, [TEXT[:split], TEXT[split:]]):
                            if event:
                                body = {'type': event, **body}
                            frames += stream.feed(event, body if isinstance(body, str) else json.dumps(body))
                        frames += stream.finish()
                        wire = ''.join(frames)
                        self.assertNotIn('private', wire)
                        self.assertNotIn('<think>', wire)
                        self.assertNotIn('reasoning_content', wire)
                        self.assertNotIn('thinking_delta', wire)
                        self.assertEqual(stream.usage, {'prompt_tokens': 11, 'completion_tokens': 17, 'total_tokens': 28})
                        visible = []
                        for frame in frames:
                            data = next(line[6:] for line in frame.splitlines() if line.startswith('data: '))
                            if data == '[DONE]':
                                continue
                            body = json.loads(data)
                            if target == 'chat':
                                visible += [c['delta'].get('content', '') for c in body['choices']]
                            elif body.get('type') == 'content_block_delta':
                                self.assertEqual(body['index'], 0)
                                visible.append(body['delta'].get('text', ''))
                            elif body.get('type') == 'response.output_text.delta':
                                self.assertEqual(body['output_index'], 0)
                                visible.append(body['delta'])
                        self.assertEqual(''.join(visible), 'beforeafter')
                        self.assertNotIn('private', json.dumps(stream.response))

    def test_tool_stream_arguments_and_terminal_settlement(self):
        for source in FORMATS:
            for target in FORMATS:
                with self.subTest(source=source, target=target):
                    stream = ProtocolStream(source, target, 'model')
                    frames = []
                    for event, body in events(source, [TEXT]):
                        if source == 'chat' and isinstance(body, dict) and body.get('usage'):
                            calls = [('', {'choices': [{'index': 0, 'delta': {'tool_calls': [
                                {'index': 0, 'id': 'c', 'type': 'function',
                                 'function': {'name': 'echo', 'arguments': ARGUMENTS}}]}}]})]
                        elif source == 'anthropic' and event == 'message_delta':
                            calls = [('content_block_start', {'index': 2, 'content_block':
                                      {'type': 'tool_use', 'id': 'c', 'name': 'echo', 'input': {}}}),
                                     ('content_block_delta', {'index': 2, 'delta':
                                      {'type': 'input_json_delta', 'partial_json': ARGUMENTS}}),
                                     ('content_block_stop', {'index': 2})]
                        elif source == 'responses' and event == 'response.completed':
                            item = {'type': 'function_call', 'id': 'f', 'call_id': 'c', 'name': 'echo', 'arguments': ''}
                            calls = [('response.output_item.added', {'output_index': 2, 'item': item}),
                                     ('response.function_call_arguments.delta', {'output_index': 2, 'delta': ARGUMENTS}),
                                     ('response.function_call_arguments.done', {'output_index': 2, 'arguments': ARGUMENTS})]
                            body['response']['output'].append({**item, 'arguments': ARGUMENTS})
                        else:
                            calls = []
                        for call_event, call_body in calls:
                            frames += stream.feed(call_event, json.dumps({'type': call_event, **call_body}))
                        frames += stream.feed(event, body if isinstance(body, str) else json.dumps({'type': event, **body}))
                    self.assertNotIn('[DONE]', ''.join(frames))
                    self.assertNotIn('event: message_stop', ''.join(frames))
                    self.assertNotIn('event: response.completed', ''.join(frames))
                    frames += stream.finish()
                    self.assertIn('tool data', ''.join(frames))
                    native = convert_response(stream.response, target, 'chat')
                    call = native['choices'][0]['message']['tool_calls'][0]
                    self.assertEqual(call['id'], 'c')
                    self.assertEqual(json.loads(call['function']['arguments']), json.loads(ARGUMENTS))
                    self.assertEqual(stream.usage['completion_tokens'], 17)

    def test_unclosed_reasoning_does_not_hide_next_text_block(self):
        for target in FORMATS:
            stream = ProtocolStream('anthropic', target, 'model')
            frames = []
            messages = [
                ('message_start', {'message': {'id': 'r', 'content': [], 'usage': {'input_tokens': 1, 'output_tokens': 0}}}),
                ('content_block_start', {'index': 0, 'content_block': {'type': 'text', 'text': '<think>private'}}),
                ('content_block_stop', {'index': 0}),
                ('content_block_start', {'index': 1, 'content_block': {'type': 'text', 'text': 'answer'}}),
                ('content_block_stop', {'index': 1}),
                ('message_delta', {'delta': {'stop_reason': 'end_turn'}, 'usage': {'output_tokens': 4}}),
                ('message_stop', {})]
            for event, body in messages:
                frames += stream.feed(event, json.dumps({'type': event, **body}))
            frames += stream.finish()
            self.assertNotIn('private', ''.join(frames))
            self.assertIn('answer', ''.join(frames))
            self.assertIn('answer', json.dumps(stream.response))


if __name__ == '__main__':
    unittest.main()
