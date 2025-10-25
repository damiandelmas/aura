# AURA Qdrant - Vector Database Lifecycle Manager

**Qdrant** manages the lifecycle of the Qdrant vector database service used by IMEM for document search.

## Features

- 🐳 **Docker Management**: Automated Docker Compose setup
- 🚀 **Service Lifecycle**: Start, stop, and monitor Qdrant
- 📦 **Persistent Storage**: Data persists across restarts
- 🔍 **Health Checks**: Verify service availability

## Installation

```bash
# Install from source
cd qdrant/
pip install -e .

# Verify installation
python -c "from qdrant_manager import QdrantService; print('OK')"
```

## Dependencies

- `qdrant-client>=1.7.0` - Qdrant Python client
- `click>=8.0.0` - CLI framework
- **Docker** - Required for running Qdrant container

## Usage (Library)

```python
from qdrant_manager import QdrantService

# Create service manager
service = QdrantService()

# Start Qdrant
service.start()

# Check if running
if service.is_running():
    print("Qdrant is running!")

# Get status
status = service.status()
print(f"Collections: {status['collections']}")
print(f"Port: {status['port']}")

# Ensure running (start if not)
service.ensure_running()

# Stop service
service.stop()
```

## Configuration

### Default Settings

- **Port**: 6334 (external) → 6333 (container internal)
- **Host**: localhost
- **Storage**: `~/.context/qdrant_storage/`
- **Docker Compose**: `~/.context/docker-compose.yml`

### Container Settings

- **Image**: `qdrant/qdrant:latest`
- **Container Name**: `imem_qdrant`
- **Restart Policy**: `unless-stopped`
- **Log Level**: INFO

## How It Works

1. **Docker Compose**: Generates configuration in `~/.context/docker-compose.yml`
2. **Container**: Runs Qdrant in Docker with persistent volume
3. **Health Check**: Validates service by listing collections
4. **Client**: Uses `qdrant-client` for all interactions

## Storage

All Qdrant data is stored in:
```
~/.context/qdrant_storage/
├── collections/    # Vector collections
├── wal/           # Write-ahead log
└── snapshots/     # Backups
```

## API Reference

### QdrantService

```python
class QdrantService:
    def __init__(self):
        """Initialize service manager"""

    def start(self) -> bool:
        """Start Qdrant service. Returns True if successful."""

    def stop(self) -> bool:
        """Stop Qdrant service. Returns True if successful."""

    def is_running(self) -> bool:
        """Check if Qdrant is accessible."""

    def status(self) -> Dict[str, Any]:
        """Get detailed service status."""

    def ensure_running(self) -> bool:
        """Ensure service is running, start if needed."""

    def create_docker_compose(self):
        """Generate docker-compose.yml configuration."""
```

## Troubleshooting

**Docker not found**:
```bash
# Install Docker
# Linux: https://docs.docker.com/engine/install/
# Mac: https://docs.docker.com/desktop/install/mac-install/

# Verify installation
docker --version
docker-compose --version
```

**Port 6334 already in use**:
```bash
# Find process using port
lsof -i :6334

# Kill process or change port in __init__(self)
```

**Permission denied**:
```bash
# Add user to docker group (Linux)
sudo usermod -aG docker $USER
newgrp docker
```

**Data persistence issues**:
```bash
# Check storage directory
ls -la ~/.context/qdrant_storage/

# Reset storage (WARNING: deletes all data)
rm -rf ~/.context/qdrant_storage/
imem service start
```

## Development

```bash
# Install in editable mode
pip install -e .

# Run tests
pytest tests/
```

## Integration with IMEM

IMEM uses QdrantService automatically:

```python
# In IMEM CLI
service = QdrantService()
if not service.ensure_running():
    print("Failed to start Qdrant")
    sys.exit(1)
```

## Related Microservices

- **IMEM**: Vector search (uses Qdrant) (`../imem/`)
- **TRACE**: Conversation archaeology (`../trace/`)

## Docker-Free Alternative

For environments without Docker, you can run Qdrant natively:

```bash
# Download Qdrant binary
wget https://github.com/qdrant/qdrant/releases/latest/download/qdrant

# Make executable
chmod +x qdrant

# Run
./qdrant --storage-path ~/.context/qdrant_storage/ --port 6334
```

Note: You'll need to modify `QdrantService` to skip Docker commands.
