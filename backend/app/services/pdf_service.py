from pypdf import PdfReader


class PdfService:
    def extract_text(self, file_path: str) -> str:
        reader = PdfReader(file_path, strict=False)
        pages_text: list[str] = []

        for page in reader.pages:
            text = page.extract_text() or ""
            pages_text.append(text.strip())

        return "\n\n".join(pages_text).strip()


pdf_service = PdfService()
