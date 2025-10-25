from setuptools import setup, find_packages

setup(
    name="aura",
    version="3.0.0",
    description="AURA - Institutional Memory Ecosystem (Aggregate Installer)",
    author="AURA Project",
    python_requires=">=3.8",
    packages=find_packages(include=['aura_cli', 'aura_cli.*']),
    install_requires=[
        "click>=8.0.0",
    ],
    extras_require={
        "all": ["aura-imem", "aura-trace", "aura-qdrant"],
        "search": ["aura-imem"],
        "conversation": ["aura-trace"],
        "db": ["aura-qdrant"],
    },
    entry_points={
        "console_scripts": [
            "aura=aura_cli.cli:aura",
        ],
    },
)
