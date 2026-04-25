"""SQLite database operations for LLMS memory system."""

import aiosqlite
import json
import logging
from pathlib import Path
import datetime

logger = logging.getLogger("hive.memory.db")

class Database:
    def __init__(self, db_path: str, schema_path: str):
        self.db_path = Path(db_path)
        self.schema_path = Path(schema_path)
        self.connection = None

    async def initialize(self) -> None:
        try:
            # Create parent directories for db_path if they don't exist
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Connect to SQLite via aiosqlite.connect(str(self.db_path))
            self.connection = await aiosqlite.connect(str(self.db_path))
            # Set row_factory to aiosqlite.Row
            self.connection.row_factory = aiosqlite.Row
            
            # Execute: PRAGMA journal_mode=WAL
            await self.connection.execute("PRAGMA journal_mode=WAL")
            # Execute: PRAGMA foreign_keys=ON
            await self.connection.execute("PRAGMA foreign_keys=ON")
            
            # Read schema.sql file contents
            with open(self.schema_path, 'r', encoding='utf-8') as f:
                schema_script = f.read()
            
            # Execute schema via executescript
            await self.connection.executescript(schema_script)
            # Commit
            await self.connection.commit()
            
            # Log: "Database initialized at {db_path}"
            logger.info(f"Database initialized at {self.db_path}")

        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise

    async def close(self) -> None:
        try:
            # If self.connection is not None, close it
            if self.connection is not None:
                await self.connection.close()
                self.connection = None
        except Exception as e:
            logger.error(f"Failed to close database: {e}")
            raise

    async def get_profile(self) -> dict:
        try:
            # SELECT key, value FROM profile
            cursor = await self.connection.execute("SELECT key, value FROM profile")
            rows = await cursor.fetchall()
            # Return as {key: value} dict
            return {row['key']: row['value'] for row in rows}
        except Exception as e:
            logger.error(f"Failed to get profile: {e}")
            raise

    async def set_profile(self, key: str, value: str) -> None:
        try:
            # INSERT OR REPLACE INTO profile (key, value, updated_at) VALUES (?, ?, ?)
            updated_at = datetime.datetime.now().isoformat()
            await self.connection.execute(
                "INSERT OR REPLACE INTO profile (key, value, updated_at) VALUES (?, ?, ?)",
                (key, value, updated_at)
            )
            await self.connection.commit()
        except Exception as e:
            logger.error(f"Failed to set profile: {e}")
            raise

    async def create_project(self, name: str, root_path: str = None, description: str = None) -> int:
        try:
            # INSERT into projects table with name, root_path, description
            cursor = await self.connection.execute(
                "INSERT INTO projects (name, root_path, description) VALUES (?, ?, ?)",
                (name, root_path, description)
            )
            await self.connection.commit()
            # Return cursor.lastrowid
            return cursor.lastrowid
        except Exception as e:
            logger.error(f"Failed to create project: {e}")
            raise

    async def get_project(self, name: str) -> dict | None:
        try:
            # SELECT * FROM projects WHERE name = ?
            cursor = await self.connection.execute("SELECT * FROM projects WHERE name = ?", (name,))
            row = await cursor.fetchone()
            
            if row:
                # If found, UPDATE last_accessed to now, commit
                now = datetime.datetime.now().isoformat()
                await self.connection.execute(
                    "UPDATE projects SET last_accessed = ? WHERE id = ?",
                    (now, row['id'])
                )
                await self.connection.commit()
                # Return as dict or None
                return self._row_to_dict(row)
            return None
        except Exception as e:
            logger.error(f"Failed to get project: {e}")
            raise

    async def list_projects(self) -> list[dict]:
        try:
            # SELECT * FROM projects ORDER BY last_accessed DESC
            cursor = await self.connection.execute("SELECT * FROM projects ORDER BY last_accessed DESC")
            rows = await cursor.fetchall()
            # Return as list of dicts
            return [self._row_to_dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to list projects: {e}")
            raise

    async def store_document(self, project_id: int | None, source_path: str, doc_type: str, title: str, page_count: int = None) -> int:
        try:
            # INSERT into documents
            cursor = await self.connection.execute(
                "INSERT INTO documents (project_id, source_path, doc_type, title, page_count) VALUES (?, ?, ?, ?, ?)",
                (project_id, source_path, doc_type, title, page_count)
            )
            await self.connection.commit()
            # Return lastrowid
            return cursor.lastrowid
        except Exception as e:
            logger.error(f"Failed to store document: {e}")
            raise

    async def store_chunk(self, document_id: int, chunk_index: int, content: str, content_type: str, page_number: int = None, embedding: bytes = None, token_count: int = None) -> int:
        try:
            # INSERT into chunks
            cursor = await self.connection.execute(
                "INSERT INTO chunks (document_id, chunk_index, content, content_type, page_number, embedding, token_count) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (document_id, chunk_index, content, content_type, page_number, embedding, token_count)
            )
            await self.connection.commit()
            # Return lastrowid
            return cursor.lastrowid
        except Exception as e:
            logger.error(f"Failed to store chunk: {e}")
            raise

    async def store_memory(self, content: str, category: str, importance: float = 0.5, project_id: int = None, source_document_id: int = None, summary_type: str = None, tags: list[str] = None, embedding: bytes = None) -> int:
        try:
            # If tags is not None, convert to JSON string via json.dumps(tags)
            tags_json = json.dumps(tags) if tags is not None else None
            
            # INSERT into memories
            cursor = await self.connection.execute(
                """INSERT INTO memories (content, category, importance, project_id, source_document_id, summary_type, tags, embedding) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (content, category, importance, project_id, source_document_id, summary_type, tags_json, embedding)
            )
            await self.connection.commit()
            # Return lastrowid
            return cursor.lastrowid
        except Exception as e:
            logger.error(f"Failed to store memory: {e}")
            raise

    async def search_chunks_by_ids(self, chunk_ids: list[int]) -> list[dict]:
        if not chunk_ids:
            return []
        try:
            # Build query: SELECT * FROM chunks WHERE id IN ({placeholders})
            placeholders = ', '.join(['?'] * len(chunk_ids))
            query = f"SELECT * FROM chunks WHERE id IN ({placeholders})"
            
            # Use parameterized query with the list
            cursor = await self.connection.execute(query, chunk_ids)
            rows = await cursor.fetchall()
            
            # Return list of dicts
            return [self._row_to_dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to search chunks by ids: {e}")
            raise

    async def search_memories_by_ids(self, memory_ids: list[int]) -> list[dict]:
        if not memory_ids:
            return []
        try:
            # SELECT * FROM memories WHERE id IN ({placeholders})
            placeholders = ', '.join(['?'] * len(memory_ids))
            query = f"SELECT * FROM memories WHERE id IN ({placeholders})"
            
            cursor = await self.connection.execute(query, memory_ids)
            rows = await cursor.fetchall()
            
            results = []
            now = datetime.datetime.now().isoformat()
            
            for row in rows:
                row_dict = self._row_to_dict(row)
                
                # For each returned row, UPDATE: access_count = access_count + 1, last_accessed = now
                await self.connection.execute(
                    "UPDATE memories SET access_count = access_count + 1, last_accessed = ? WHERE id = ?",
                    (now, row['id'])
                )
                
                # Parse tags back from JSON string to list where not None
                if row_dict.get('tags'):
                    try:
                        row_dict['tags'] = json.loads(row_dict['tags'])
                    except json.JSONDecodeError:
                        row_dict['tags'] = None
                
                results.append(row_dict)
            
            # Commit updates
            await self.connection.commit()
            
            # Return list of dicts
            return results
        except Exception as e:
            logger.error(f"Failed to search memories by ids: {e}")
            raise

    async def get_all_embeddings(self, table: str = "chunks") -> list[tuple[int, bytes]]:
        try:
            # VALIDATE table is either "chunks" or "memories" — if not, raise ValueError
            if table not in ("chunks", "memories"):
                raise ValueError("Table must be 'chunks' or 'memories'")
            
            # SELECT id, embedding FROM {table} WHERE embedding IS NOT NULL
            cursor = await self.connection.execute(f"SELECT id, embedding FROM {table} WHERE embedding IS NOT NULL")
            rows = await cursor.fetchall()
            
            # Return list of (id, embedding_bytes) tuples
            return [(row['id'], row['embedding']) for row in rows]
        except Exception as e:
            logger.error(f"Failed to get all embeddings: {e}")
            raise

    async def get_instinct_memories(self, threshold: float = 0.9) -> list[dict]:
        try:
            # SELECT * FROM memories WHERE importance >= ?
            cursor = await self.connection.execute("SELECT * FROM memories WHERE importance >= ?", (threshold,))
            rows = await cursor.fetchall()
            
            results = []
            for row in rows:
                row_dict = self._row_to_dict(row)
                # Parse tags from JSON where not None
                if row_dict.get('tags'):
                    try:
                        row_dict['tags'] = json.loads(row_dict['tags'])
                    except json.JSONDecodeError:
                        row_dict['tags'] = None
                results.append(row_dict)
            
            # Return list of dicts
            return results
        except Exception as e:
            logger.error(f"Failed to get instinct memories: {e}")
            raise

    async def log_conversation(self, session_id: str, user_message: str, bot_response: str, model_used: str = None, route_decision: str = None, memory_used: list = None, tools_used: list = None, response_time: float = None, project_id: int = None) -> int:
        try:
            # If memory_used is not None, json.dumps(memory_used)
            memory_used_json = json.dumps(memory_used) if memory_used is not None else None
            # If tools_used is not None, json.dumps(tools_used)
            tools_used_json = json.dumps(tools_used) if tools_used is not None else None
            
            # INSERT into conversations with all fields
            cursor = await self.connection.execute(
                """INSERT INTO conversations (session_id, user_message, bot_response, model_used, route_decision, memory_used, tools_used, response_time, project_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (session_id, user_message, bot_response, model_used, route_decision, memory_used_json, tools_used_json, response_time, project_id)
            )
            await self.connection.commit()
            # Return lastrowid
            return cursor.lastrowid
        except Exception as e:
            logger.error(f"Failed to log conversation: {e}")
            raise

    async def log_query(self, query: str, routed_to: str, reasoning: str = None, project_id: int = None) -> None:
        try:
            # INSERT into query_log
            await self.connection.execute(
                "INSERT INTO query_log (query, routed_to, reasoning, project_id) VALUES (?, ?, ?, ?)",
                (query, routed_to, reasoning, project_id)
            )
            # Commit
            await self.connection.commit()
        except Exception as e:
            logger.error(f"Failed to log query: {e}")
            raise

    async def add_feedback(self, conversation_id: int, feedback: str) -> None:
        try:
            # UPDATE conversations SET feedback = ? WHERE id = ?
            await self.connection.execute(
                "UPDATE conversations SET feedback = ? WHERE id = ?",
                (feedback, conversation_id)
            )
            # Commit
            await self.connection.commit()
        except Exception as e:
            logger.error(f"Failed to add feedback: {e}")
            raise

    async def export_conversations(self, limit: int = None, feedback_filter: str = None) -> list[dict]:
        try:
            # Start with: SELECT * FROM conversations
            query = "SELECT * FROM conversations"
            params = []
            
            # If feedback_filter is not None, add WHERE feedback = ?
            if feedback_filter is not None:
                query += " WHERE feedback = ?"
                params.append(feedback_filter)
            
            # Add ORDER BY timestamp DESC
            query += " ORDER BY timestamp DESC"
            
            # If limit is not None, add LIMIT ?
            if limit is not None:
                query += " LIMIT ?"
                params.append(limit)
                
            cursor = await self.connection.execute(query, params)
            rows = await cursor.fetchall()
            
            results = []
            for row in rows:
                row_dict = self._row_to_dict(row)
                
                # Parse memory_used and tools_used from JSON where not None
                if row_dict.get('memory_used'):
                    try:
                        row_dict['memory_used'] = json.loads(row_dict['memory_used'])
                    except json.JSONDecodeError:
                        row_dict['memory_used'] = None
                
                if row_dict.get('tools_used'):
                    try:
                        row_dict['tools_used'] = json.loads(row_dict['tools_used'])
                    except json.JSONDecodeError:
                        row_dict['tools_used'] = None
                        
                results.append(row_dict)
                
            # Return list of dicts
            return results
        except Exception as e:
            logger.error(f"Failed to export conversations: {e}")
            raise

    def _row_to_dict(self, row) -> dict:
        # Convert an aiosqlite.Row to a regular dict
        return dict(row)
