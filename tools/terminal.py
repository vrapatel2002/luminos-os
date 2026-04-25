"""Terminal command execution tool with strict safety controls."""

import logging
import shlex
import subprocess
import os
import pathlib
from typing import Tuple, Dict, Any
from .base import Tool

logger = logging.getLogger("hive.tools.terminal")

class TerminalTool(Tool):
    """Executes whitelisted terminal commands with user confirmation."""
    
    name = "terminal"
    description = "Run terminal commands (pip install, dir, mkdir, git, etc.)"

    # A. WHITELISTED COMMAND PREFIXES
    _WHITELIST = [
        "pip install", "pip uninstall", "pip list", "pip freeze", "pip show",
        "conda list", "conda info",
        "mkdir", "dir", "ls", "cat", "type", "echo",
        "cd",
        "git status", "git log", "git diff", "git add", "git commit",
        "python",
        "ollama list", "ollama ps", "ollama pull",
        "aider --version",
        "cls", "clear",
        "tesseract --version",
    ]

    # B. BLACKLISTED PATTERNS
    _BLACKLIST = [
        "rm -rf", "del /s", "del /q", "del *", "rmdir /s",
        "format", "shutdown", "restart", "taskkill",
        "reg add", "reg delete", "regedit",
        "netsh", "net user", "net stop",
        "powershell -encodedcommand",
        ".exe",  # Generic exe block
        "|", ">", ">>",  # Pipe/redirect
        "sudo", "runas", "admin",
    ]
    
    _EXE_EXCEPTIONS = ["python.exe", "pip.exe", "git.exe", "ollama.exe", "tesseract.exe"]

    # C. ALLOWED DIRECTORIES
    _ALLOWED_ROOT = pathlib.Path("C:/Users/vrati/VSCODE").resolve()

    def __init__(self, config: dict):
        super().__init__(config)
        self.timeout = config.get("timeout", 30)
        self.require_confirmation = config.get("require_confirmation", True)
        self.allowed_dirs = [pathlib.Path(d).resolve() for d in config.get("allowed_dirs", [])]
        if not self.allowed_dirs:
            self.allowed_dirs = [self._ALLOWED_ROOT]

    def get_name(self) -> str:
        return self.name

    def get_description(self) -> str:
        return self.description

    def is_whitelisted(self, command: str) -> bool:
        cmd_lower = command.lower().strip()
        return any(cmd_lower.startswith(prefix) for prefix in self._WHITELIST)

    def is_blacklisted(self, command: str) -> Tuple[bool, str]:
        cmd_lower = command.lower()
        
        # Check explicit blacklist patterns
        for pattern in self._BLACKLIST:
            if pattern == ".exe":
                # Special handling for .exe to allow exceptions
                if ".exe" in cmd_lower:
                    # Check if allowed exception
                    is_exception = any(exc in cmd_lower for exc in self._EXE_EXCEPTIONS)
                    if not is_exception:
                        return True, f"Blocked pattern: .exe (only specific tools allowed)"
            elif pattern in cmd_lower:
                return True, f"Blocked pattern: {pattern}"

        return False, ""

    def is_path_allowed(self, path: str) -> bool:
        try:
            target = pathlib.Path(path).resolve()
            return any(str(target).startswith(str(allowed)) for allowed in self.allowed_dirs)
        except Exception:
            return False

    def get_risk_level(self, command: str) -> str:
        cmd_lower = command.lower()
        if any(x in cmd_lower for x in ["pip uninstall", "del", "rmdir"]):
            return "high"
        if any(x in cmd_lower for x in ["pip install", "mkdir", "git commit"]):
            return "medium"
        return "low"

    def format_confirmation(self, command: str, risk: str) -> str:
        return (
            f"CONFIRMATION REQUEST\n"
            f"Command: {command}\n"
            f"Risk: {risk.upper()}\n"
            f"Explanation: This command will run on your system. "
            f"Please review carefully.\n"
            f"To execute, reply with: CONFIRM: yes"
        )

    async def execute(self, params: dict) -> dict:
        command = params.get("command", "")
        cwd = params.get("cwd", os.getcwd())
        confirmed = params.get("confirmed", False)
        
        # 1. Basic Validation
        if not command:
            return {"success": False, "error": "No command provided"}
        
        # 2. Safety Checks
        if not self.is_whitelisted(command):
            return {"success": False, "error": f"Command not allowed: {command}"}

        blocked, reason = self.is_blacklisted(command)
        if blocked:
            logger.warning(f"Blocked blacklist command: {command} ({reason})")
            return {"success": False, "error": reason}

        if not self.is_path_allowed(cwd):
             return {"success": False, "error": f"Working directory not allowed: {cwd}"}

        # 3. Confirmation Flow
        if self.require_confirmation and not confirmed:
            risk = self.get_risk_level(command)
            logger.info(f"Requesting confirmation for: {command} ({risk})")
            return {
                "success": False,
                "status": "confirmation_required",
                "message": self.format_confirmation(command, risk),
                "command": command,
                "risk": risk
            }

        # 4. Execution
        try:
            logger.info(f"Executing command: {command} in {cwd}")
            proc = subprocess.run(
                command,
                cwd=cwd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=self.timeout
            )
            
            result = {
                "success": proc.returncode == 0,
                "stdout": proc.stdout,
                "stderr": proc.stderr,
                "returncode": proc.returncode
            }
            logger.info(f"Execution finished. RC={proc.returncode}")
            return result

        except subprocess.TimeoutExpired:
            logger.error(f"Command timed out: {command}")
            return {"success": False, "error": "Command timed out"}
        except Exception as e:
            logger.error(f"Execution error: {e}")
            return {"success": False, "error": str(e)}
