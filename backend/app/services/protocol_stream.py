"""Incremental protocol SSE conversion with settlement-controlled completion."""
import copy
import json
import time
import uuid


class ProtocolStream:
    def __init__(self, source, target, model):
        if source not in ('chat', 'anthropic', 'responses') or target not in ('chat', 'anthropic', 'responses'):
            raise ValueError('Unsupported stream protocol')
        self.source, self.target, self.model = source, target, model
        self.usage = None
        self.completed = False
        self.response = None
        self._finished = False
        self._started = False
        self._id = 'resp_' + uuid.uuid4().hex
        self._created = int(time.time())
        self._reason = 'stop'
        self._terminal = []
        self._blocks = {}
        self._source_blocks = {}
        self._source_response = {}
        self._sequence = 0
        self._chat_usage = None
        self._think_states = {}
        self._native_indices = {}

    def _filter_think_delta(self, text, key):
        hidden, pending = self._think_states.get(key, (False, ''))
        data, pending = pending + text, ''
        output = []
        while data:
            tag = '</think>' if hidden else '<think>'
            position = data.find(tag)
            if position >= 0:
                if not hidden:
                    output.append(data[:position])
                data = data[position + len(tag):]
                hidden = not hidden
                continue
            keep = next((size for size in range(min(len(data), len(tag) - 1), 0, -1)
                         if tag.startswith(data[-size:])), 0)
            if not hidden:
                output.append(data[:-keep] if keep else data)
            pending = data[-keep:] if keep else ''
            break
        # Incomplete tags/reasoning are withheld, including at end of stream.
        self._think_states[key] = (hidden, pending)
        return ''.join(output)

    def _text_piece(self, key, text):
        visible = self._filter_think_delta(text, key=key)
        return self._piece(key, 'text', visible) if visible else []

    @staticmethod
    def _frame(event, data):
        payload = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False, separators=(',', ':'))
        return (f'event: {event}\n' if event else '') + ''.join(f'data: {line}\n' for line in payload.split('\n')) + '\n'

    def _event(self, event, **fields):
        data = {'type': event, **fields}
        if self.target == 'responses':
            data['sequence_number'] = self._sequence
            self._sequence += 1
        return self._frame(event, data)

    def _chunk(self, delta, reason=None, usage=None):
        data = {'id': self._id, 'object': 'chat.completion.chunk', 'created': self._created,
                'model': self.model, 'choices': [{'index': 0, 'delta': delta, 'finish_reason': reason}]}
        if usage is not None:
            data['usage'] = usage
        return self._frame('', data)

    def _start(self):
        if self._started:
            return []
        self._started = True
        if self.target == 'chat':
            return [self._chunk({'role': 'assistant'})]
        if self.target == 'anthropic':
            return [self._event('message_start', message={'id': self._id, 'type': 'message',
                    'role': 'assistant', 'model': self.model, 'content': [], 'stop_reason': None,
                    'stop_sequence': None, 'usage': {'input_tokens': (self.usage or {}).get('prompt_tokens', 0), 'output_tokens': 0}})]
        response = {'id': self._id, 'object': 'response', 'created_at': self._created,
                    'status': 'in_progress', 'model': self.model, 'output': []}
        return [self._event('response.created', response=response), self._event('response.in_progress', response=response)]

    def _piece(self, key, kind, text='', call_id=None, name=None):
        """Publish one text or argument delta, retaining only final content snapshots."""
        out = self._start()
        block = self._blocks.get(key)
        if block is None:
            index = len(self._blocks)
            block = {'kind': kind, 'index': index, 'text': '', 'arguments': '',
                     'id': call_id or ('msg_' + uuid.uuid4().hex), 'name': name or ''}
            self._blocks[key] = block
            if kind == 'tool' and (not call_id or not name):
                raise ValueError('Tool delta requires an initial call id and name')
            if self.target == 'anthropic':
                content = {'type': 'text', 'text': ''} if kind == 'text' else {
                    'type': 'tool_use', 'id': block['id'], 'name': block['name'], 'input': {}}
                out.append(self._event('content_block_start', index=index, content_block=content))
            elif self.target == 'responses':
                item = ({'id': block['id'], 'type': 'message', 'status': 'in_progress', 'role': 'assistant', 'content': []}
                        if kind == 'text' else {'id': 'fc_' + block['id'], 'type': 'function_call', 'status': 'in_progress',
                                              'call_id': block['id'], 'name': block['name'], 'arguments': ''})
                block['item_id'] = item['id']
                out.append(self._event('response.output_item.added', output_index=index, item=item))
                if kind == 'text':
                    out.append(self._event('response.content_part.added', item_id=block['item_id'], output_index=index,
                                           content_index=0, part={'type': 'output_text', 'text': '', 'annotations': []}))
            elif kind == 'tool':
                tool_index = sum(b['kind'] == 'tool' for b in self._blocks.values()) - 1
                block['tool_index'] = tool_index
                out.append(self._chunk({'tool_calls': [{'index': tool_index, 'id': block['id'], 'type': 'function',
                                                       'function': {'name': block['name'], 'arguments': ''}}]}))
        if name and name != block['name']:
            raise ValueError('Tool name changed after its start')
        if not isinstance(text, str):
            raise ValueError('Stream delta must be a string')
        if text:
            block['text' if kind == 'text' else 'arguments'] += text
            if self.target == 'chat':
                delta = {'content': text} if kind == 'text' else {'tool_calls': [
                    {'index': block['tool_index'], 'function': {'arguments': text}}]}
                out.append(self._chunk(delta))
            elif self.target == 'anthropic':
                delta = {'type': 'text_delta', 'text': text} if kind == 'text' else {'type': 'input_json_delta', 'partial_json': text}
                out.append(self._event('content_block_delta', index=block['index'], delta=delta))
            else:
                event = 'response.output_text.delta' if kind == 'text' else 'response.function_call_arguments.delta'
                fields = {'item_id': block['item_id'], 'output_index': block['index'], 'delta': text}
                if kind == 'text':
                    fields['content_index'] = 0
                out.append(self._event(event, **fields))
        return out

    def _set_usage(self, usage):
        if not isinstance(usage, dict):
            raise ValueError('Invalid stream usage')
        if self.source == 'chat':
            self._chat_usage = copy.deepcopy(usage)
            prompt, completion = usage.get('prompt_tokens'), usage.get('completion_tokens')
        else:
            prompt, completion = usage.get('input_tokens'), usage.get('output_tokens')
            if prompt is not None and self.source == 'anthropic':
                prompt += usage.get('cache_read_input_tokens', 0) + usage.get('cache_creation_input_tokens', 0)
        if prompt is None and self.usage:
            prompt = self.usage['prompt_tokens']
        if completion is None and self.usage:
            completion = self.usage['completion_tokens']
        if prompt is not None and completion is not None:
            if not isinstance(prompt, int) or not isinstance(completion, int) or prompt < 0 or completion < 0:
                raise ValueError('Invalid stream token counts')
            self.usage = {'prompt_tokens': prompt, 'completion_tokens': completion, 'total_tokens': prompt + completion}

    def feed(self, event_name, data):
        if self.completed or self._finished:
            raise ValueError('Data received after stream completion')
        if self.source == 'chat' and data.strip() == '[DONE]':
            self.completed = True
            if self.source == self.target:
                self._terminal.append(self._frame(event_name, data))
            return []
        try:
            body = json.loads(data)
        except (ValueError, TypeError) as exc:
            raise ValueError('Malformed stream JSON') from exc
        if not isinstance(body, dict):
            raise ValueError('Stream event must be an object')
        event = event_name or body.get('type', '')
        if body.get('error') or event in ('error', 'response.failed', 'response.incomplete'):
            raise ValueError('Upstream stream error: ' + str(body.get('error') or body.get('response') or body))
        try:
            if self.source == 'chat':
                out, terminal = self._read_chat(body)
            elif self.source == 'anthropic':
                out, terminal = self._read_anthropic(event, body)
            else:
                out, terminal = self._read_responses(event, body)
        except (KeyError, TypeError, IndexError, AttributeError) as exc:
            raise ValueError('Malformed ' + self.source + ' stream event') from exc
        if self.source == self.target:
            body = self._clean_native_event(event, body)
            if body is None:
                return []
            frame = self._frame(event_name, body)
            if terminal or self._terminal:
                self._terminal.append(frame)
                return []
            return [frame]
        return out

    def _clean_native_event(self, event, body):
        from app.services.protocol_conversion import _clean_response, _strip_think_text

        body = copy.deepcopy(body)
        if self.source == 'chat':
            for choice in body['choices']:
                delta = choice['delta']
                for field in ('reasoning_content', 'reasoning', 'thinking'):
                    delta.pop(field, None)
                if isinstance(delta.get('content'), str):
                    delta['content'] = self._filter_think_delta(delta['content'], key=('text', choice.get('index', 0)))
        elif self.source == 'anthropic':
            if event == 'message_start':
                body['message'] = _clean_response(body['message'], 'anthropic')
            if 'index' in body:
                index = body['index']
                block = self._source_blocks[index]
                if block.get('type') in ('thinking', 'redacted_thinking'):
                    return None
                if index not in self._native_indices:
                    self._native_indices[index] = len(self._native_indices)
                body['index'] = self._native_indices[index]
                if event == 'content_block_start' and block.get('type') == 'text':
                    body['content_block']['text'] = self._filter_think_delta(body['content_block'].get('text', ''), key=index)
                elif event == 'content_block_delta' and body['delta'].get('type') == 'text_delta':
                    body['delta']['text'] = self._filter_think_delta(body['delta']['text'], key=index)
        else:
            if event.startswith(('response.reasoning_', 'response.reasoning.')):
                return None
            if 'response' in body:
                body['response'] = _clean_response(body['response'], 'responses')
            if 'output_index' in body:
                index = body['output_index']
                if self._source_blocks.get(index, {}).get('type') == 'reasoning':
                    return None
                if index not in self._native_indices:
                    self._native_indices[index] = len(self._native_indices)
                body['output_index'] = self._native_indices[index]
                key = ('text', index, body.get('content_index', 0))
                if event == 'response.output_text.delta':
                    body['delta'] = self._filter_think_delta(body['delta'], key=key)
                elif event == 'response.content_part.added' and body['part'].get('type') == 'output_text':
                    body['part']['text'] = self._filter_think_delta(body['part'].get('text', ''), key=key)
                elif event == 'response.output_text.done':
                    body['text'] = _strip_think_text(body['text'])
                elif event == 'response.content_part.done':
                    body['part'] = _strip_think_text([body['part']])[0]
                elif event in ('response.output_item.added', 'response.output_item.done'):
                    body['item'] = _clean_response({'output': [body['item']]}, 'responses')['output'][0]
        return body

    def _read_chat(self, body):
        if 'choices' not in body or not isinstance(body['choices'], list):
            raise ValueError('Chat stream event requires choices')
        self._id = body.get('id', self._id)
        self._created = body.get('created', self._created)
        if body.get('usage') is not None:
            self._set_usage(body['usage'])
        out, terminal = [], False
        for choice in body['choices']:
            if choice.get('index', 0) != 0:
                raise ValueError('Multiple stream choices are not supported')
            delta = choice.get('delta')
            if not isinstance(delta, dict):
                raise ValueError('Chat stream choice requires delta')
            text = delta.get('content')
            if text is not None:
                if not isinstance(text, str):
                    raise ValueError('Chat text delta must be a string')
                block = self._source_blocks.setdefault(('text', 0), {'type': 'text', 'text': ''})
                block['text'] += text
                if self.source != self.target:
                    out += self._text_piece(('text', 0), text)
            if delta.get('reasoning_content'):
                self._source_response['reasoning_content'] = self._source_response.get('reasoning_content', '') + delta['reasoning_content']
            for call in delta.get('tool_calls') or []:
                key = ('tool', call['index'])
                block = self._source_blocks.setdefault(key, {'type': 'tool_use', 'id': '', 'name': '', 'arguments': ''})
                function = call.get('function', {})
                block['id'] = call.get('id') or block['id']
                block['name'] += function.get('name', '')
                arguments = function.get('arguments', '')
                block['arguments'] += arguments
                if self.source != self.target:
                    out += self._piece(key, 'tool', arguments, block['id'], block['name'])
            if choice.get('finish_reason') is not None:
                self._reason = choice['finish_reason']
                terminal = True
        return out, terminal

    def _read_anthropic(self, event, body):
        out, terminal = [], False
        if event == 'message_start':
            self._source_response = copy.deepcopy(body['message'])
            self._id = body['message'].get('id', self._id)
            if body['message'].get('usage') is not None:
                self._set_usage(body['message']['usage'])
            if self.source != self.target:
                out += self._start()
        elif event == 'content_block_start':
            index = body['index']
            if index in self._source_blocks:
                raise ValueError('Duplicate content block start')
            block = copy.deepcopy(body['content_block'])
            self._source_blocks[index] = block
            kind = block.get('type')
            if kind == 'tool_use':
                block['_arguments'] = ''
            if self.source != self.target:
                if kind == 'text':
                    out += self._text_piece(index, block.get('text', ''))
                elif kind == 'tool_use':
                    out += self._piece(index, 'tool', '', block['id'], block['name'])
                elif kind not in ('thinking', 'redacted_thinking'):
                    raise ValueError('Unsupported cross-protocol content block: ' + str(kind))
        elif event == 'content_block_delta':
            index, delta = body['index'], body['delta']
            block = self._source_blocks[index]
            kind = delta['type']
            if block.get('_stopped'):
                raise ValueError('Delta received after content block stop')
            if kind == 'text_delta':
                block['text'] += delta['text']
                if self.source != self.target:
                    out += self._text_piece(index, delta['text'])
            elif kind == 'input_json_delta':
                block['_arguments'] += delta['partial_json']
                if self.source != self.target:
                    out += self._piece(index, 'tool', delta['partial_json'])
            elif kind in ('thinking_delta', 'signature_delta'):
                field = 'thinking' if kind == 'thinking_delta' else 'signature'
                block[field] = block.get(field, '') + delta[field]
            elif self.source != self.target:
                raise ValueError('Unsupported cross-protocol content delta: ' + str(kind))
        elif event == 'content_block_stop':
            block = self._source_blocks[body['index']]
            if block.get('_stopped'):
                raise ValueError('Duplicate content block stop')
            block['_stopped'] = True
        elif event == 'message_delta':
            delta = body['delta']
            self._source_response.update(delta)
            if body.get('usage') is not None:
                merged = {**self._source_response.get('usage', {}), **body['usage']}
                self._source_response['usage'] = merged
                self._set_usage(merged)
            self._reason = {'end_turn': 'stop', 'stop_sequence': 'stop', 'tool_use': 'tool_calls', 'max_tokens': 'length'}.get(delta.get('stop_reason'), self._reason)
            terminal = delta.get('stop_reason') is not None
        elif event == 'message_stop':
            self.completed, terminal = True, True
        elif event != 'ping' and self.source != self.target:
            raise ValueError('Unsupported Anthropic stream event: ' + str(event))
        return out, terminal

    def _read_responses(self, event, body):
        out, terminal = [], False
        if event in ('response.created', 'response.in_progress'):
            response = body['response']
            self._source_response.update(copy.deepcopy(response))
            self._id = response.get('id', self._id)
            self._created = response.get('created_at', self._created)
            if self.source != self.target:
                out += self._start()
        elif event == 'response.output_item.added':
            index, item = body['output_index'], copy.deepcopy(body['item'])
            self._source_blocks[index] = item
            if item['type'] == 'function_call' and self.source != self.target:
                out += self._piece(('tool', index), 'tool', item.get('arguments', ''), item.get('call_id', item['id']), item['name'])
            elif item['type'] not in ('message', 'function_call', 'reasoning') and self.source != self.target:
                raise ValueError('Unsupported cross-protocol output item: ' + str(item['type']))
        elif event == 'response.content_part.added':
            item = self._source_blocks[body['output_index']]
            content = item.setdefault('content', [])
            index = body['content_index']
            if index != len(content):
                raise ValueError('Invalid response content index')
            part = copy.deepcopy(body['part'])
            content.append(part)
            if self.source != self.target:
                if part['type'] != 'output_text':
                    raise ValueError('Unsupported response content part: ' + str(part['type']))
                out += self._text_piece(('text', body['output_index'], index), part.get('text', ''))
        elif event == 'response.output_text.delta':
            index, content_index = body['output_index'], body['content_index']
            item = self._source_blocks[index]
            part = item['content'][content_index]
            part['text'] += body['delta']
            if self.source != self.target:
                out += self._text_piece(('text', index, content_index), body['delta'])
        elif event == 'response.function_call_arguments.delta':
            index = body['output_index']
            item = self._source_blocks[index]
            item['arguments'] = item.get('arguments', '') + body['delta']
            if self.source != self.target:
                out += self._piece(('tool', index), 'tool', body['delta'], item.get('call_id', item['id']), item['name'])
        elif event == 'response.output_item.done':
            self._source_blocks[body['output_index']] = copy.deepcopy(body['item'])
        elif event == 'response.content_part.done':
            self._source_blocks[body['output_index']]['content'][body['content_index']] = copy.deepcopy(body['part'])
        elif event == 'response.output_text.done':
            self._source_blocks[body['output_index']]['content'][body['content_index']]['text'] = body['text']
        elif event == 'response.function_call_arguments.done':
            self._source_blocks[body['output_index']]['arguments'] = body['arguments']
        elif event == 'response.completed':
            response = body['response']
            if response.get('status') not in (None, 'completed') or response.get('error'):
                raise ValueError('Upstream response did not complete successfully')
            self._source_response.update(copy.deepcopy(response))
            if response.get('usage') is not None:
                self._set_usage(response['usage'])
            self.completed, terminal = True, True
        elif event.startswith(('response.reasoning_', 'response.reasoning.')):
            pass
        elif self.source != self.target:
            raise ValueError('Unsupported Responses stream event: ' + str(event))
        return out, terminal

    def _snapshot(self):
        if self.source == 'chat':
            message = {'role': 'assistant', 'content': ''.join(b['text'] for b in self._source_blocks.values() if b['type'] == 'text') or None}
            calls = [{'id': b['id'], 'type': 'function', 'function': {'name': b['name'], 'arguments': b['arguments']}}
                     for b in self._source_blocks.values() if b['type'] == 'tool_use']
            if calls:
                message['tool_calls'] = calls
            if 'reasoning_content' in self._source_response:
                message['reasoning_content'] = self._source_response['reasoning_content']
            result = {'id': self._id, 'object': 'chat.completion', 'created': self._created, 'model': self.model,
                      'choices': [{'index': 0, 'message': message, 'finish_reason': self._reason}]}
            if self._chat_usage is not None:
                result['usage'] = self._chat_usage
            return result
        result = copy.deepcopy(self._source_response)
        if self.source == 'anthropic':
            content = []
            for block in self._source_blocks.values():
                block = copy.deepcopy(block)
                block.pop('_stopped', None)
                arguments = block.pop('_arguments', '')
                if block['type'] == 'tool_use' and arguments:
                    try:
                        block['input'] = json.loads(arguments)
                    except ValueError as exc:
                        raise ValueError('Malformed tool arguments') from exc
                content.append(block)
            result['content'] = content
        elif not result.get('output'):
            result['output'] = [self._source_blocks[i] for i in sorted(self._source_blocks)]
        result.setdefault('id', self._id)
        result.setdefault('model', self.model)
        return result

    def finish(self):
        if not self.completed:
            raise ValueError('Upstream stream ended without a completion event')
        if self._finished:
            return []
        from app.services.protocol_conversion import convert_response
        self.response = convert_response(self._snapshot(), self.source, self.target, self.model)
        if self.source == self.target:
            self._finished = True
            return self._terminal
        out = self._start()
        if self.target == 'chat':
            reason = self.response['choices'][0].get('finish_reason', self._reason)
            out.append(self._chunk({}, reason, self.usage))
            out.append(self._frame('', '[DONE]'))
        elif self.target == 'anthropic':
            for block in self._blocks.values():
                out.append(self._event('content_block_stop', index=block['index']))
            reason = self.response.get('stop_reason', 'end_turn')
            out.append(self._event('message_delta', delta={'stop_reason': reason, 'stop_sequence': self.response.get('stop_sequence')},
                                   usage=self.response.get('usage', {'output_tokens': (self.usage or {}).get('completion_tokens', 0)})))
            out.append(self._event('message_stop'))
        else:
            for block in self._blocks.values():
                index, item_id = block['index'], block['item_id']
                if block['kind'] == 'text':
                    part = {'type': 'output_text', 'text': block['text'], 'annotations': []}
                    out.append(self._event('response.output_text.done', item_id=item_id, output_index=index, content_index=0, text=block['text']))
                    out.append(self._event('response.content_part.done', item_id=item_id, output_index=index, content_index=0, part=part))
                    item = {'id': item_id, 'type': 'message', 'status': 'completed', 'role': 'assistant', 'content': [part]}
                else:
                    out.append(self._event('response.function_call_arguments.done', item_id=item_id, output_index=index, arguments=block['arguments']))
                    item = {'id': item_id, 'type': 'function_call', 'status': 'completed', 'call_id': block['id'],
                            'name': block['name'], 'arguments': block['arguments']}
                out.append(self._event('response.output_item.done', output_index=index, item=item))
            # Use the actual streamed item identities in the final snapshot.
            items = []
            for block in self._blocks.values():
                if block['kind'] == 'text':
                    items.append({'id': block['item_id'], 'type': 'message', 'status': 'completed', 'role': 'assistant',
                                  'content': [{'type': 'output_text', 'text': block['text'], 'annotations': []}]})
                else:
                    items.append({'id': block['item_id'], 'type': 'function_call', 'status': 'completed', 'call_id': block['id'],
                                  'name': block['name'], 'arguments': block['arguments']})
            self.response.update({'id': self._id, 'output': items})
            out.append(self._event('response.completed', response=self.response))
        self._finished = True
        return out
