# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

#!/bin/bash

# Development Setup Script for Metrics Computation Engine
# This script sets up the development environment

set -e  # Exit on any error

echo "🛠️  Setting up development environment..."

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "❌ uv is not installed. Please install uv first:"
    echo "   curl -LsSf https://astral.sh/uv/install.sh | sh"
    echo "   or"
    echo "   pip install uv"
    exit 1
fi

echo "✅ Found uv: $(uv --version)"

# Install the package in development mode with all dependencies
echo "📦 Installing package in development mode..."
uv pip install -e ".[dev,test]"

echo "📋 Creating .env file from template..."
if [ ! -f .env ]; then
    cp .env.example .env
    echo "✅ Created .env file. Please edit it with your API keys."
else
    echo "⚠️  .env file already exists. Skipping creation."
fi

# Install pre-commit hooks if available
if [ -f .pre-commit-config.yaml ]; then
    echo "🪝 Installing pre-commit hooks..."
    uv pip install pre-commit
    pre-commit install
fi

echo ""
echo "✅ Development setup completed successfully!"
echo ""
echo "Development commands:"
echo "  mce-server          - Start the development server"
echo "  mce-cli --help      - Show CLI help"
echo "  pytest              - Run tests"
echo "  isort .             - Sort imports"
echo ""
echo "Don't forget to:"
echo "1. Edit .env file with your API keys"
echo "2. Review and configure any additional settings"
echo ""
