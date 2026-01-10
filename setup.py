#!/usr/bin/env python3
"""
Setup script for Financial Advisor - Retirement Planning Tool
"""

from setuptools import setup, find_packages
import os

# Read the README file
def read_readme():
    with open("README.md", "r", encoding="utf-8") as fh:
        return fh.read()

# Read requirements
def read_requirements():
    try:
        with open("requirements.txt", "r", encoding="utf-8") as fh:
            return [line.strip() for line in fh if line.strip() and not line.startswith("#")]
    except FileNotFoundError:
        # Fallback to core dependencies if requirements.txt not found during build
        return [
            "streamlit>=1.28.0",
            "pandas>=2.0.0",
            "reportlab>=4.0.0",
        ]

setup(
    name="financial-advisor",
    version="7.3.0",
    author="Your Name",
    author_email="your.email@example.com",
    description="A comprehensive Python-based financial planning tool for retirement projections",
    long_description=read_readme(),
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/financialadvisor",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: End Users/Desktop",
        "Intended Audience :: Financial and Insurance Industry",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Office/Business :: Financial :: Investment",
        "Topic :: Scientific/Engineering :: Mathematics",
    ],
    python_requires=">=3.8",
    install_requires=read_requirements(),
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "black>=22.0.0",
            "flake8>=5.0.0",
            "mypy>=1.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "financial-advisor=fin_advisor:main",
        ],
    },
    keywords="finance, retirement, planning, investment, calculator, streamlit",
    project_urls={
        "Bug Reports": "https://github.com/yourusername/financialadvisor/issues",
        "Source": "https://github.com/yourusername/financialadvisor",
        "Documentation": "https://github.com/yourusername/financialadvisor#readme",
    },
)
