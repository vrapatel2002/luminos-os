"""File operations tools (read/write) with path sandboxing."""

import logging
import os
import pathlib
from .base import Tool

logger = logging.getLogger("hive.tools.file_tools")


class FileReadTool(Tool):
    def get_name(self) -> str:
        return "file_read"

    def get_description(self) -> str:
        return "Read the contents of a file. Restricted to project directories only."

    async def execute(self, params: dict) -> dict:
        if not self.enabled:
            return {"success": False, "error": "FileRead tool is disabled"}

        file_path = params.get("file_path")
        project_root = params.get("project_root")

        if not file_path or not project_root:
            return {"success": False, "error": "Missing file_path or project_root"}

        # Security Check: Prevent path traversal
        try:
            root_path = pathlib.Path(project_root).resolve()
            target_path = (root_path / file_path).resolve()
            
            if not str(target_path).startswith(str(root_path)):
                return {"success": False, "error": "Access denied: Path is outside project root"}
            
            if not target_path.exists():
                return {"success": False, "error": f"File not found: {file_path}"}
                
            if target_path.stat().st_size > 1_000_000: # 1MB limit
                 return {"success": False, "error": "File too large (>1MB)"}

            # Read file
            try:
                content = target_path.read_text(encoding='utf-8')
                return {"success": True, "result": content}
            except UnicodeDecodeError:
                 return {"success": False, "error": "Binary file detected, cannot read as text"}

        except Exception as e:
            logger.error(f"File read error: {e}")
            return {"success": False, "error": str(e)}


class FileWriteTool(Tool):
    def get_name(self) -> str:
        return "file_write"

    def get_description(self) -> str:
        return "Write content to a file. Restricted to project directories only."

    async def execute(self, params: dict) -> dict:
        if not self.enabled:
            return {"success": False, "error": "FileWrite tool is disabled"}

        file_path = params.get("file_path")
        content = params.get("content")
        project_root = params.get("project_root")

        if not file_path or content is None or not project_root:
             return {"success": False, "error": "Missing file_path, content, or project_root"}

        # Security Check: Prevent path traversal
        try:
            root_path = pathlib.Path(project_root).resolve()
            target_path = (root_path / file_path).resolve()
            
            if not str(target_path).startswith(str(root_path)):
                return {"success": False, "error": "Access denied: Path is outside project root"}

            # Create parent directories
            target_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write file
            target_path.write_text(content, encoding='utf-8')
            return {"success": True, "result": f"Successfully wrote to {file_path}"}

        except Exception as e:
            logger.error(f"File write error: {e}")
            return {"success": False, "error": str(e)}
