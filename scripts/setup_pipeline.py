"""Provision CodeBuild projects and CodePipeline using existing pre-created IAM roles.

Use `--dry-run` to inspect configuration before touching AWS.
"""
import argparse,json,os,subprocess
from pathlib import Path

def required(name):
    val=os.getenv(name)
    if not val:raise RuntimeError('Missing '+name)
    return val

def cmd(args,dry):
    print(' '.join(args[:3])+' ...')
    if not dry:subprocess.run(args,check=True)

def main():
    p=argparse.ArgumentParser();p.add_argument('--dry-run',action='store_true');a=p.parse_args()
    values={
      '__PIPELINE_ROLE_ARN__':required('PIPELINE_ROLE_ARN'),
      '__ARTIFACT_BUCKET__':required('PIPELINE_ARTIFACT_BUCKET'),
      '__CONNECTION_ARN__':required('GITHUB_CONNECTION_ARN'),
      '__GITHUB_REPO__':required('GITHUB_REPO'),
      '__GITHUB_BRANCH__':os.getenv('GITHUB_BRANCH','main')}
    config=json.loads(Path('config/pipeline.json').read_text())
    source=json.dumps(config)
    for k,v in values.items():source=source.replace(k,v)
    pipeline=json.loads(source)
    role=required('CODEBUILD_ROLE_ARN')
    envvars=[{'name':k,'value':required(k),'type':'PLAINTEXT'} for k in ['SITE_BUCKET','CLOUDFRONT_DISTRIBUTION_ID','SITE_URL']]
    for name,buildspec in [('project6-validation','buildspec-test.yml'),('project6-deployment','buildspec-deploy.yml')]:
        project={'name':name,'serviceRole':role,'artifacts':{'type':'CODEPIPELINE'},'source':{'type':'CODEPIPELINE','buildspec':buildspec},'environment':{'type':'LINUX_CONTAINER','image':'aws/codebuild/amazonlinux-x86_64-standard:5.0','computeType':'BUILD_GENERAL1_SMALL','environmentVariables':envvars},'timeoutInMinutes':30}
        target=Path(f'config/generated-{name}.json');target.write_text(json.dumps(project,indent=2))
        cmd(['aws','codebuild','create-project','--cli-input-json','file://'+str(target)],a.dry_run)
    Path('config/generated-pipeline.json').write_text(json.dumps(pipeline,indent=2))
    cmd(['aws','codepipeline','create-pipeline','--cli-input-json','file://config/generated-pipeline.json'],a.dry_run)
    print('Setup complete (or dry run). IAM roles and S3 artifact bucket must exist.')
if __name__=='__main__':main()
