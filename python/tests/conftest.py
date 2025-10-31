"""
Pytest configuration and fixtures for HSX tests.
"""
import subprocess
import sys
from pathlib import Path
import pytest


@pytest.fixture(scope="session", autouse=True)
def build_demo_files():
    """
    Build required demo files before running tests.
    This ensures examples/demos/build/mailbox/*.hxe files exist.
    """
    repo_root = Path(__file__).resolve().parents[2]
    demos_dir = repo_root / "examples" / "demos"
    
    # Check if the required .hxe files exist
    consumer_hxe = demos_dir / "build" / "mailbox" / "consumer.hxe"
    producer_hxe = demos_dir / "build" / "mailbox" / "producer.hxe"
    
    if not (consumer_hxe.exists() and producer_hxe.exists()):
        # Build the demo files using make
        try:
            result = subprocess.run(
                ["make", "mailbox_consumer", "mailbox_producer"],
                cwd=demos_dir,
                capture_output=True,
                text=True,
                timeout=180
            )
            if result.returncode != 0:
                pytest.fail(
                    f"Failed to build demo files:\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}"
                )
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            pytest.fail(f"Failed to build demo files: {e}")
