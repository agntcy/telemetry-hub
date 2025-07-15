# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

#!/bin/bash

# Test Runner Script for Metrics Computation Engine
# This script runs the test suite

set -e  # Exit on any error

echo "🧪 Running Metrics Computation Engine tests..."

# Check if we're in a virtual environment or have uv
if ! command -v pytest &> /dev/null && ! command -v uv &> /dev/null; then
    echo "❌ Neither pytest nor uv found. Please install dependencies first:"
    echo "   ./install.sh or ./dev-setup.sh"
    exit 1
fi

# Load environment variables if .env file exists
if [ -f .env ]; then
    echo "📋 Loading environment variables from .env file..."
    export $(cat .env | grep -v '^#' | xargs)
fi

# Run tests with pytest
echo "🔬 Running test suite..."

if command -v pytest &> /dev/null; then
    # Direct pytest execution
    pytest src/metrics_computation_engine/tests/ -v
elif command -v uv &> /dev/null; then
    # Run via uv
    uv run --env-file .env pytest src/metrics_computation_engine/tests/ -v
else
    echo "❌ Cannot run tests. Please install pytest or uv."
    exit 1
fi

echo ""
echo "✅ Tests completed!"
echo ""
