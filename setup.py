"""
Setup configuration for AI Testing Agent
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read README for long description
readme_file = Path(__file__).parent / "README.md"
long_description = readme_file.read_text(encoding="utf-8") if readme_file.exists() else ""

setup(
    name="ai-testing-agent",
    version="1.0.0",
    author="Your Name",
    author_email="your.email@example.com",
    description="Autonomous AI agent for test automation using pytest",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/ai-testing-agent",
    py_modules=["ai_testing_agent", "cli"],
    python_requires=">=3.8",
    install_requires=[
        "pytest>=7.4.0",
        "anthropic>=0.18.0",
        "PyPDF2>=3.0.0",
        "python-docx>=1.1.0",
    ],
    extras_require={
        "dev": [
            "black>=23.0.0",
            "flake8>=6.0.0",
            "mypy>=1.0.0",
            "pytest-cov>=4.1.0",
        ],
        "reporting": [
            "pytest-html>=4.1.0",
            "allure-pytest>=2.13.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "ai-test=cli:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Testing",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    keywords="testing automation ai pytest agent",
    project_urls={
        "Bug Reports": "https://github.com/yourusername/ai-testing-agent/issues",
        "Source": "https://github.com/yourusername/ai-testing-agent",
        "Documentation": "https://ai-testing-agent.readthedocs.io",
    },
)
