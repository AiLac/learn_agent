"""A teaching subset of MCP 2025-11-25 over stdio (no SDK needed)."""
import argparse
import json
import subprocess
import sys
from pathlib import Path

VERSION = '2025-11-25'
EVIDENCE = Path(__file__).resolve().parents[2] / 'data/hk-study-rooms/search-v2/evidence.json'
TOOL = {'name': 'lookup_hours', 'description': 'Read public study-room hours by ID.',
        'inputSchema': {'type': 'object', 'properties': {'place': {'type': 'string'}},
                        'required': ['place'], 'additionalProperties': False}}

def server():
    cards = {d['place_id']:d for d in json.loads(EVIDENCE.read_text(encoding='utf-8'))['documents']
             if d['id'].startswith('hours:')}
    stage = 'new'
    for line in sys.stdin:
        request = json.loads(line)
        method = request['method']
        if 'id' not in request:
            if method == 'notifications/initialized' and stage == 'negotiated':
                stage = 'ready'
            continue
        response = {'jsonrpc':'2.0', 'id':request['id']}
        if method == 'initialize' and stage == 'new':
            response['result'] = {'protocolVersion': VERSION, 'capabilities': {'tools': {}},
                                  'serverInfo': {'name':'course-hours', 'version':'1'}}
            stage = 'negotiated'
        elif stage != 'ready':
            response['error'] = {'code':-32000, 'message':'initialize first'}
        elif method == 'tools/list':
            response['result'] = {'tools':[TOOL]}
        elif method == 'tools/call':
            params = request.get('params', {})
            args = params.get('arguments', {})
            if params.get('name') != TOOL['name']:
                response['error'] = {'code':-32602, 'message':'unknown tool'}
            elif not isinstance(args, dict) or set(args) != {'place'} or not isinstance(args['place'], str):
                response['result'] = {'isError':True, 'content':[{'type':'text','text':'invalid place argument'}]}
            else:
                card = cards.get(args['place'])
                obs = {'status':'FOUND','id':card['id'],'text':card['text']} if card else {'status':'NO_DATA'}
                response['result'] = {'content':[{'type':'text','text':json.dumps(obs, ensure_ascii=False)}]}
        else:
            response['error'] = {'code':-32601, 'message':'unknown method'}
        print(json.dumps(response, ensure_ascii=True), flush=True)

def client(place):
    with subprocess.Popen([sys.executable, __file__, '--serve'], stdin=subprocess.PIPE,
                          stdout=subprocess.PIPE, encoding='utf-8') as child:
        def exchange(msg):
            child.stdin.write(json.dumps({'jsonrpc':'2.0', **msg})+'\n')
            child.stdin.flush()
            if 'id' not in msg:
                print(msg['method'], '(notification)')
                return None
            response = json.loads(child.stdout.readline())
            if response['id'] != msg['id'] or 'error' in response:
                raise RuntimeError(str(response))
            return response['result']
        try:
            hello=exchange({'id':1,'method':'initialize','params':{'protocolVersion':VERSION,'capabilities':{},
                            'clientInfo':{'name':'course-client','version':'1'}}})
            if hello['protocolVersion'] != VERSION or 'tools' not in hello['capabilities']:
                raise ValueError('incompatible server')
            print('initialize',hello['protocolVersion'])
            exchange({'method':'notifications/initialized'})
            catalog=exchange({'id':2,'method':'tools/list'})
            print('tools/list',catalog['tools'][0]['name'])
            result=exchange({'id':3,'method':'tools/call','params':{'name':'lookup_hours','arguments':{'place':place}}})
            print('tools/call',result['content'][0]['text'])
        finally:
            child.stdin.close()

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--serve', action='store_true')
    parser.add_argument('place',nargs='?',default='E06')
    opts=parser.parse_args()
    server() if opts.serve else client(opts.place)
