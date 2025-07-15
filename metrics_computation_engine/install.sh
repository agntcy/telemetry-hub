# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

#!/bin/bash

# Metrics Computation Engine Installation Script
# This script installs the package using uv

set -e  # Exit on any error

echo "🚀 Installing Metrics Computation Engine..."

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "❌ uv is not installed. Please install uv first:"
    echo "   curl -LsSf https://astral.sh/uv/install.sh | sh"
    echo "   or"
    echo "   pip install uv"
    exit 1
fi

echo "✅ Found uv: $(uv --version)"

# Install the package in development mode
echo "📦 Installing package and dependencies..."
uv pip install -e .

echo "🔧 Installing development dependencies..."
uv pip install -e ".[dev]"

echo "📋 Creating .env file from template..."
if [ ! -f .env ]; then
    cp .env.example .env
    echo "✅ Created .env file. Please edit it with your API keys."
else
    echo "⚠️  .env file already exists. Skipping creation."
fi

echo ""
echo "✅ Installation completed successfully!"
echo ""
echo "Next steps:"
echo "1. Edit .env file with your API keys"
echo "2. Run the server: mce-server"
echo "3. Or use the CLI: mce-cli --help"
echo ""
echo "For testing:"
echo "  pytest src/metrics_computation_engine/tests/"
echo ""
