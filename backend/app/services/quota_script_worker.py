"""Private subprocess entry point for restricted JavaScript quota queries."""
import json
import resource
import sys
from urllib.parse import urljoin, urlsplit

import httpx
import quickjs


def evaluate(payload):
    context = quickjs.Context()
    context.set_memory_limit(16 * 1024 * 1024)
    context.set_max_stack_size(256 * 1024)
    endpoint = payload['endpoint']
    calls = 0

    def request(options_json):
        nonlocal calls
        calls += 1
        try:
            options = json.loads(options_json)
            url = urljoin(endpoint.rstrip('/') + '/', options['url'])
            origin, target = urlsplit(endpoint), urlsplit(url)
            if calls > 3 or target.scheme not in ('http', 'https') or (
                target.scheme, target.hostname, target.port
            ) != (origin.scheme, origin.hostname, origin.port) or target.username or target.password:
                raise ValueError('仅允许请求渠道同源地址，每次脚本最多 3 次请求')
            method = options.get('method', 'GET').upper()
            if method not in ('GET', 'POST'):
                raise ValueError('仅支持 GET 和 POST')
            with httpx.Client(timeout=8, follow_redirects=False, trust_env=False) as client:
                with client.stream(method, url, headers=options.get('headers'), params=options.get('params'), json=options.get('data')) as response:
                    body = bytearray()
                    for chunk in response.iter_bytes():
                        body.extend(chunk)
                        if len(body) > 262144:
                            raise ValueError('HTTP 响应超过 256KB')
                    if not 200 <= response.status_code < 300:
                        raise ValueError(f'HTTP {response.status_code}')
                    return json.dumps({'data': json.loads(body), 'status': response.status_code})
        except Exception as error:
            return json.dumps({'error': str(error)})

    context.add_callable('__request', request)
    context.set('endpoint', endpoint)
    context.set('apiKey', payload['api_key'])
    context.eval('''
        const http = Object.freeze({
            request(options) {
                const result = JSON.parse(__request(JSON.stringify(options)));
                if (result.error) throw new Error(result.error);
                return result;
            },
            get(url, options = {}) { return this.request({...options, url, method: 'GET'}); },
            post(url, data, options = {}) { return this.request({...options, url, data, method: 'POST'}); }
        });
    ''')
    result = context.eval('JSON.stringify((function() { "use strict";\n' + payload['script'] + '\n})())')
    if not result or len(result) > 262144:
        raise ValueError('脚本必须返回对象，结果不得超过 256KB')
    return json.loads(result)


if __name__ == '__main__':
    resource.setrlimit(resource.RLIMIT_CPU, (3, 3))
    resource.setrlimit(resource.RLIMIT_AS, (256 * 1024 * 1024, 256 * 1024 * 1024))
    payload = json.load(sys.stdin)
    try:
        result = {'data': evaluate(payload)}
    except Exception as error:
        result = {'error': str(error)}
    encoded = json.dumps(result, ensure_ascii=False)
    if payload['api_key']:
        encoded = encoded.replace(json.dumps(payload['api_key'], ensure_ascii=False)[1:-1], '***')
    sys.stdout.write(encoded)
