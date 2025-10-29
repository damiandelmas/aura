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

    def register_project(self, project_root: Path) -> dict:
        """Register a project and return collection names"""
        project_key = str(project_root.resolve())
        hash_suffix = hashlib.md5(project_key.encode()).hexdigest()[:8]

        collections = {
            "context": f"imem_{hash_suffix}_context",
            "conversation": f"imem_{hash_suffix}_conversation"
        }

        self.data["projects"][project_key] = {
            "collections": collections,
            "indexed_at": datetime.now().isoformat(),
            "doc_counts": {
                "context": 0,
                "conversation": 0
            }
        }
        self._save()
        return collections

    def is_registered(self, project_root: Path) -> bool:
        """Check if project is registered"""
        return str(project_root.resolve()) in self.data["projects"]

    def get_project_info(self, project_root: Path) -> dict:
        """Get project information"""
        return self.data["projects"].get(str(project_root.resolve()), {})

    def get_collection_by_type(self, project_root: Path, collection_type: str) -> str:
        """Get collection name for a specific type (context or conversation)"""
        info = self.get_project_info(project_root)
        if not info:
            raise ValueError(f"Project not registered: {project_root}")

        collections = info.get('collections', {})

        # Backward compatibility: if old schema, return single collection for context
        if not collections and 'collection' in info:
            if collection_type == 'context':
                return info['collection']
            else:
                raise ValueError(f"Old registry format - no {collection_type} collection")

        if collection_type not in collections:
            raise ValueError(f"Unknown collection type: {collection_type}")

        return collections[collection_type]

    def update_doc_count(self, project_root: Path, collection_type: str, count: int):
        """Update document count for a specific collection type"""
        project_key = str(project_root.resolve())
        if project_key in self.data["projects"]:
            # Backward compatibility: handle old schema
            if "doc_counts" not in self.data["projects"][project_key]:
                self.data["projects"][project_key]["doc_counts"] = {
                    "context": 0,
                    "conversation": 0
                }

            self.data["projects"][project_key]["doc_counts"][collection_type] = count
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
