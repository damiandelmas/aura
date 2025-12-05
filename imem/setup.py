from setuptools import setup, find_packages

setup(
    name="aura-imem",
    version="4.0.0",
    description="AURA IMEM - Knowledge compiler for AI agent memories",
    author="AURA Project",
    packages=find_packages(where='src'),
    package_dir={'': 'src'},
    python_requires=">=3.8",
    install_requires=[
        "sentence-transformers>=2.2.0",
        "click>=8.0.0",
        "pyyaml>=6.0",
    ],
    extras_require={
        # Tier 3: Vector features (EPIC 4)
        "vectors": [
            "sqlite-vec>=0.1.0",
        ],
        # Legacy dependencies (kept for backward compatibility)
        "legacy": [
            "qdrant-client>=1.7.0",
            "llama-index-core>=0.11.0",
        ],
    },
    entry_points={
        "console_scripts": ["imem=imem.cli_new:imem"]
    },
)
