#!/usr/bin/env python3
"""
Qdrant Service Manager - Manages global Qdrant instance
"""

import os
import json
import subprocess
import time
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

from .config import config

logger = logging.getLogger(__name__)

class QdrantService:
    """Manages the global Qdrant instance"""

    def __init__(self):
        """Initialize the Qdrant service manager.

        Sets up the service configuration including storage paths, Docker Compose
        file location, and connection parameters. Creates necessary directories
        from the global configuration.

        Args:
            None

        Returns:
            None

        Attributes:
            home_dir: Path to context directory for IMEM data (from config)
            docker_compose_path: Path to the Docker Compose configuration file
            storage_path: Path to persistent Qdrant storage directory
            port: Port number for Qdrant service (from config)
            host: Hostname for Qdrant connection (from config)

        Notes:
            - Creates context directory if it doesn't exist
            - Creates qdrant_storage subdirectory for persistent vector data
            - All paths and ports are configured from the global config module
        """
        self.home_dir = config.context_dir
        self.home_dir.mkdir(exist_ok=True)

        self.docker_compose_path = self.home_dir / "docker-compose.yml"
        self.storage_path = self.home_dir / "qdrant_storage"
        self.storage_path.mkdir(exist_ok=True)

        self.port = config.qdrant_port
        self.host = config.qdrant_host
        
    def create_docker_compose(self):
        """Create Docker Compose configuration for Qdrant.

        Generates a docker-compose.yml file with the Qdrant service configuration
        including port mapping, volume mounts, and environment settings. The
        configuration uses the latest Qdrant image and sets up persistent storage.

        Args:
            None

        Returns:
            None. Writes docker-compose.yml to self.docker_compose_path.

        Notes:
            - Uses qdrant/qdrant:latest Docker image
            - Maps container port 6333 to configured host port
            - Mounts storage_path to /qdrant/storage for persistence
            - Sets QDRANT__LOG_LEVEL to INFO
            - Configures restart policy to unless-stopped
            - Container named 'imem_qdrant'
        """
        compose_content = f"""version: '3.8'

services:
  qdrant:
    image: qdrant/qdrant:latest
    container_name: imem_qdrant
    ports:
      - "{self.port}:6333"
    volumes:
      - {self.storage_path}:/qdrant/storage
    environment:
      - QDRANT__LOG_LEVEL=INFO
    restart: unless-stopped
"""
        with open(self.docker_compose_path, 'w') as f:
            f.write(compose_content)
    
    def start(self) -> bool:
        """Start the Qdrant service"""
        if self.is_running():
            print(f"✅ Qdrant already running on port {self.port}")
            return True
        
        # Create docker-compose if it doesn't exist
        if not self.docker_compose_path.exists():
            self.create_docker_compose()
        
        print(f"🚀 Starting Qdrant on port {self.port}...")
        try:
            subprocess.run(
                ["docker-compose", "-f", str(self.docker_compose_path), "up", "-d"],
                check=True,
                capture_output=True,
                text=True
            )
            
            # Wait for service to be ready
            for i in range(config.service_start_retries):
                if self.is_running():
                    print(f"✅ Qdrant started successfully on port {self.port}")
                    return True
                time.sleep(config.service_start_delay)
            
            print("⚠️ Qdrant started but not responding")
            return False
            
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to start Qdrant: {e}")
            return False
    
    def stop(self) -> bool:
        """Stop the Qdrant service"""
        if not self.is_running():
            print("ℹ️ Qdrant is not running")
            return True
        
        print("🛑 Stopping Qdrant...")
        try:
            subprocess.run(
                ["docker-compose", "-f", str(self.docker_compose_path), "down"],
                check=True,
                capture_output=True,
                text=True
            )
            print("✅ Qdrant stopped")
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to stop Qdrant: {e}")
            return False
    
    def is_running(self) -> bool:
        """Check if Qdrant is running and accessible"""
        try:
            client = QdrantClient(host=self.host, port=self.port, timeout=config.qdrant_timeout)
            # Try to get collections - if this works, Qdrant is running
            client.get_collections()
            return True
        except KeyboardInterrupt:
            raise  # Allow user to cancel
        except (ConnectionError, TimeoutError) as e:
            logger.debug(f"Qdrant not accessible: {e}")
            return False
        except Exception as e:
            logger.debug(f"Error checking Qdrant status: {e}")
            return False
    
    def status(self) -> Dict[str, Any]:
        """Get service status"""
        is_running = self.is_running()
        
        status = {
            "running": is_running,
            "port": self.port,
            "host": self.host,
            "storage": str(self.storage_path)
        }
        
        if is_running:
            try:
                client = QdrantClient(host=self.host, port=self.port)
                collections = client.get_collections()
                status["collections"] = len(collections.collections)
                status["collection_names"] = [c.name for c in collections.collections]
            except KeyboardInterrupt:
                raise  # Allow user to cancel
            except (ConnectionError, TimeoutError) as e:
                logger.debug(f"Failed to get collection info: {e}")
            except Exception as e:
                logger.warning(f"Unexpected error getting collections: {e}")
        
        return status
    
    def ensure_running(self) -> bool:
        """Ensure Qdrant is running, start if not"""
        if self.is_running():
            return True
        return self.start()