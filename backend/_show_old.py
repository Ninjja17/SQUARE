lines = open('_old_client.py', encoding='utf-8').read().splitlines()
in_fn = False
depth = 0
for i, l in enumerate(lines):
    if 'def _build_agent_payload' in l:
        in_fn = True
    if in_fn:
        print(f'{i+1:4}: {l}')
        depth += l.count('{') - l.count('}')
        if i > 5 and depth <= 0 and l.strip() == '':
            break
