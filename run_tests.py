#!/usr/bin/env python3
"""
Test runner script for the Vinyl Recognition System.

This script provides an easy way to run tests with different configurations
and generate coverage reports.
"""

import sys
import subprocess
import argparse
from pathlib import Path


def run_command(cmd, description):
    """Run a command and handle errors."""
    print(f"\n🔄 {description}")
    print(f"Running: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("✅ Success!")
        if result.stdout:
            print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Error: {e}")
        if e.stdout:
            print("STDOUT:", e.stdout)
        if e.stderr:
            print("STDERR:", e.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(description="Run tests for Vinyl Recognition System")
    parser.add_argument("--quick", action="store_true", help="Run quick tests only")
    parser.add_argument("--coverage", action="store_true", help="Generate coverage report")
    parser.add_argument("--html", action="store_true", help="Generate HTML coverage report")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--unit", action="store_true", help="Run unit tests only")
    parser.add_argument("--integration", action="store_true", help="Run integration tests only")
    parser.add_argument("--file", help="Run specific test file")
    parser.add_argument("--install-deps", action="store_true", help="Install test dependencies")
    
    args = parser.parse_args()
    
    # Check if we're in the right directory
    if not Path("src").exists():
        print("❌ Error: Please run this script from the project root directory")
        sys.exit(1)
    
    # Install dependencies if requested
    if args.install_deps:
        print("📦 Installing test dependencies...")
        if not run_command([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], 
                          "Installing dependencies"):
            sys.exit(1)
    
    # Build pytest command
    cmd = [sys.executable, "-m", "pytest"]
    
    # Check if pytest is available
    try:
        subprocess.run([sys.executable, "-m", "pytest", "--version"], 
                      check=True, capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ pytest not found. Installing test dependencies...")
        if not run_command([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], 
                          "Installing dependencies"):
            print("❌ Failed to install dependencies. Please run manually:")
            print("   pip install -r requirements.txt")
            sys.exit(1)
    
    if args.verbose:
        cmd.append("-v")
    
    if args.quick:
        cmd.extend(["-m", "not slow"])
    elif args.unit:
        cmd.extend(["-m", "unit"])
    elif args.integration:
        cmd.extend(["-m", "integration"])
    
    if args.file:
        cmd.append(args.file)
    
    if args.coverage:
        cmd.extend([
            "--cov=src",
            "--cov-report=term-missing",
            "--cov-fail-under=80"
        ])
    
    if args.html:
        cmd.extend([
            "--cov=src",
            "--cov-report=html:htmlcov",
            "--cov-report=term-missing"
        ])
    
    # Run tests
    print("🧪 Running Vinyl Recognition System Tests")
    print("=" * 50)
    
    success = run_command(cmd, "Running tests")
    
    if success:
        print("\n🎉 All tests passed!")
        
        if args.coverage or args.html:
            print("\n📊 Coverage Report:")
            print("   - HTML report: htmlcov/index.html")
            print("   - XML report: coverage.xml")
        
        if args.html:
            print("\n🌐 Open coverage report:")
            print("   open htmlcov/index.html")
    else:
        print("\n💥 Tests failed!")
        sys.exit(1)


if __name__ == "__main__":
    main() 