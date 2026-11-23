# CSCE 412 Project 6 — CloudForge CI/CD and AI agents

**Status:** Repository-ready implementation template. It has not been deployed to your AWS account or committed to GitHub. The `site/` contains the actual CloudForge Project 5 five-page website from the supplied project archive.

## Architecture

GitHub private repo (`main`) → AWS CodePipeline Source (CodeConnections) → CodeBuild Validate (predeploy quality gate) → CodeBuild DeployAndVerify → private S3 origin → CloudFront invalidation → HTTPS live verification → mark known-good. A bounded recovery process restores the most recent verified *complete* S3 snapshot, invalidates CloudFront, and re-verifies it when deployment verification fails.

Existing Route 53 DNS, ACM certificate, CloudFront OAC/OAI and private S3 bucket from Project 5 are reused. No new AWS runtime service is required except the approved CodePipeline and CodeBuild (plus their existing IAM roles and S3 artifact bucket).

## Five specialized agent roles

1. **Pipeline engineer** parses pipeline config, validates stage order and buildspec YAML with an executable tool.
2. **Test engineer** executes pytest and interprets exit code, XML report and output.
3. **Verification engineer** reads actual production verification JSON and reports pass/fail per check.
4. **Failure analyst** uses real test or verification output and optionally calls an LLM API with an evidence-grounded diagnosis; fallback works without LLM.
5. **Recovery coordinator** executes a read-only AWS status tool and describes a narrowly scoped recovery action. The deterministic deployment workflow runs bounded rollback from an approved snapshot; LLM output is *never* executed as commands.

All agents exchange evidence in `results/agents.jsonl`, and CodeBuild output shows their actions. Do not log API keys. Configure `AI_API_KEY` through a secured environment mechanism outside the repo if demonstrating an actual LLM call; without this it falls back to deterministic guidance. The AI integration uses the OpenAI-compatible `/chat/completions` format, JSON output mode, and `AI_MODEL` (provider/model compatibility may need adjustment).

## Setup

Requirements: Python 3.11+, AWS CLI v2, AWS credentials for a restricted deploy identity, Git, GitHub private repository, existing working Project 5 domain/bucket/distribution. Install:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Fill in values; load the environment from .env using your local shell or secure environment loader.
export RELEASE_ID=$(git rev-parse HEAD)
python scripts/build.py
python -m agents.run pipeline
python -m agents.run testing
```

Required deploy variables: `SITE_BUCKET`, `CLOUDFRONT_DISTRIBUTION_ID`, `SITE_URL`, `RELEASE_ID`. Required setup variables: `GITHUB_CONNECTION_ARN`, `GITHUB_REPO` (`owner/repo`), `GITHUB_BRANCH`, `PIPELINE_ROLE_ARN`, `CODEBUILD_ROLE_ARN`, `PIPELINE_ARTIFACT_BUCKET`. Optional AI variables: `AI_API_KEY`, `AI_API_URL`, `AI_MODEL`. Keep any local `.env` out of Git.

### AWS one-time configuration

1. Confirm CloudFront redirects HTTP→HTTPS, ACM TLS certificate, S3 Block Public Access all four enabled, CloudFront OAC (or OAI), and direct anonymous S3 reads forbidden. Confirm public website already works.
2. Create private GitHub repository and push this source. In AWS Developer Tools > Connections create a GitHub connection, install/authorize GitHub App for that repo, and **complete** the pending connection handshake in the AWS console. A `PENDING` connection cannot trigger the pipeline.
3. Provision two restricted IAM roles in your account. **CodePipeline role** needs the GitHub connection `UseConnection`, CodeBuild `StartBuild`/`BatchGetBuilds` scoped to the two projects and S3 artifact read/write on the artifact bucket. **CodeBuild role** needs read/write to only the existing website S3 bucket (including `_project6/` snapshots), `s3:GetBucketPublicAccessBlock`, `cloudfront:CreateInvalidation`/`GetInvalidation` on your distribution, and log publishing for its builds. Add CodeBuild S3 artifact bucket read permission and log permissions as required. Do not use administrator permissions long term.
4. Set all setup environment variables and inspect generated configs with `python scripts/setup_pipeline.py --dry-run`. After reviewing AWS IAM roles and environment values run `python scripts/setup_pipeline.py`. This creates CodeBuild projects and CodePipeline. If resources already exist, update them rather than creating duplicates.
5. Pipeline Source uses the designated GitHub branch with automatic change detection; GitHub push should trigger Source > Validate > DeployAndVerify. The pipeline passes `#{SourceVariables.CommitId}` as `RELEASE_ID` to both CodeBuild projects. CodeBuild uses source ZIP artifacts with the buildspecs from this repository.
6. Check the CodePipeline execution and CodeBuild logs, live domain, and `aws s3 cp s3://$SITE_BUCKET/_project6/known-good.json -` for the current verified release ID.

**Important:** First deployment auto-snapshots an existing site as a baseline if no previously verified release is registered. A baseline may not meet the new five-page verifier, so the fallback verifies HTTPS homepage reachability only. For best recovery assurance, deploy a complete valid five-page release first, and run a subsequent release as the rollback demo. Do not run concurrent pipeline deployments against the same S3 root; enable serialized execution in pipeline settings if supported and avoid manual overlapping deploys.

### What pipeline commands actually run

Pre-deployment `buildspec-test.yml` performs `scripts/build.py`, pipeline config validation and `pytest` (required pages, navigation links, assets, HTML structure, contact-form JavaScript hook, release manifest). Failed tests stop deployment stage.

Post-deployment `buildspec-deploy.yml` regenerates the release ID, re-runs pytest as a safety check, snapshots full site, syncs it to S3, requests and waits for CloudFront invalidation, checks actual HTTPS pages and assets and release manifest, and checks S3 public access configuration plus anonymous S3 read denial. Successful verification promotes the snapshot to known-good. Failure causes bounded rollback and failing CodeBuild exit status. The contact-form JavaScript feature is statically smoke-checked from its live asset, not executed in a headless browser; for stronger end-to-end functionality verification add a browser test using Playwright and run it inside CodeBuild.

### Commands and evidence

```bash
python -m pytest -q tests --junitxml=results/pytest.xml
python -m agents.run pipeline
python -m agents.run testing
python -m agents.run diagnosis --evidence results/pytest.xml
python -m scripts.release status
# Controlled manual rollback of the current failed attempt ONLY:
python -m scripts.release rollback --release "$RELEASE_ID"
# Live verification when site is deployed:
python -m scripts.verify --release "$RELEASE_ID"
```

Keep chronological logs, CodePipeline execution screenshots/statuses, CodeBuild test output, `results/agents.jsonl`, deployed `release.json`, and rollback evidence for your project submission. `results/` is intentionally ignored: copy relevant sanitized logs into `evidence/` after real executions. No fabricated experiments/logs are provided.

### Required experiments

- **Successful release:** record `known-good.json`, edit visible page, commit/push to main, show automatic successful CodePipeline execution, inspect new `release.json` on HTTPS site.
- **Failed validation:** deliberately remove `site/contact.html` on a temporary test commit, push to main, demonstrate pytest blocks deployment; verify existing live `release.json` remains unchanged. Restore the file and push another commit.
- **Post-deployment recovery (additional):** force a controlled verification failure only in a noncritical demonstration window, confirm `attempt.json` records a failed release, rollback restores full known-good snapshot, invalidation finishes, and live verification passes.
- **Agent analysis:** run `python -m agents.run diagnosis --evidence results/pytest.xml` with actual failed test output; if API configured, show evidence-grounded LLM output in agent logs and relay to recovery coordinator.

## Repository security and submission

Never commit credentials, personal access tokens, secret environment files or private TLS keys. Keep repo **Private** and invite instructor/TA GitHub accounts as collaborators. Paste the exact repo URL into Canvas only after real deployment/test completion. Verify branch protection or review policy as appropriate to keep the deployment branch approved.

**AWS source references:** https://docs.aws.amazon.com/codepipeline/latest/userguide/action-reference-CodestarConnectionSource.html and https://docs.aws.amazon.com/codebuild/latest/userguide/build-spec-ref.html

## Integrated Project 5 inventory

The original `website/` directory was imported into `site/`: `index.html`, `about.html`, `services.html`, `projects.html`, `contact.html`, `styles.css`, and `script.js`. The original Project 5 agent files are preserved in `project5_reference/agents/`; the executable Project 6 agent workflow is `agents/run.py`. The predeploy and live tests match the real CloudForge contact form and mobile navigation.

**Security:** `site/script.js` contains the pre-existing `mailto:` destination from your Project 5 archive. Inspect it before publishing. Do not put AWS keys or AI API keys into website source files.
