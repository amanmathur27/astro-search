from setuptools import setup, find_packages

setup(
    name="astro-search",
    version="2.1.0",
    description="Domain-specific astronomy search engine (free sources only)",
    packages=find_packages(),
    install_requires=[
        "feedparser>=6.0",
        "requests>=2.28",
        "python-dateutil>=2.8",
    ],
    extras_require={
        "local": ["ephem>=4.1", "skyfield>=1.45"],
        "semantic": ["sentence-transformers>=2.0"],
        "test": ["pytest>=7.0"],
    },
    python_requires=">=3.9",
)
