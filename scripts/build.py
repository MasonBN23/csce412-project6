import json, os, re
from datetime import datetime, timezone
from pathlib import Path

release = os.getenv('RELEASE_ID') or os.getenv('CODEBUILD_RESOLVED_SOURCE_VERSION')
if not release or not re.fullmatch(r'[0-9a-zA-Z_-]{7,64}', release):
    raise SystemExit('RELEASE_ID must be a valid source commit hash or release identifier')
path = Path('site/release.json')
path.write_text(json.dumps({'release_id':release,'built_at':datetime.now(timezone.utc).isoformat()}, indent=2)+'\n')
print(f'Built release {release}')
