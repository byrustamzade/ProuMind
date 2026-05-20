class ChunkingService:
    def split_text(
        self,
        text: str,
        chunk_size: int = 1200,
        overlap: int = 200,
    ) -> list[str]:
        cleaned_text = text.strip()
        if not cleaned_text:
            return []

        if chunk_size <= 0:
            raise ValueError("chunk_size must be a positive integer")
        if overlap < 0:
            raise ValueError("overlap cannot be negative")
        if overlap >= chunk_size:
            raise ValueError("overlap must be smaller than chunk_size")

        chunks = []
        start = 0
        text_length = len(cleaned_text)
        step = chunk_size - overlap

        while start < text_length:
            end = start + chunk_size
            if end < text_length:
                split_at = cleaned_text.rfind(" ", start, end)
                if split_at > start + (chunk_size // 2):
                    end = split_at

            chunk = cleaned_text[start:end].strip()

            if chunk:
                chunks.append(chunk)

            start += step

        return chunks


chunking_service = ChunkingService()
