class ContextService:
    def prepare_chunks(
        self,
        chunks: list[dict],
        max_chunks: int = 5,
        max_chars_per_chunk: int = 1800,
    ) -> list[dict]:
        unique_chunks = []
        seen_texts = set()

        for chunk in chunks:
            text = (chunk.get("text") or "").strip()

            if not text:
                continue

            normalized = self._normalize_text(text)

            if normalized in seen_texts:
                continue

            seen_texts.add(normalized)

            chunk["text"] = text[:max_chars_per_chunk]
            unique_chunks.append(chunk)

            if len(unique_chunks) >= max_chunks:
                break

        return unique_chunks

    def build_context(
        self,
        retrieved_chunks: list[dict],
        graph_context: list[dict],
    ) -> str:
        parts = []

        if retrieved_chunks:
            chunk_parts = []

            for index, result in enumerate(retrieved_chunks, start=1):
                chunk_parts.append(
                    f"""
Source {index}
Document: {result.get("document_title")}
Chunk ID: {result.get("chunk_id")}
Text:
{result.get("text")}
""".strip()
                )

            parts.append(
                "DOCUMENT CONTEXT:\n\n" + "\n\n---\n\n".join(chunk_parts)
            )

        if graph_context:
            graph_lines = []

            for item in graph_context:
                entity = item.get("entity") or {}
                related = item.get("related") or {}
                relationship = item.get("relationship")

                if not entity:
                    continue

                if related and relationship:
                    graph_lines.append(
                        f"{entity.get('type')}:{entity.get('name')} "
                        f"-[{relationship}]- "
                        f"{related.get('type')}:{related.get('name')}"
                    )
                else:
                    graph_lines.append(
                        f"{entity.get('type')}:{entity.get('name')}"
                    )

            graph_lines = list(dict.fromkeys(graph_lines))

            if graph_lines:
                parts.append(
                    "KNOWLEDGE GRAPH CONTEXT:\n\n" + "\n".join(graph_lines)
                )

        return "\n\n====================\n\n".join(parts)

    def _normalize_text(self, text: str) -> str:
        return " ".join(text.lower().split())


context_service = ContextService()