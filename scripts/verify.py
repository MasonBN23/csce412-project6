import argparse, json, os, ssl, subprocess, sys, time
from html.parser import HTMLParser
from urllib.request import urlopen, Request
from urllib.error import HTTPError

PAGES=['index.html','about.html','services.html','projects.html','contact.html']

class PageParser(HTMLParser):
    def __init__(self):
        super().__init__();self.tags=set();self.ids=set()
    def handle_starttag(self,tag,attrs):
        self.tags.add(tag)
        for k,v in attrs:
            if k=='id':self.ids.add(v)

def fetch(url):
    with urlopen(Request(url,headers={'Cache-Control':'no-cache'}),timeout=15,context=ssl.create_default_context()) as r:
        return r.status,r.read().decode('utf-8')

def verify(url,release,bucket,attempts=8):
    assert url.startswith('https://'), 'Expected HTTPS site URL'
    base=url.rstrip('/')
    result={'release_id':release,'url':url,'checks':{},'passed':False};errors=[]
    for attempt in range(attempts):
        try:
            checks={}
            for page in PAGES:
                status,html=fetch(base+'/'+page)
                parsed=PageParser();parsed.feed(html)
                assert status==200 and {'main','nav','html'}.issubset(parsed.tags),f'{page} missing required structure'
                checks[page]='pass'
                if page=='contact.html':
                    assert {'contact-form','form-status'}.issubset(parsed.ids),'Contact feature markup missing'
            status,body=fetch(base+'/release.json')
            actual=json.loads(body).get('release_id')
            assert status==200 and actual==release,f'Release mismatch expected {release}, got {actual}'
            checks['release']='pass'
            for asset in ('styles.css','script.js'):
                status,body=fetch(base+'/'+asset)
                assert status==200 and len(body)>50,f'{asset} missing'
                if asset=='script.js':
                    assert 'addEventListener' in body and 'mailto:' in body and 'preventDefault' in body,'Contact JS missing'
                checks[asset]='pass'
            checks['https']='pass'
            result['checks']=checks
            break
        except Exception as exc:
            errors.append(str(exc))
            if attempt<attempts-1:time.sleep(10)
    else:
        result['errors']=errors;return result
    try:
        p=subprocess.run(['aws','s3api','get-public-access-block','--bucket',bucket,'--output','json'],capture_output=True,text=True,check=True)
        cfg=json.loads(p.stdout)['PublicAccessBlockConfiguration']
        assert all(cfg[k] for k in ('BlockPublicAcls','IgnorePublicAcls','BlockPublicPolicy','RestrictPublicBuckets'))
        result['checks']['s3_block_public_access']='pass'
        try:
            status,_=fetch(f'https://{bucket}.s3.amazonaws.com/index.html')
            raise AssertionError(f'Anonymous S3 returned {status}')
        except HTTPError as err:
            assert err.code in (403,404),f'Anonymous S3 returned unexpected HTTP {err.code}'
        result['checks']['anonymous_s3_denied']='pass'
        result['passed']=True
    except Exception as exc:
        result.setdefault('errors',[]).append('Security check failed: '+str(exc))
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--release',required=True);p.add_argument('--out',default='results/verification.json');a=p.parse_args()
    result=verify(os.environ['SITE_URL'],a.release,os.environ['SITE_BUCKET'])
    os.makedirs(os.path.dirname(a.out) or '.',exist_ok=True)
    with open(a.out,'w') as f:json.dump(result,f,indent=2)
    print(json.dumps(result,indent=2));sys.exit(0 if result['passed'] else 1)
