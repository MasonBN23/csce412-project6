"""Five real agents with structured handoff, tool execution, evidence and optional LLM review.

Actions are allowlisted; generated text is never executed as code or shell commands.
"""
import argparse, json, os, subprocess, sys, urllib.request
from datetime import datetime,timezone
from pathlib import Path

LOG=Path('results/agents.jsonl')

def emit(role,action,data):
    LOG.parent.mkdir(exist_ok=True)
    record={'at':datetime.now(timezone.utc).isoformat(),'agent':role,'action':action,'data':data}
    with LOG.open('a') as f:f.write(json.dumps(record)+'\n')
    print(json.dumps(record))
    return record

def tool(name,argv):
    allowed={'pytest','pipeline-check','release-status'}
    if name not in allowed:raise ValueError('Tool is not allowlisted')
    result=subprocess.run(argv,capture_output=True,text=True,timeout=180)
    evidence={'tool':name,'argv':argv,'returncode':result.returncode,'stdout':result.stdout[-2500:],'stderr':result.stderr[-2500:]}
    emit('tool-runner','result',evidence)
    return evidence

def llm_diagnosis(evidence):
    key=os.getenv('AI_API_KEY')
    if not key:return {'mode':'deterministic','diagnosis':'Check the named failing test or pipeline stage','recommended_action':'Fix the observed error; rerun validation','evidence':evidence}
    endpoint=os.environ.get('AI_API_URL','https://api.openai.com/v1/chat/completions')
    if not endpoint.startswith('https://'):raise ValueError('AI endpoint must use HTTPS')
    prompt='Analyze CI/CD failure using only the following execution evidence. Return JSON with keys observed_failure, root_cause, affected_stage, recommended_action, evidence. Do not suggest directly executing commands. '+json.dumps(evidence)[-9000:]
    payload={'model':os.getenv('AI_MODEL','gpt-4o-mini'),'messages':[{'role':'system','content':'You are a cautious CI/CD failure analyst. Do not invent evidence.'},{'role':'user','content':prompt}],'response_format':{'type':'json_object'}}
    request=urllib.request.Request(endpoint,json.dumps(payload).encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'},method='POST')
    with urllib.request.urlopen(request,timeout=25) as response:
        obj=json.load(response)
    return {'mode':'llm','analysis':json.loads(obj['choices'][0]['message']['content'])}

def pipeline_agent():
    config=Path('config/pipeline.json')
    try: obj=json.loads(config.read_text())
    except Exception as e:raise RuntimeError('Cannot parse pipeline JSON: '+str(e))
    names=[s['name'] for s in obj['pipeline']['stages']]
    assert names==['Source','Validate','DeployAndVerify'],names
    assert Path('buildspec-test.yml').is_file() and Path('buildspec-deploy.yml').is_file()
    evidence=tool('pipeline-check',[sys.executable,'-c','import yaml;[yaml.safe_load(open(x)) for x in ("buildspec-test.yml","buildspec-deploy.yml")]'])
    emit('pipeline-engineer','pipeline-reviewed',{'stages':names,'yaml_check':evidence['returncode']})
    return evidence['returncode']==0

def testing_agent():
    evidence=tool('pytest',[sys.executable,'-m','pytest','-q','tests','--junitxml=results/pytest.xml'])
    emit('test-engineer','test-evaluated',{'pass':evidence['returncode']==0,'evidence':evidence})
    return evidence['returncode']==0

def verification_agent():
    p=Path('results/verification.json')
    if not p.exists():emit('verification-engineer','missing-evidence',{});return False
    result=json.loads(p.read_text())
    emit('verification-engineer','production-evidence-reviewed',{'passed':result.get('passed'), 'checks':result.get('checks'),'errors':result.get('errors')})
    return bool(result.get('passed'))

def diagnosis_agent(path):
    evidence=Path(path).read_text()[-12000:] if Path(path).exists() else 'No diagnostic evidence file found'
    try: result=llm_diagnosis(evidence)
    except Exception as e:result={'mode':'deterministic-fallback','error':str(e),'diagnosis':'Review actual recorded test failures','evidence':evidence}
    emit('failure-analyst','diagnosis',result)
    return result

def recovery_agent():
    evidence=tool('release-status',[sys.executable,'-m','scripts.release','status'])
    emit('recovery-coordinator','recovery-plan',{'approved_automatic_action':'Only rollback of current failed attempt to pinned known-good snapshot','unrestricted_changes':'Require operator approval','status':evidence})
    return evidence['returncode']==0

def main():
    p=argparse.ArgumentParser();p.add_argument('role',choices=['pipeline','testing','verification','diagnosis','recovery','all']);p.add_argument('--evidence',default='results/verification.json');a=p.parse_args()
    roles={'pipeline':pipeline_agent,'testing':testing_agent,'verification':verification_agent,'diagnosis':lambda:diagnosis_agent(a.evidence),'recovery':recovery_agent}
    if a.role=='all':
        ok=pipeline_agent() and testing_agent()
    else:
        result=roles[a.role]();ok=result is not False
    sys.exit(0 if ok else 1)
if __name__=='__main__':main()
