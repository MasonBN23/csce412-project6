import argparse, json, os, time
from pathlib import Path
from .common import ROOT, config, new_run_id, log_message, log_tool, approval
from .requirements_agent import run as requirements_run
from .website_agent import run as website_run
from .infrastructure_agent import assess, execute
from .security_agent import run as security_run
from .verification_agent import run as verification_run
from .recovery_agent import diagnose
from infra.deploy import session, inspect_security

GOAL = """Design, deploy, and verify a secure five-page static website on private S3 through
CloudFront OAC, Route 53 and an ACM certificate. Require human approval for consequential changes."""

def plan():
    rid = new_run_id()
    print("Run ID:", rid)
    req = requirements_run(rid, GOAL)
    site = website_run(rid)
    print(json.dumps({"requirements_plan": req, "website_review": site}, indent=2))
    return 0 if site.get("passed") else 1

def deploy_cmd():
    rid = new_run_id()
    cfg = config()
    plan_result = requirements_run(rid, GOAL)
    site = website_run(rid)
    if not site.get("passed"):
        raise RuntimeError("Website agent found missing requirements; fix website before deployment.")
    infra_result, evidence = assess(rid, cfg)
    if not infra_result.get("ready"):
        print("Infrastructure agent reports readiness concerns:", json.dumps(infra_result, indent=2))
        approval("Proceed only after reviewing these readiness findings and confirming the certificate/domain are ready.", "I REVIEWED AWS READINESS")
    result = execute(rid, cfg)
    print(json.dumps(result, indent=2))
    return 0

def verify_cmd():
    rid = new_run_id()
    cfg = config()
    evidence, interpretation = verification_run(rid, cfg)
    config_evidence = inspect_security(cfg, rid)
    security = security_run(rid, {"live_verification": evidence, "aws_configuration": config_evidence})
    print(json.dumps({"evidence": evidence, "verification_agent": interpretation,
                      "aws_security_configuration": config_evidence, "security_agent": security}, indent=2))
    return 0 if evidence.get("overall_pass") and security.get("secure") else 1

def failure_demo():
    rid = new_run_id()
    cfg = config()
    if os.getenv("ALLOW_AWS_CHANGES", "false").lower() != "true":
        raise RuntimeError("Set ALLOW_AWS_CHANGES=true for the controlled failure exercise.")
    s = session(cfg)
    cf = s.client("cloudfront")
    resp = cf.list_distributions()
    dist = next((d for d in resp.get("DistributionList", {}).get("Items", [])
                 if cfg["DOMAIN"] in d.get("Aliases", {}).get("Items", [])), None)
    if not dist:
        raise RuntimeError("Could not find deployed CloudFront distribution for domain.")
    dist_id = dist["Id"]
    current = cf.get_distribution_config(Id=dist_id)
    original = current["DistributionConfig"]
    etag = current["ETag"]
    if original.get("DefaultRootObject") != "index.html":
        raise RuntimeError("Expected DefaultRootObject=index.html before failure exercise.")
    approval("This introduces a temporary, reversible CloudFront default-root-object error. Website root may fail until restored.", "INTRODUCE CONTROLLED FAILURE", rid)
    broken = dict(original)
    broken["DefaultRootObject"] = "missing-demo-index.html"
    update = cf.update_distribution(Id=dist_id, IfMatch=etag, DistributionConfig=broken)
    log_tool("RecoveryAgent", "cloudfront.update_distribution_introduce_failure",
             {"distribution_id": dist_id, "DefaultRootObject": "missing-demo-index.html"},
             {"status": update["Distribution"]["Status"]}, "success", rid)
    print("Waiting for controlled failure configuration to deploy...")
    cf.get_waiter("distribution_deployed").wait(Id=dist_id)
    inv = cf.create_invalidation(DistributionId=dist_id, InvalidationBatch={
        "Paths": {"Quantity": 1, "Items": ["/*"]}, "CallerReference": rid + "-failure"})
    log_tool("RecoveryAgent", "cloudfront.create_invalidation_failure", {"distribution_id": dist_id, "path": "/*"},
             {"invalidation_id": inv["Invalidation"]["Id"]}, "success", rid)
    cf.get_waiter("invalidation_completed").wait(DistributionId=dist_id, Id=inv["Invalidation"]["Id"])
    import requests
    try:
        r = requests.get("https://" + cfg["DOMAIN"] + "/", timeout=30)
        failure = {"url": "https://" + cfg["DOMAIN"] + "/", "status": r.status_code,
                   "expected_failure_observed": r.status_code >= 400}
    except Exception as e:
        failure = {"error": str(e), "expected_failure_observed": True}
    with (ROOT / "logs" / "failure_recovery.log").open("a", encoding="utf-8") as f:
        f.write(json.dumps({"timestamp": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
                            "event": "controlled_failure_observed", "evidence": failure}) + "\n")
    if not failure["expected_failure_observed"]:
        raise RuntimeError("Controlled failure was not observed; do not claim a successful failure demonstration.")
    proposal = diagnose(rid, failure)
    print("Recovery proposal:", json.dumps(proposal, indent=2))
    approval("Recovery Agent proposes restoring DefaultRootObject=index.html. Review proposal and confirm.", "APPROVE RESTORE INDEX", rid)
    latest = cf.get_distribution_config(Id=dist_id)
    restored = dict(latest["DistributionConfig"])
    restored["DefaultRootObject"] = "index.html"
    fixed = cf.update_distribution(Id=dist_id, IfMatch=latest["ETag"], DistributionConfig=restored)
    log_tool("RecoveryAgent", "cloudfront.update_distribution_restore",
             {"distribution_id": dist_id, "DefaultRootObject": "index.html"},
             {"status": fixed["Distribution"]["Status"]}, "success", rid)
    print("Waiting for recovery deployment...")
    cf.get_waiter("distribution_deployed").wait(Id=dist_id)
    inv = cf.create_invalidation(DistributionId=dist_id, InvalidationBatch={
        "Paths": {"Quantity": 1, "Items": ["/*"]}, "CallerReference": rid + "-recovery"})
    log_tool("RecoveryAgent", "cloudfront.create_invalidation_recovery", {"distribution_id": dist_id, "path": "/*"},
             {"invalidation_id": inv["Invalidation"]["Id"]}, "success", rid)
    cf.get_waiter("invalidation_completed").wait(DistributionId=dist_id, Id=inv["Invalidation"]["Id"])
    evidence, interpretation = verification_run(rid, cfg)
    with (ROOT / "logs" / "failure_recovery.log").open("a", encoding="utf-8") as f:
        f.write(json.dumps({"timestamp": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
                            "event": "recovery_verification", "evidence": evidence,
                            "agent_interpretation": interpretation}) + "\n")
    if not evidence.get("overall_pass"):
        raise RuntimeError("Recovery verification failed. Keep investigating; do not claim recovery.")
    print("Recovery verified.")
    return 0

def main():
    p = argparse.ArgumentParser()
    p.add_argument("command", choices=["plan", "deploy", "verify", "failure-demo"])
    args = p.parse_args()
    return {"plan": plan, "deploy": deploy_cmd, "verify": verify_cmd, "failure-demo": failure_demo}[args.command]()

if __name__ == "__main__":
    raise SystemExit(main())
