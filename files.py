"""
JARVIS OMEGA — Files (root-level agent)
File operations and project scanning.
"""
import os
from typing import Dict, List, Optional
from pathlib import Path
from datetime import datetime


class FilesAgent:
    """
    File management agent with project scanning.
    """

    def __init__(self):
        pass

    def list_directory(self, path: str = ".") -> Dict:
        """List files in directory."""
        try:
            path = os.path.abspath(path)
            if not os.path.exists(path):
                return {"error": f"Path not found: {path}"}
            if not os.path.isdir(path):
                return {"error": f"Not a directory: {path}"}

            files = []
            for item in os.listdir(path):
                item_path = os.path.join(path, item)
                is_dir = os.path.isdir(item_path)
                try:
                    size = os.path.getsize(item_path)
                except OSError:
                    size = 0
                files.append({
                    "name": item,
                    "path": item_path,
                    "is_dir": is_dir,
                    "size": size,
                })
            return {"path": path, "files": files, "count": len(files)}
        except Exception as e:
            return {"error": str(e)}

    def read_file(self, filepath: str) -> Dict:
        """Read file contents."""
        try:
            filepath = os.path.abspath(filepath)
            if not os.path.exists(filepath):
                return {"error": f"File not found: {filepath}"}
            if not os.path.isfile(filepath):
                return {"error": f"Not a file: {filepath}"}

            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            return {"path": filepath, "content": content, "size": len(content)}
        except Exception as e:
            return {"error": str(e)}

    def write_file(self, filename: str, content: str, mode: str = "w") -> Dict:
        """Write to file."""
        try:
            filename = os.path.abspath(filename)
            os.makedirs(os.path.dirname(filename), exist_ok=True)
            with open(filename, mode, encoding="utf-8") as f:
                f.write(content)
            return {"path": filename, "size": len(content), "mode": mode}
        except Exception as e:
            return {"error": str(e)}

    def scan_project(self, folder_path: str) -> Dict:
        """
        Lightweight project scanner that returns structure info.
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
            "fastapi": ["main.py", "app.py"],
            "django": ["manage.py"],
            "flask": ["wsgi.py"],
            "nodejs": ["package.json", "index.js"],
            "react": ["src/index.jsx", "src/index.tsx"],
            "python": ["requirements.txt", "setup.py", "pyproject.toml"],
            "html": ["index.html"],
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
            "folder": path,
            "project_type": project_type,
            "total_files": total_files,
            "structure": structure,
        }
