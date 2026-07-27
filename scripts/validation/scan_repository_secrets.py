from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXCLUDED = {'.git', 'node_modules', '.venv', 'venv', '.next', 'runtime', 'dist', 'build'}
TEXT_SUFFIXES = {'.py','.ps1','.ts','.tsx','.js','.json','.yaml','.yml','.toml','.md','.txt','.env','.ini','.sql','.puml'}
PATTERNS = {
    'OpenAI-style key': re.compile(r'\bsk-[A-Za-z0-9_-]{24,}\b'),
    'Anthropic key': re.compile(r'\bsk-ant-[A-Za-z0-9_-]{20,}\b'),
    'Google API key': re.compile(r'\bAIza[0-9A-Za-z_-]{30,}\b'),
    'Private key': re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
}
ALLOW_FILES = {ROOT/'.env.example'}
findings: list[str] = []
for path in ROOT.rglob('*'):
    if not path.is_file() or any(part in EXCLUDED for part in path.parts) or path in ALLOW_FILES:
        continue
    if path.suffix.lower() not in TEXT_SUFFIXES and path.name not in {'.env.example','.gitignore'}:
        continue
    try:
        text = path.read_text(encoding='utf-8')
    except UnicodeDecodeError:
        continue
    for name, pattern in PATTERNS.items():
        for match in pattern.finditer(text):
            value = match.group(0)
            if value.startswith('sk-...') or 'example' in value.lower():
                continue
            findings.append(f'{path.relative_to(ROOT)}: potential {name}')
if findings:
    raise SystemExit('Potential committed secret(s) detected:\n' + '\n'.join(findings))
print('High-confidence repository secret scan passed.')
