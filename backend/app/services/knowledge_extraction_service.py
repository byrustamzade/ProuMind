import json
import re

from app.services.llm_service import llm_service


class KnowledgeExtractionService:
    def extract(self, text: str) -> dict:
        prompt_context = text[:8000]

        prompt = f"""
Extract a knowledge graph from the text.

Return ONLY valid JSON with this structure:
{{
  "entities": [
    {{
      "name": "Stripe Migration",
      "type": "Project"
    }}
  ],
  "relationships": [
    {{
      "from": "Stripe Migration",
      "from_type": "Project",
      "relation": "DEPENDS_ON",
      "to": "Payment API",
      "to_type": "Service"
    }}
  ]
}}

Allowed entity types:
Person, Company, Client, Project, Task, Service, API, Document, Risk, Decision, Deadline, Technology, Product, Other

Rules:
- Use short clear names.
- Do not invent entities.
- Extract only important business/technical entities.
- Use uppercase relationship names like DEPENDS_ON, BLOCKED_BY, AFFECTS, OWNS, USES, MENTIONS, RELATED_TO.
- Return JSON only.

Text:
{prompt_context}
""".strip()

        raw_response = llm_service.generate_raw(prompt)

        return self._parse_json(raw_response)

    def _parse_json(self, raw_response: str) -> dict:
        cleaned = raw_response.strip()

        fenced_match = re.search(r"```(?:json)?(.*?)```", cleaned, re.DOTALL)
        if fenced_match:
            cleaned = fenced_match.group(1).strip()

        json_match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if json_match:
            cleaned = json_match.group(0)

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            return {
                "entities": [],
                "relationships": [],
            }

        return {
            "entities": data.get("entities", []),
            "relationships": data.get("relationships", []),
        }

    def extract_query_entities(self, question: str) -> list[str]:
        prompt = f"""
    Extract important entity names from this question.

    Return ONLY valid JSON:
    {{
      "entities": ["Stripe Migration", "Payment API"]
    }}

    Question:
    {question}
    """.strip()

        raw_response = llm_service.generate_raw(prompt)
        data = self._parse_json(raw_response)

        entities = data.get("entities", [])

        return [
            entity
            for entity in entities
            if isinstance(entity, str) and entity.strip()
        ]


knowledge_extraction_service = KnowledgeExtractionService()