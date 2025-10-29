from __future__ import annotations

import json
from typing import List, Optional, Dict, Any

from groq import Groq

from tdp_secrets import GROQ_API_KEY

SYSTEM_PROMPT = (
    "You are an expert software requirements engineer. "
    "Given a list of functional requirements (FRs), produce a structured set of high-quality, testable Non-Functional Requirements (NFRs). "
    "Follow these rules strictly: "
    "(1) Map each NFR to one or more FR IDs. "
    "(2) Cover only the NFR categories that are realistically relevant to the given FRs and domain. Example categories: "
    "performance, scalability, reliability/availability, security, privacy, usability/accessibility, maintainability, "
    "observability, portability, compatibility, compliance/regulatory, and cost/efficiency. "
    "(3) Make each NFR SMART: include measurable thresholds, metrics, and clear acceptance criteria. Use concrete numbers (e.g., p95 latency, uptime %, MTTR minutes, error budgets). "
    "(4) Include rationale that explains the business/technical motivation. "
    "(5) Include verification method (test, monitoring, audit, inspection, analysis) and, if relevant, target environment and workload assumptions. "
    "(6) Output strictly valid JSON matching the `nfr_schema` below—no extra commentary."
)

NFR_SCHEMA_STR = json.dumps({
    "type": "object",
    "properties": {
        "domain": {"type": "string"},
        "source_functional_requirements": {
            "type": "array",
            "items": {"type": "object", "properties": {"id": {"type": "string"}, "text": {"type": "string"}},
                      "required": ["id", "text"]}
        },
        "non_functional_requirements": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "category": {"type": "string"},
                    "statement": {"type": "string"},
                    "rationale": {"type": "string"},
                    "linked_functional_requirements": {"type": "array", "items": {"type": "string"}},
                    "acceptance_criteria": {"type": "array", "items": {"type": "string"}},
                    "metrics": {"type": "array", "items": {"type": "string"}},
                    "priority": {"type": "string"},
                    "verification_method": {"type": "string"}
                },
                "required": [
                    "id", "category", "statement", "rationale", "linked_functional_requirements",
                    "acceptance_criteria", "metrics", "priority", "verification_method"
                ]
            }
        }
    },
    "required": ["domain", "source_functional_requirements", "non_functional_requirements"]
}, indent=2)

GENERATION_INSTRUCTIONS = (
    "Return JSON only. Use concise but precise language. "
    "Choose realistic thresholds (e.g., p95 latency under 300 ms for core APIs unless domain dictates otherwise). "
    "Where domain specifics matter (e.g., payments), prioritize security, privacy, auditability, and compliance (PCI-DSS, SOC2, ISO 27001 as relevant). "
)

DEFAULT_MODEL = "llama-3.1-8b-instant"


class NFRGenerator:
    def __init__(self, model: str):
        if not model:
            model = DEFAULT_MODEL
        api_key = GROQ_API_KEY
        if not api_key:
            raise RuntimeError("GROQ_API_KEY is not set. Export your Groq API key first.")
        self.client = Groq(api_key=api_key)
        self.model = model

    def generate(self, functional_requirements: List[str], domain: Optional[str] = None) -> Dict[str, Any]:
        fr_objs = [{"id": f"FR-{i + 1}", "text": fr.strip()} for i, fr in enumerate(functional_requirements) if
                   fr.strip()]
        if not fr_objs:
            raise ValueError("No functional requirements provided.")
        domain = domain or "General software system"

        user_payload = {
            "domain": domain,
            "source_functional_requirements": fr_objs,
            "schema": json.loads(NFR_SCHEMA_STR),
            "instructions": GENERATION_INSTRUCTIONS,
        }

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)}
        ]

        completion = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.2,
            max_tokens=4096,
            top_p=0.9,
            stream=False,
        )
        content = completion.choices[0].message.content
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            start = content.find('{');
            end = content.rfind('}')
            if start != -1 and end != -1 and end > start:
                data = json.loads(content[start:end + 1])
            else:
                raise
        return data
