from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.schema import Document


class ChunkingService:
    def __init__(self):
        self.parser = SentenceSplitter(
            chunk_size=1024,
            chunk_overlap=150,
        )

    def split_text(self, text: str) -> list[str]:
        document = Document(text=text)

        nodes = self.parser.get_nodes_from_documents([document])

        return [node.text for node in nodes]


chunking_service = ChunkingService()
