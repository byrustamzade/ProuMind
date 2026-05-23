from neo4j import GraphDatabase

from app.core.config import settings


class Neo4jService:
    def __init__(self):
        self.driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )

    def close(self):
        self.driver.close()

    def ensure_constraints(self):
        queries = [
            """
            CREATE CONSTRAINT document_id_unique IF NOT EXISTS
            FOR (d:Document) REQUIRE d.id IS UNIQUE
            """,
            """
            CREATE CONSTRAINT entity_key_unique IF NOT EXISTS
            FOR (e:Entity) REQUIRE e.key IS UNIQUE
            """,
        ]

        with self.driver.session() as session:
            for query in queries:
                session.run(query)

    def upsert_document(self, document_id: int, title: str, source_type: str):
        self.ensure_constraints()

        query = """
        MERGE (d:Document {id: $document_id})
        SET d.title = $title,
            d.source_type = $source_type
        RETURN d
        """

        with self.driver.session() as session:
            session.run(
                query,
                document_id=document_id,
                title=title,
                source_type=source_type,
            )

    def upsert_entity(self, name: str, entity_type: str):
        self.ensure_constraints()

        key = self._build_entity_key(name=name, entity_type=entity_type)

        query = """
        MERGE (e:Entity {key: $key})
        SET e.name = $name,
            e.type = $entity_type
        RETURN e
        """

        with self.driver.session() as session:
            session.run(
                query,
                key=key,
                name=name,
                entity_type=entity_type,
            )

        return key

    def link_document_to_entity(
        self,
        document_id: int,
        entity_name: str,
        entity_type: str,
    ):
        entity_key = self.upsert_entity(entity_name, entity_type)

        query = """
        MATCH (d:Document {id: $document_id})
        MATCH (e:Entity {key: $entity_key})
        MERGE (d)-[:MENTIONS]->(e)
        """

        with self.driver.session() as session:
            session.run(
                query,
                document_id=document_id,
                entity_key=entity_key,
            )

    def create_entity_relationship(
        self,
        from_name: str,
        from_type: str,
        relation: str,
        to_name: str,
        to_type: str,
    ):
        from_key = self.upsert_entity(from_name, from_type)
        to_key = self.upsert_entity(to_name, to_type)

        relation_type = self._sanitize_relation_type(relation)

        query = f"""
        MATCH (a:Entity {{key: $from_key}})
        MATCH (b:Entity {{key: $to_key}})
        MERGE (a)-[r:{relation_type}]->(b)
        SET r.label = $relation
        """

        with self.driver.session() as session:
            session.run(
                query,
                from_key=from_key,
                to_key=to_key,
                relation=relation,
            )

    def get_document_graph(self, document_id: int):
        query = """
        MATCH (d:Document {id: $document_id})-[:MENTIONS]->(e:Entity)
        OPTIONAL MATCH (e)-[r]->(related:Entity)
        RETURN d, e, r, related
        """

        with self.driver.session() as session:
            result = session.run(query, document_id=document_id)

            rows = []
            for record in result:
                rows.append(
                    {
                        "document": dict(record["d"]) if record["d"] else None,
                        "entity": dict(record["e"]) if record["e"] else None,
                        "relationship": record["r"].type if record["r"] else None,
                        "related": dict(record["related"]) if record["related"] else None,
                    }
                )

            return rows

    def _build_entity_key(self, name: str, entity_type: str) -> str:
        return f"{entity_type.lower()}:{name.strip().lower()}"

    def _sanitize_relation_type(self, relation: str) -> str:
        safe = "".join(
            char if char.isalnum() else "_"
            for char in relation.upper().strip()
        )
        return safe or "RELATED_TO"

    def search_related_entities(self, entity_names: list[str], limit: int = 20):
        if not entity_names:
            return []

        query = """
        MATCH (e:Entity)
        WHERE toLower(e.name) IN $entity_names
        OPTIONAL MATCH (e)-[r]-(related:Entity)
        RETURN e, r, related
        LIMIT $limit
        """

        normalized_names = [name.lower() for name in entity_names]

        with self.driver.session() as session:
            result = session.run(
                query,
                entity_names=normalized_names,
                limit=limit,
            )

            rows = []

            for record in result:
                rows.append(
                    {
                        "entity": dict(record["e"]) if record["e"] else None,
                        "relationship": record["r"].type if record["r"] else None,
                        "related": dict(record["related"]) if record["related"] else None,
                    }
                )

            return rows


neo4j_service = Neo4jService()