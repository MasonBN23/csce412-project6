# Fast start — integrated Project 5 website

1. Install Python 3.11+, Git, AWS CLI v2.
2. `python3 -m venv .venv && source .venv/bin/activate`
3. `pip install -r requirements.txt`
4. `export RELEASE_ID=localtest1234567 && python scripts/build.py && python -m pytest -q tests`
5. `python -m agents.run pipeline && python -m agents.run testing`
6. Create a **private** repo, commit/push with `git init`, `git add .`, `git commit`, and `git push`.
7. Confirm your existing AWS bucket/distribution/domain with `aws sts get-caller-identity` and `aws cloudfront list-distributions`.
8. Create an AWS GitHub Connection in Developer Tools (complete GitHub authorization), an S3 CodePipeline artifact bucket, and two restricted IAM roles. See README for permissions.
9. Configure `SITE_BUCKET`, `SITE_URL=https://csce412masonnguyen1223.me`, `CLOUDFRONT_DISTRIBUTION_ID`, `GITHUB_CONNECTION_ARN`, `GITHUB_REPO`, `GITHUB_BRANCH=main`, `PIPELINE_ROLE_ARN`, `CODEBUILD_ROLE_ARN`, `PIPELINE_ARTIFACT_BUCKET`.
10. `python scripts/setup_pipeline.py --dry-run` then `python scripts/setup_pipeline.py` (creates resources once).
11. Push visible edit to `site/index.html`; inspect CodePipeline and verify live `/release.json` commit hash.
12. Deliberately remove `site/contact.html`; commit/push; Validate fails, DeployAndVerify is skipped, live `/release.json` remains unchanged. Restore file and commit/push.
13. Save truthful console screenshots, CodeBuild logs, agent JSONL evidence, and live release comparison; invite instructor/TA collaborators.

**Important:** Setup script uses AWS CLI `create-project` and `create-pipeline`; rerunning without cleanup/update fails if resources exist. CodeBuild/CodePipeline IAM roles and permissions are not auto-created. The contact form is checked via actual live HTML and JS assets, not browser simulation. Post-deploy rollback requires a previous known-good snapshot and should be demonstrated only after a successful release.

## Optional recovery demonstration

After one or more successful verified releases, temporarily set `PROJECT6_DEMO_FAIL_AFTER_DEPLOY=1` in the CodeBuild **deployment** project environment and push a visible harmless update. The deployment performs real checks, then deliberately flags the release as failed, and the bounded recovery restores the previously verified full snapshot and re-verifies it. The build should be FAILED while the live website displays the previous known-good release. **Remove this environment variable immediately after the experiment** and push a normal successful fix. Do not run this without a verified known-good release.
