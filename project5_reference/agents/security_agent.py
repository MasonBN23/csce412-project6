from .common import llm_json, log_message

SYSTEM = """You are the Security Agent. Evaluate only supplied AWS evidence. Look for public
S3 access, overly broad bucket policies, missing CloudFront OAC, HTTP allowed at viewer,
and invalid/missing ACM certificate. Return JSON keys: secure, findings, severity,
required_remediations. Do not claim checks passed when evidence is missing."""

def run(run_id, evidence):
    result, _, _ = llm_json("SecurityAgent", "Review deployed origin and delivery security", SYSTEM,
                            {"evidence": evidence}, run_id)
    aws_checks = evidence.get("aws_configuration", {}).get("checks", {})
    live_checks = evidence.get("live_verification", {}).get("checks", {})
    required_aws = ["s3_block_public_access", "bucket_policy_cloudfront_only_pattern", "cloudfront_oac", "acm_certificate"]
    required_live = ["https_root", "http_root", "tls_certificate", "direct_s3_anonymous_denied",
                     "page_index.html", "page_about.html", "page_services.html", "page_projects.html", "page_contact.html"]
    deterministic_pass = (all(aws_checks.get(k, {}).get("passed") is True for k in required_aws)
                          and all(live_checks.get(k, {}).get("ok") is True for k in required_live))
    result["configuration_checks_pass"] = deterministic_pass
    result["secure"] = bool(result.get("secure")) and deterministic_pass
    log_message(run_id, "SecurityAgent", "Orchestrator", "security_review", result)
    return result
