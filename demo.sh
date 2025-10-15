#!/bin/bash
# DV-Smith v0.2.0 Quick Demo
# Demonstrates the new Typer + Rich CLI

set -e

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  DV-SMITH v0.2.0 - Quick Demo"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check prerequisites
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "⚠️  Warning: ANTHROPIC_API_KEY not set"
    echo "   Set it with: export ANTHROPIC_API_KEY=your-key-here"
    echo ""
fi

# Show version
echo "1. Version Check:"
python3 -m dvsmith.cli.app --version
echo ""

# Show help
echo "2. Available Commands:"
python3 -m dvsmith.cli.app --help | grep -A 20 "Commands"
echo ""

# Demo ingest (if API key available)
if [ -n "$ANTHROPIC_API_KEY" ]; then
    echo "3. Demo: Ingesting APB AVIP repository..."
    echo "   (This will take ~30 seconds)"
    echo ""
    
    DEMO_WORKSPACE="/tmp/dvsmith_demo_$(date +%s)"
    
    python3 -m dvsmith.cli.app ingest \
        --workspace "$DEMO_WORKSPACE" \
        https://github.com/mbits-mirafra/apb_avip
    
    echo ""
    echo "4. Demo: Listing Profiles..."
    python3 -m dvsmith.cli.app list-profiles --workspace "$DEMO_WORKSPACE"
    
    echo ""
    echo "5. Demo: Workspace Info..."
    python3 -m dvsmith.cli.app info --workspace "$DEMO_WORKSPACE"
    
    echo ""
    echo "6. Demo: Validating Profile..."
    python3 -m dvsmith.cli.app validate-profile \
        "$DEMO_WORKSPACE/profiles/apb_avip.yaml"
    
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  ✅ Demo Complete!"
    echo "  Workspace: $DEMO_WORKSPACE"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
else
    echo "3. Skipping demo (no ANTHROPIC_API_KEY)"
    echo ""
    echo "To run full demo:"
    echo "  export ANTHROPIC_API_KEY=your-key"
    echo "  ./demo.sh"
fi

echo ""
echo "Try it yourself:"
echo "  dvsmith ingest <repo-url>"
echo "  dvsmith list-profiles"
echo "  dvsmith info"
