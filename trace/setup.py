from setuptools import setup, find_packages

setup(
    name="aura-trace",
    version="3.0.0",
    description="AURA TRACE - Conversation archaeology (parse Claude Code JSONL)",
    author="AURA Project",
    packages=find_packages(where='src'),
    package_dir={'': 'src'},
    python_requires=">=3.8",
    install_requires=["click>=8.0.0"],
    entry_points={
        "console_scripts": ["trace=aura_trace.cli:trace"]
    },
)
