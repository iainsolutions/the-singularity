#!/usr/bin/env python3
"""
Start script for the Innovation game backend server.
"""

import sys
import subprocess
import os
import signal
import socket
from pathlib import Path

# Load environment variables from .env before anything else
try:
    from dotenv import load_dotenv  # type: ignore

    def _load_env_files():
        # Try project root, then backend dir
        repo_root = Path(__file__).resolve().parent
        candidates = [
            repo_root.parent / ".env",
            repo_root / ".env",
        ]
        for p in candidates:
            if p.exists():
                # Only override in dev to avoid clobbering deployment secrets
                is_dev = os.getenv("INNOVATION_ENV", "development") == "development"
                load_dotenv(dotenv_path=p, override=is_dev)
except Exception:
    def _load_env_files():
        # dotenv not available; continue without .env
        pass

def is_port_in_use(port):
    """Check if a port is in use."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0

def kill_process_on_port(port):
    """Kill any process using the specified port.

    Tries psutil if available; falls back to lsof/kill on Unix systems.
    """
    # Attempt psutil approach first (installed via requirements.txt)
    try:
        import psutil  # type: ignore

        for proc in psutil.process_iter(['pid', 'name', 'connections']):
            try:
                for conn in proc.info.get('connections', []):
                    if getattr(conn.laddr, 'port', None) == port:
                        print(f"Found existing process {proc.info['name']} (PID: {proc.info['pid']}) on port {port}")
                        print(f"Stopping PID {proc.info['pid']}...")
                        proc.terminate()
                        try:
                            proc.wait(timeout=5)
                        except psutil.TimeoutExpired:
                            print(f"Force killing PID {proc.info['pid']}...")
                            proc.kill()
                        print("Process stopped.")
                        return True
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, AttributeError):
                continue
    except Exception:
        # Fallback for environments without psutil (e.g., fresh setup)
        try:
            # macOS/Linux: lsof to find PIDs, then kill
            result = subprocess.run(
                ["lsof", "-t", f"-i:{port}"], capture_output=True, text=True
            )
            pids = [pid.strip() for pid in result.stdout.splitlines() if pid.strip()]
            killed_any = False
            for pid in pids:
                try:
                    print(f"Stopping PID {pid} on port {port}...")
                    os.kill(int(pid), signal.SIGTERM)
                    killed_any = True
                except Exception:
                    # Try force kill
                    try:
                        os.kill(int(pid), signal.SIGKILL)
                        killed_any = True
                    except Exception:
                        pass
            if killed_any:
                print("Process(es) stopped.")
                return True
        except FileNotFoundError:
            # lsof not available; best effort only
            pass

    return False

def check_redis():
    """Check if Redis is installed and optionally start it."""
    try:
        # Check if Redis server is installed
        result = subprocess.run(['which', 'redis-server'], capture_output=True, text=True)
        if result.returncode == 0:
            # Check if Redis is already running on port 6379
            if not is_port_in_use(6379):
                print("Redis is installed but not running. Starting Redis...")
                # Start Redis in the background
                subprocess.Popen(['redis-server', '--daemonize', 'yes'],
                               stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL)
                print("Redis started on port 6379")
            else:
                print("Redis is already running on port 6379")
        else:
            print("Redis not installed. Application will use in-memory storage.")
            print("To install Redis (optional): brew install redis (macOS) or apt-get install redis-server (Linux)")
    except Exception as e:
        print(f"Could not check Redis status: {e}")
        print("Application will use in-memory storage if Redis is unavailable.")

def clear_python_cache():
    """Clear Python bytecode cache to force module recompilation in debug mode."""
    debug_mode = os.getenv('INNOVATION_DEBUG', 'false').lower() == 'true'
    if not debug_mode:
        return

    print("Debug mode: Clearing Python bytecode cache...")
    backend_dir = Path(__file__).resolve().parent / 'backend'
    if not backend_dir.exists():
        return

    import shutil
    cache_dirs_removed = 0
    for pycache in backend_dir.rglob('__pycache__'):
        try:
            shutil.rmtree(pycache)
            cache_dirs_removed += 1
        except Exception as e:
            print(f"  Warning: Could not remove {pycache}: {e}")

    if cache_dirs_removed > 0:
        print(f"  Cleared {cache_dirs_removed} __pycache__ directories")
    else:
        print("  No cache directories found")

def main():
    # Load .env early so flags like INNOVATION_DEBUG are honored
    _load_env_files()
    # Small visibility log for debug gating of admin endpoints
    try:
        debug_value = os.getenv('INNOVATION_DEBUG', 'false')
        debug_enabled = debug_value.lower() == 'true'
        print(f"INNOVATION_DEBUG detected: {debug_enabled} (raw value: {debug_value})")
    except Exception:
        pass

    # Clear Python cache in debug mode to ensure code changes are loaded
    clear_python_cache()

    # Check and optionally start Redis
    check_redis()

    # Check and kill any existing process on port 8000
    if is_port_in_use(8000):
        print("Port 8000 is already in use.")
        kill_process_on_port(8000)
        # Give the OS a moment to release the port
        import time
        time.sleep(1)

    # Change to backend directory
    backend_dir = os.path.join(os.path.dirname(__file__), 'backend')

    if not os.path.exists(backend_dir):
        print("Backend directory not found!")
        sys.exit(1)

    os.chdir(backend_dir)

    # Check if virtual environment exists
    if not os.path.exists('../venv') and not os.path.exists('venv'):
        print("No virtual environment found. Creating one...")
        # Prefer Python 3.11/3.12 for best wheels compatibility (pydantic-core)
        candidates = ['python3.11', 'python3.12', 'python3', sys.executable]
        python_cmd = None
        for cand in candidates:
            try:
                subprocess.run([cand, '--version'], check=True, capture_output=True)
                python_cmd = cand
                break
            except (subprocess.CalledProcessError, FileNotFoundError):
                continue
        if not python_cmd:
            python_cmd = sys.executable

        subprocess.run([python_cmd, '-m', 'venv', '../venv'], check=True)
        print("Virtual environment created.")

    # Install dependencies
    venv_python = '../venv/bin/python' if os.name != 'nt' else '../venv/Scripts/python.exe'
    venv_pip = '../venv/bin/pip' if os.name != 'nt' else '../venv/Scripts/pip.exe'

    print("Installing dependencies...")
    subprocess.run([venv_pip, 'install', '-r', '../requirements.txt'], check=True)

    print("Starting Innovation backend server on http://localhost:8000")
    print("Press Ctrl+C to stop the server")

    # Ensure a dev JWT secret for non-prod/local runs (respect .env if provided)
    os.environ.setdefault(
        'JWT_SECRET_KEY', os.getenv('JWT_SECRET_KEY', 'dev-local-secret-not-for-prod-12345678901234567890')
    )

    # Prefer uvicorn in CI or when USE_UVICORN is set
    use_uvicorn = os.getenv('GITHUB_ACTIONS') == 'true' or os.getenv('USE_UVICORN', 'false').lower() == 'true'
    if use_uvicorn:
        try:
            uvicorn_bin = '../venv/bin/uvicorn' if os.name != 'nt' else '../venv/Scripts/uvicorn.exe'
            # We are already chdir'ed into the backend directory above, so import path is just 'main:app'
            subprocess.run([uvicorn_bin, 'main:app', '--host', '127.0.0.1', '--port', '8000', '--log-level', 'info'], check=True)
            return
        except Exception as e:
            print(f"Failed to start via uvicorn in CI mode: {e}. Falling back to main.py")

    # Start the server via uvicorn (not main.py directly)
    # This ensures main.py is imported as 'main' module, not '__main__'
    # which prevents duplicate module initialization issues with admin routes
    try:
        uvicorn_bin = '../venv/bin/uvicorn' if os.name != 'nt' else '../venv/Scripts/uvicorn.exe'
        # Already in backend directory; use 'main:app'
        subprocess.run([uvicorn_bin, 'main:app', '--host', '0.0.0.0', '--port', '8000', '--log-level', 'info'], check=True)
    except Exception as e:
        print(f"uvicorn startup failed: {e}")
        raise

if __name__ == '__main__':
    main()
