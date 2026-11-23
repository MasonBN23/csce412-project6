from .common import llm_json, log_message

SYSTEM = """You are the Requirements Agent for a student cloud engineering project.
Convert requirements into an ordered, testable task plan. Separate human-only steps,
read-only checks, and consequential operations requiring explicit approval. Do not claim
anything has been deployed. Return JSON keys: project, tasks (array of objects with id,
owner, action, depends_on, approval_required, acceptance_test), risks."""

def run(run_id, goal):
    result, analysis, model = llm_json("RequirementsAgent", "Decompose project requirements", SYSTEM,
                                       {"goal": goal}, run_id)
    log_message(run_id, "RequirementsAgent", "Orchestrator", "task_plan", result)
    return result
