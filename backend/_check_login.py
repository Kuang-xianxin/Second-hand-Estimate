import json
import pathlib

p = pathlib.Path('xianyu_storage_state.json')
if p.exists():
    data = json.loads(p.read_text())
    cookies = data.get('cookies', [])
    print(f'Storage state exists: {len(cookies)} cookies')
    for c in cookies[:5]:
        name = c.get('name', '')
        val = c.get('value', '')[:30]
        print(f'  {name}: {val}...')
else:
    print('No storage state file')

p2 = pathlib.Path('xianyu_cookies.txt')
if p2.exists():
    data = p2.read_text()
    print(f'Cookie file exists: {len(data)} bytes')
else:
    print('No cookie file')
