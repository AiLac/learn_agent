"""JDK 17+ and Python 3.9+. Scripted or live decisions share the same Java host."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.error
import urllib.request

HERE = Path(__file__).resolve().parent
EVIDENCE = HERE.parents[1] / 'data/hk-study-rooms/search-v2/evidence.json'
CASES = ('sat', 'sun', 'ambiguous', 'timeout', 'early', 'wrong', 'repeat', 'replay', 'forbidden', 'skip', 'missing-day')
SYSTEM = ('核验花园街学生自修室 E06 的11月普通非节假日周末19:00是否开放。每轮只选择一个动作。'
          '未指定星期用 ask_day。指定星期用 lookup_hours 取得时段后用 finish 报告。'
          '引用必须来自本次观察。只读工具超时可重试一次或报告 unknown。')
def tool(name, description, properties):
    return {'type': 'function', 'function': {'name': name, 'description': description,
            'parameters': {'type': 'object', 'properties': properties, 'required': list(properties),
                           'additionalProperties': False}}}

TOOLS = [tool('lookup_hours', '查询指定学生自修室的常规时间表',
              {'place': {'type': 'string', 'enum': ['E06']}}),
         tool('ask_day', '询问用户需要查询周六还是周日', {}),
         tool('finish', '提交待宿主核验的结论；unknown 时 citation 传空字符串',
              {'claim': {'type': 'string', 'enum': ['open', 'closed', 'unknown']},
               'citation': {'type': 'string'}})]

def scripted(case, turn, last):
    cid = 'c1' if case == 'replay' else 'c' + str(turn)
    name, args = 'lookup_hours', {'place': 'E06'}
    if case == 'skip':
        name, args = 'finish', {'claim': 'unknown', 'citation': ''}
    elif case == 'ambiguous' or (last and last['status'] == 'NEED_DAY'):
        name, args = 'ask_day', {}
    elif case == 'forbidden':
        name, args = 'book_room', {}
    elif case == 'early' or (last and last['status'] == 'FOUND' and case not in ('repeat','replay')):
        name = 'finish'
        args = {'claim': 'closed' if case in ('sun', 'wrong') else 'open', 'citation': 'hours:E06'}
    elif last and last['status'] == 'TIMEOUT':
        name, args = 'finish', {'claim': 'unknown', 'citation': ''}
    return cid, name, args

def live(messages):
    url = os.environ['AGENT_CHAT_URL']
    request = urllib.request.Request(url, method='POST', headers={
        'Authorization': 'Bearer ' + os.environ['AGENT_API_KEY'], 'Content-Type': 'application/json'},
        data=json.dumps({'model': os.environ['AGENT_MODEL'], 'messages': messages,
                         'tools': TOOLS, 'tool_choice': 'required'}).encode())
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            msg = json.load(response)['choices'][0]['message']
    except urllib.error.HTTPError as exc:
        raise ValueError('model HTTP ' + str(exc.code)) from None
    calls = msg.get('tool_calls') or []
    if len(calls) != 1:
        raise ValueError('lesson requires exactly one tool proposal')
    call = calls[0]
    if call.get('type') != 'function':
        raise ValueError('unsupported proposal type')
    return call['id'], call['function']['name'], json.loads(call['function']['arguments'])

def wire(cid, name, args):
    fields = {'lookup_hours': ['place'], 'ask_day': [], 'finish': ['claim', 'citation']}
    if not isinstance(args, dict) or (name in fields and set(args) != set(fields[name])):
        raise ValueError('invalid argument keys')
    values = [cid, name] + [args[k] for k in fields.get(name, [])]
    if any(not isinstance(v, str) or any(c in v for c in '\r\n\t') for v in values):
        raise ValueError('invalid argument type or delimiter')
    return '\t'.join((values + ['', ''])[:4]) + '\n'

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('case', choices=CASES)
    ap.add_argument('--live', action='store_true')
    opt = ap.parse_args()
    if opt.live and opt.case not in ('sat', 'sun', 'ambiguous','timeout'):
        ap.error('faulty model proposals are replay-only')
    if opt.live and any(not os.environ.get(k) for k in ('AGENT_CHAT_URL','AGENT_MODEL','AGENT_API_KEY')):
        ap.error('set AGENT_CHAT_URL, AGENT_MODEL and AGENT_API_KEY for your provider')
    day = {'sun':'SUN', 'ambiguous':'UNKNOWN', 'missing-day':'UNKNOWN'}.get(opt.case, 'SAT')
    prompt = '11月普通非节假日，' + {'SAT':'周六','SUN':'周日','UNKNOWN':'周末'}[day] + '19:00花园街学生自修室按表开放吗？'
    cards = json.loads(EVIDENCE.read_text(encoding='utf-8'))['documents']
    card = next(x for x in cards if x['id']=='hours:E06')
    hours = card['weekday_intervals'].get({'SAT':'6','SUN':'7'}.get(day,''), 'unspecified')
    messages = [{'role':'system','content':SYSTEM},{'role':'user','content':prompt}]
    print('mode=' + ('live' if opt.live else 'scripted') + ' case=' + opt.case)
    with subprocess.Popen(['java','-Dfile.encoding=UTF-8',str(HERE/'AgentHost.java'),day,hours,
                           str(opt.case=='timeout').lower()], stdin=subprocess.PIPE,
                          stdout=subprocess.PIPE, text=True, encoding='utf-8') as host:
        last = None
        try:
            for turn in range(1, 5):
                cid, name, args = live(messages) if opt.live else scripted(opt.case, turn, last)
                host.stdin.write(wire(cid, name, args))
                host.stdin.flush()
                parts = host.stdout.readline().rstrip('\r\n').split('\t')
                if len(parts) != 5:
                    raise ValueError('missing Java host response')
                kind, status, detail, rounds, attempts = parts
                print(f'{cid} {name} -> {status} {detail} | rounds={rounds} toolAttempts={attempts}')
                if kind == 'END':
                    return 0
                last = {'status':status, 'detail':detail}
                messages.extend([{'role':'assistant','content':None,'tool_calls':[{'id':cid,'type':'function',
                    'function':{'name':name,'arguments':json.dumps(args,ensure_ascii=False)}}]},
                    {'role':'tool','tool_call_id':cid,'content':json.dumps(last, ensure_ascii=False)}])
        finally:
            host.stdin.close()
    raise ValueError('host did not reach a terminal state')

if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, IndexError) as exc:
        sys.exit('Agent lab stopped: ' + str(exc))
