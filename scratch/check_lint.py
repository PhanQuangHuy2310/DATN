import subprocess
import json

p = subprocess.run(
    'npx eslint src vite.config.js -f json',
    cwd='web_client',
    shell=True,
    capture_output=True,
    encoding='utf-8',
    errors='replace'
)
idx = p.stdout.find('[')
data = json.loads(p.stdout[idx:])
for d in data:
    if d['messages']:
        rel_path = d['filePath'].split('web_client\\')[-1]
        print(f"=== {rel_path} ({len(d['messages'])} issues) ===")
        for m in d['messages']:
            print(f"  Line {m['line']}:{m['column']} [{m['ruleId']}]: {m['message']}")

