"""
JARVIS OMEGA — Files (root-level shim)
Re-exports FilesAgent from agents.files, with a scan_project method
that delegates to the project scanner for compatibility with orchestrator.py.
"""
import os
from typing import Dict, List, Optional
from pathlib import Path
from datetime import datetime

from agents.files import FilesAgent as _FilesAgent


class FilesAgent(_FilesAgent):
    """
    Extends the base FilesAgent with a scan_project() method
    so the Orchestrator can call jarvis.files.scan_project(path).
    """

    def scan_project(self, folder_path: str) -> Dict:
        """
        Lightweight project scanner that returns structure info.
        (Full AI-powered scanning is in ProjectScannerAgent.)
        """
        path = os.path.abspath(folder_path)
        if not os.path.exists(path):
            return {"error": f"Path not found: {path}"}
        if not os.path.isdir(path):
            return {"error": f"Not a directory: {path}"}

        SKIP_DIRS = {"__pycache__", "node_modules", ".git", "venv", ".venv",
                     "env", "dist", "build", ".next", "target", "vendor"}
        BINARY_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".pdf", ".exe",
                       ".dll", ".so", ".zip", ".gz", ".tar", ".db", ".sqlite",
                       ".pyc", ".class", ".o", ".obj"}

        structure = []
        total_files = 0
        project_type = "unknown"

        # Detect project type by sentinel files
        type_markers = {
            "fastapi":  ["main.py", "app.py"],
            "django":   ["manage.py"],
            "flask":    ["wsgi.py"],
            "nodejs":   ["package.json", "index.js"],
            "react":    ["src/index.jsx", "src/index.tsx"],
            "python":   ["requirements.txt", "setup.py", "pyproject.toml"],
            "html":     ["index.html"],
        }
        for ptype, markers in type_markers.items():
            if any(os.path.exists(os.path.join(path, m)) for m in markers):
                project_type = ptype
                break

        for root, dirs, files in os.walk(path):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
            rel_root = os.path.relpath(root, path)
            for fname in files:
                ext = Path(fname).suffix.lower()
                if ext in BINARY_EXTS:
                    continue
                rel = os.path.join(rel_root, fname) if rel_root != "." else fname
                try:
                    size = os.path.getsize(os.path.join(root, fname))
                except OSError:
                    size = 0
                structure.append({"path": rel, "name": fname, "ext": ext, "size": size})
                total_files += 1
                if total_files >= 150:
                    break
            if total_files >= 150:
                break

        return {
            "folder":       path,
            "project_type": project_type,
            "total_files":  total_files,
            "structure":    structure,
        }
