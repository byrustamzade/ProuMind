import requests
from openai import OpenAI

from app.core.config import settings


class LLMService:
    def generate_answer(self, question: str, context: str) -> str:
        provider = settings.llm_provider.lower()

        if provider == "openai":
            return self._generate_with_openai(question, context)

        return self._generate_with_ollama(question, context)

    def _build_prompt(self, question: str, context: str) -> str:
        return f"""
You are ProuMind, an enterprise AI knowledge assistant.

Answer the user's question using ONLY the provided context.

Rules:
- If the answer is not in the context, say that the available sources do not contain enough information.
- Do not invent facts.
- Be concise.
- Mention uncertainty when needed.

Context:
{context}

Question:
{question}

Answer:
""".strip()

    def _generate_with_ollama(self, question: str, context: str) -> str:
        prompt = self._build_prompt(question, context)
        return self._generate_raw_with_ollama(prompt)

    def _generate_with_openai(self, question: str, context: str) -> str:
        prompt = self._build_prompt(question, context)
        return self._generate_raw_with_openai(prompt)

    def _generate_raw_with_ollama(self, prompt: str) -> str:
        response = requests.post(
            f"{settings.ollama_base_url}/api/chat",
            json={
                "model": settings.ollama_model,
                "stream": False,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
            },
            timeout=120,
        )

        response.raise_for_status()
        data = response.json()

        return data["message"]["content"].strip()

    def _generate_raw_with_openai(self, prompt: str) -> str:
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required when LLM_PROVIDER=openai")

        client = OpenAI(api_key=settings.openai_api_key)

        response = client.responses.create(
            model=settings.openai_model,
            input=prompt,
        )

        return response.output_text.strip()

    def generate_raw(self, prompt: str) -> str:
        provider = settings.llm_provider.lower()

        if provider == "openai":
            return self._generate_raw_with_openai(prompt)

        return self._generate_raw_with_ollama(prompt)


llm_service = LLMService()
