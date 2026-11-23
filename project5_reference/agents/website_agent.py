from pathlib import Path
from .common import ROOT, llm_json, log_message

SYSTEM = """You are the Website Agent. Inspect the supplied static website inventory and
report whether at least five distinct HTML pages, shared navigation, responsive styling,
a client-side interactive feature, and a custom 404 page exist. Do not invent files.
Return JSON keys: passed, page_files, checks, issues, recommended_actions."""

def run(run_id):
    pages = sorted(p.name for p in (ROOT / "website").glob("*.html"))
    assets = [p.name for p in (ROOT / "website").iterdir() if p.is_file()]
    result, _, _ = llm_json("WebsiteAgent", "Inspect static website deliverables", SYSTEM,
                            {"html_pages": pages, "site_files": assets}, run_id)
    log_message(run_id, "WebsiteAgent", "Orchestrator", "website_inventory", result)
    return result
