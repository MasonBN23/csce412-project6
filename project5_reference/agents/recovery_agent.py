from .common import llm_json, log_message

SYSTEM = """You are the Recovery Agent. Diagnose the supplied real failure evidence. Propose
one minimal, reversible corrective action. Never execute changes. Return JSON keys:
diagnosis, evidence, proposed_action, rollback, confidence, requires_human_approval (must be true)."""

def diagnose(run_id, evidence):
    result, _, _ = llm_json("RecoveryAgent", "Diagnose controlled website delivery failure", SYSTEM,
                            {"failure_evidence": evidence}, run_id)
    log_message(run_id, "RecoveryAgent", "Orchestrator", "recovery_proposal", result)
    return result
