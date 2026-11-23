from .common import llm_json, log_message
from infra.deploy import deploy, discover

SYSTEM = """You are the Infrastructure Agent. Review configuration/discovery evidence and
identify readiness issues. Never assert AWS changes occurred unless tool results prove it.
Return JSON keys: ready, findings, required_human_steps, deployment_plan."""

def assess(run_id, cfg):
    evidence = discover(cfg)
    result, _, _ = llm_json("InfrastructureAgent", "Assess AWS deployment readiness", SYSTEM,
                            {"configuration": cfg, "aws_discovery": evidence}, run_id)
    log_message(run_id, "InfrastructureAgent", "Orchestrator", "infrastructure_assessment", result)
    return result, evidence

def execute(run_id, cfg):
    return deploy(run_id, cfg)
