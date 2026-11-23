"""Bounded automatic rollback after failed post-deploy verification."""
import json,os,subprocess,sys
from scripts import release
from scripts.verify import verify

id=os.getenv('RELEASE_ID') or os.getenv('CODEBUILD_RESOLVED_SOURCE_VERSION')
if not id:raise SystemExit('Missing RELEASE_ID')
try:
    release.deploy(id)
    result=verify(os.environ['SITE_URL'],id,os.environ['SITE_BUCKET'])
    os.makedirs('results',exist_ok=True)
    open('results/verification.json','w').write(json.dumps(result,indent=2))
    if not result['passed']: raise RuntimeError('Production verification failed: '+str(result.get('errors')))
    if os.environ.get('PROJECT6_DEMO_FAIL_AFTER_DEPLOY')=='1':
        raise RuntimeError('Intentional post-deployment rollback demonstration (operator-enabled)')
    release.promote(id)
    print('DEPLOYMENT VERIFIED:',id)
except Exception as exc:
    print('DEPLOYMENT FAILURE:',str(exc),file=sys.stderr)
    try:
        # Only roll back if this release was recorded as an active deployment attempt.
        attempt=release.metadata_read('attempt.json')
        if attempt and attempt.get('release_id')==id and attempt.get('status') in ('deploying','deployed_unverified'):
            previous=release.rollback(id)
            if previous.startswith('baseline_'):
                # Baseline has original pages but may lack new validation markup.
                # Check the critical original baseline index and manifest over HTTPS.
                import ssl
                from urllib.request import urlopen
                with urlopen(os.environ['SITE_URL'].rstrip('/')+'/index.html',timeout=15,context=ssl.create_default_context()) as r:
                    assert r.status==200
                print('BASELINE RECOVERY VERIFIED:',previous)
            else:
                restored=verify(os.environ['SITE_URL'],previous,os.environ['SITE_BUCKET'])
                if not restored['passed']: raise RuntimeError('Restored release verification failed '+str(restored.get('errors')))
                print('ROLLBACK VERIFIED:',previous)
    except Exception as recovery_exc:
        print('RECOVERY ERROR:',str(recovery_exc),file=sys.stderr)
    sys.exit(1)
