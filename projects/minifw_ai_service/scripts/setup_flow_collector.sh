#!/bin/bash
# Quick Setup Script for MiniFW-AI Flow Collector Testing
# Run this from your project root directory

set -e

echo "=========================================="
echo "MiniFW-AI Flow Collector - Quick Setup"
echo "=========================================="
echo ""

# Get current directory
PROJECT_DIR=$(pwd)

echo "[1/4] Verifying project structure..."
if [ ! -d "app/minifw_ai" ]; then
    echo "ERROR: app/minifw_ai directory not found!"
    echo "Please run this script from the project root directory:"
    echo "  cd /path/to/minifw-ritapi"
    echo "  bash scripts/setup_flow_collector.sh"
    exit 1
fi
echo "✓ Project structure OK"

echo ""
echo "[2/4] Checking required files..."

# Check collector_flow.py
if [ ! -f "app/minifw_ai/collector_flow.py" ]; then
    echo "WARNING: app/minifw_ai/collector_flow.py not found!"
    echo "Please copy collector_flow.py to app/minifw_ai/ first"
    exit 1
fi
echo "✓ collector_flow.py found"

# Check testing directory
if [ ! -d "testing" ]; then
    echo "ERROR: testing directory not found!"
    exit 1
fi
echo "✓ testing directory found"

# Check test scripts
test_scripts=(
    "test_flow_collector.py"
    "test_flow_collector_simulated.py"
    "test_real_traffic.py"
    "test_standalone_integration.py"
)

for script in "${test_scripts[@]}"; do
    if [ ! -f "testing/$script" ]; then
        echo "WARNING: testing/$script not found"
    else
        echo "✓ $script found"
    fi
done

echo ""
echo "[3/4] Creating output directories..."
mkdir -p data/testing_output
echo "✓ Created ./data/testing_output/"

echo ""
echo "[4/4] Setting up Python environment..."

# Add app to PYTHONPATH
export PYTHONPATH="${PROJECT_DIR}/app:${PYTHONPATH}"
echo "✓ Added to PYTHONPATH: ${PROJECT_DIR}/app"

echo ""
echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo ""
echo "Directory Structure:"
echo "  testing/              - All test scripts"
echo "  scripts/              - Setup and utility scripts"
echo "  data/testing_output/  - Test output files"
echo ""
echo "Available Tests:"
echo ""
echo "  1. Standalone Integration (No Root, No Gateway)"
echo "     python3 testing/test_standalone_integration.py 500"
echo ""
echo "  2. Simulated Flow Generation (No Root)"
echo "     python3 testing/test_flow_collector_simulated.py 100"
echo ""
echo "  3. Real Traffic Test (Requires Root & dnsmasq)"
echo "     sudo python3 testing/test_real_traffic.py 5"
echo ""
echo "  4. Flow Collector Only (Requires Root)"
echo "     sudo python3 testing/test_flow_collector.py 60"
echo ""
echo "Output Location:"
echo "  All tests output to: ./data/testing_output/"
echo ""
echo "Note: To make PYTHONPATH permanent for this session:"
echo "  export PYTHONPATH=\"${PROJECT_DIR}/app:\${PYTHONPATH}\""
echo ""
echo "For more details, see: testing/README.md"
echo ""