import json
runs = {
  'v0': 'runs/v0_B_base_openai_20260729T101259498936.json',
  'v1': 'runs/v1_B_base_openai_20260729T102122533988.json',
  'v2': 'runs/v2_B_base_openai_20260729T102409753230.json',
  'v3': 'runs/v3_B_base_openai_20260729T103303391718.json'
}
for v, f in runs.items():
    d = json.load(open(f, encoding='utf-8'))
    av = d.get('artifact_version', '')
    fails = [r for r in d['results'] if not r['result']['passed']]
    print(f'--- {v} ({av}): {len(fails)} failures ---')
    for r in fails:
        res = r['result']
        rid = r['id']
        actual = res.get('actual_tool_calls', [])
        tool_names = [t['name'] for t in actual] if actual else ['(no tool)']
        print(f'  {rid} | {res.get("failure_type")} | {tool_names} | {res.get("failures")}')
