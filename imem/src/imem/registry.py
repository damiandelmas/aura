#!/usr/bin/env python3
"""
SimpleRegistry - Simplified project registry for standalone imem
"""

import json
import hashlib
from pathlib import Path
from datetime import datetime
from .config import config


class SimpleRegistry:
    """Simplified project registry for standalone imem"""

    def __init__(self):
        self.registry_file = config.context_dir / "imem_registry.json"
        self.registry_file.parent.mkdir(exist_ok=True)
        self._load()

    def _load(self):
        if self.registry_file.exists():
            with open(self.registry_file) as f:
                self.data = json.load(f)
        else:
            self.data = {"projects": {}}

    def _save(self):
        with open(self.registry_file, 'w') as f:
            json.dump(self.data, f, indent=2)

    def get_project_root(self) -> Path:
        """Get project root (current directory)"""
        return Path.cwd()

    def register_project(self, project_root: Path) -> str:
        """Register a project and return collection name"""
        project_key = str(project_root.resolve())
        collection_name = f"imem_{hashlib.md5(project_key.encode()).hexdigest()[:8]}"

        self.data["projects"][project_key] = {
            "collection": collection_name,
            "indexed_at": datetime.now().isoformat(),
            "doc_count": 0
        }
        self._save()
        return collection_name

    def is_registered(self, project_root: Path) -> bool:
        """Check if project is registered"""
        return str(project_root.resolve()) in self.data["projects"]

    def get_project_info(self, project_root: Path) -> dict:
        """Get project information"""
        return self.data["projects"].get(str(project_root.resolve()), {})

    def update_doc_count(self, project_root: Path, count: int):
        """Update document count for project"""
        project_key = str(project_root.resolve())
        if project_key in self.data["projects"]:
            self.data["projects"][project_key]["doc_count"] = count
            self.data["projects"][project_key]["indexed_at"] = datetime.now().isoformat()
            self._save()

    def list_projects(self) -> dict:
        """List all registered projects"""
        return self.data["projects"]

    def get_relative_path(self, file_path: Path, project_root: Path) -> str:
        """Get relative path from project root"""
        try:
            return str(file_path.relative_to(project_root))
        except ValueError:
            return str(file_path)
