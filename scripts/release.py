"""Deploy complete snapshots and bounded rollback via S3 and CloudFront.

S3 objects prefixed `_project6/` are operational metadata; site root is public only via CloudFront.
"""
import argparse,json,os,re,subprocess,sys,tempfile
from pathlib import Path

bucket=os.environ['SITE_BUCKET']; dist=os.environ['CLOUDFRONT_DISTRIBUTION_ID']
prefix=f's3://{bucket}'

def aws(*args,allow_missing=False):
    p=subprocess.run(['aws',*args],text=True,capture_output=True)
    if p.returncode and not allow_missing: raise RuntimeError('AWS command failed: '+p.stderr[-1500:])
    return p

def validate_id(value):
    if not re.fullmatch('[a-zA-Z0-9_-]{7,64}',value): raise ValueError('Invalid release identifier')
    return value

def metadata_read(key):
    p=aws('s3','cp',f'{prefix}/_project6/{key}','-',allow_missing=True)
    return json.loads(p.stdout) if p.returncode==0 else None

def metadata_write(key,value):
    with tempfile.NamedTemporaryFile(mode='w',suffix='.json') as f:
        json.dump(value,f,indent=2);f.flush()
        aws('s3','cp',f.name,f'{prefix}/_project6/{key}','--content-type','application/json')

def invalidate():
    p=aws('cloudfront','create-invalidation','--distribution-id',dist,'--paths','/*','--output','json')
    invalid=json.loads(p.stdout)['Invalidation']['Id']
    aws('cloudfront','wait','invalidation-completed','--distribution-id',dist,'--id',invalid)
    print('CloudFront invalidation complete:',invalid)

def snapshot(release):
    validate_id(release)
    # Store an immutable full copy; deletion of any site file at source is reflected in root on deployment.
    aws('s3','sync','site/',f'{prefix}/_project6/releases/{release}/','--delete')

def restore(release):
    validate_id(release)
    with tempfile.TemporaryDirectory() as temp:
        aws('s3','sync',f'{prefix}/_project6/releases/{release}/',temp+'/')
        if not (Path(temp)/'release.json').exists(): raise RuntimeError('Missing snapshot release manifest')
        if json.loads((Path(temp)/'release.json').read_text())['release_id']!=release:
            raise RuntimeError('Snapshot mismatch')
        aws('s3','sync',temp+'/',prefix+'/','--delete','--exclude','_project6/*')
    invalidate()

def deploy(release):
    validate_id(release)
    if json.loads(Path('site/release.json').read_text())['release_id']!=release:raise RuntimeError('Release manifest mismatch')
    good=metadata_read('known-good.json')
    if good is None:
        # First use: backup the existing Project 5 site as a baseline before overwriting.
        with tempfile.TemporaryDirectory() as temp:
            aws('s3','sync',prefix+'/',temp+'/','--exclude','_project6/*')
            if (Path(temp)/'index.html').exists():
                baseline='baseline_'+(os.environ.get('CODEBUILD_BUILD_NUMBER','initial'))
                (Path(temp)/'release.json').write_text(json.dumps({'release_id':baseline}))
                aws('s3','sync',temp+'/',f'{prefix}/_project6/releases/{baseline}/')
                metadata_write('known-good.json',{'release_id':baseline})
                good={'release_id':baseline}
    snapshot(release)
    metadata_write('attempt.json',{'release_id':release,'previous_good':good['release_id'] if good else None,'status':'deploying'})
    restore(release)
    metadata_write('attempt.json',{'release_id':release,'previous_good':good['release_id'] if good else None,'status':'deployed_unverified'})

def promote(release):
    current=metadata_read('attempt.json')
    if not current or current['release_id']!=release: raise RuntimeError('No matching deployment attempt')
    metadata_write('known-good.json',{'release_id':release})
    metadata_write('attempt.json',{**current,'status':'verified'})

def rollback(release):
    current=metadata_read('attempt.json')
    if not current or current['release_id']!=release: raise RuntimeError('Rollback must target currently attempted release')
    old=current.get('previous_good')
    if not old: raise RuntimeError('No known-good snapshot; manual operator intervention required')
    if old==release: raise RuntimeError('Rollback target equals failed release')
    restore(old)
    metadata_write('attempt.json',{**current,'status':'rolled_back','restored_release':old})
    return old

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('operation',choices=['deploy','promote','rollback','status']);p.add_argument('--release');a=p.parse_args()
    if a.operation=='status': print(json.dumps({'known_good':metadata_read('known-good.json'),'attempt':metadata_read('attempt.json')},indent=2))
    else:
        if not a.release:p.error('--release required')
        result={'deploy':deploy,'promote':promote,'rollback':rollback}[a.operation](a.release)
        if result:print(result)
