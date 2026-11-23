from .common import ROOT, llm_json, log_message
from scripts.verify import verify

SYSTEM = """You are the Verification Agent. Interpret real HTTP/TLS/AWS verification evidence.
Do not convert missing evidence into success. Return JSON keys: overall_pass, failed_checks,
interpretation, next_steps."""

def run(run_id, cfg):
    evidence = verify(run_id, cfg)
    result, _, _ = llm_json("VerificationAgent", "Interpret live website and security checks", SYSTEM,
                            {"verification_evidence": evidence}, run_id)
    log_message(run_id, "VerificationAgent", "Orchestrator", "verification_result", result)
    return evidence, result
