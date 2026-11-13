#!/usr/bin/env python3
"""Check repository-local Markdown links (not links embedded in code blocks)."""
from pathlib import Path
from urllib.parse import unquote
import re
import sys

root = Path(__file__).resolve().parent.parent
errors = []
count = 0
for path in root.rglob('*.md'):
    if '.git' in path.parts:
        continue
    text = re.sub(r'```.*?```', '', path.read_text(encoding='utf-8'), flags=re.S)
    for target in re.findall(r'(?<!!)\[[^\]]+\]\(([^)]+)\)', text):
        target = unquote(target.split('#', 1)[0].strip().split(' ', 1)[0])
        if not target or re.match(r'^(?:https?://|mailto:)', target):
            continue
        count += 1
        if not (path.parent / target).exists():
            errors.append(f'{path.relative_to(root)}: {target}')
print(f'Checked {count} local links; {len(errors)} missing.')
if errors:
    print('\n'.join(errors))
    sys.exit(1)
