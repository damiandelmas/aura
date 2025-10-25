from setuptools import setup, find_packages

setup(
    name="aura-qdrant",
    version="3.0.0",
    description="AURA Qdrant - Vector database lifecycle manager",
    author="AURA Project",
    packages=find_packages(where='src'),
    package_dir={'': 'src'},
    python_requires=">=3.8",
    install_requires=["qdrant-client>=1.7.0", "click>=8.0.0"],
)
