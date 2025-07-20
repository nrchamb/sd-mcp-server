#!/usr/bin/env python3
"""
UV Environment GUI Tester Launcher

Ensures the GUI testing tool runs in the proper UV environment with all dependencies.
Also provides option to open terminal in UV environment for manual testing.
"""

import os
import sys
import subprocess
import platform
from pathlib import Path

def check_uv_installed():
    """Check if UV is installed and accessible"""
    try:
        result = subprocess.run(["uv", "--version"], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ UV found: {result.stdout.strip()}")
            return True
        else:
            print("❌ UV command failed")
            return False
    except FileNotFoundError:
        print("❌ UV not found in PATH")
        return False

def check_uv_environment():
    """Check if we're in a UV project with dependencies"""
    project_root = Path(__file__).parent
    
    # Check for pyproject.toml
    if not (project_root / "pyproject.toml").exists():
        print("❌ pyproject.toml not found - not a UV project")
        return False
    
    # Check for uv.lock
    if not (project_root / "uv.lock").exists():
        print("⚠️  uv.lock not found - run 'uv sync' first")
        return False
    
    print("✅ UV project structure detected")
    return True

def install_gui_dependencies():
    """Install additional GUI dependencies if needed"""
    try:
        print("📦 Installing GUI dependencies...")
        result = subprocess.run([
            "uv", "add", "--dev", "pillow"
        ], cwd=Path(__file__).parent, capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ GUI dependencies installed")
            return True
        else:
            print(f"❌ Failed to install dependencies: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Error installing dependencies: {e}")
        return False

def launch_gui_in_uv():
    """Launch the GUI tester in UV environment"""
    project_root = Path(__file__).parent
    gui_script = project_root / "gui_tester.py"
    
    if not gui_script.exists():
        print("❌ gui_tester.py not found")
        return False
    
    try:
        print("🚀 Launching GUI tester in UV environment...")
        
        # Launch in UV environment
        subprocess.run([
            "uv", "run", "python", str(gui_script)
        ], cwd=project_root)
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to launch GUI: {e}")
        return False

def open_uv_terminal():
    """Open a terminal/command prompt in the UV environment"""
    project_root = Path(__file__).parent
    system = platform.system().lower()
    
    try:
        if system == "windows":
            # Windows: Open Command Prompt with UV environment
            cmd = f'cd /d "{project_root}" && uv run cmd /k "echo UV Environment Ready && echo. && echo Available commands: && echo   python gui_tester.py && echo   python start_discord_bot.py && echo   python scripts/init_databases.py && echo."'
            subprocess.Popen(f'start cmd /c "{cmd}"', shell=True)
            
        elif system == "darwin":  # macOS
            # macOS: Open Terminal with UV environment
            script = f'''
tell application "Terminal"
    do script "cd '{project_root}' && echo '🚀 UV Environment Ready' && echo '' && echo 'Available commands:' && echo '  python gui_tester.py' && echo '  python start_discord_bot.py' && echo '  python scripts/init_databases.py' && echo '' && uv run bash"
    activate
end tell
'''
            subprocess.run(["osascript", "-e", script])
            
        else:  # Linux
            # Linux: Try common terminal emulators
            terminals = ["gnome-terminal", "konsole", "xterm", "terminator"]
            
            for terminal in terminals:
                try:
                    if terminal == "gnome-terminal":
                        subprocess.Popen([
                            terminal, "--", "bash", "-c", 
                            f"cd '{project_root}' && echo '🚀 UV Environment Ready' && echo '' && echo 'Available commands:' && echo '  python gui_tester.py' && echo '  python start_discord_bot.py' && echo '  python scripts/init_databases.py' && echo '' && uv run bash"
                        ])
                    else:
                        subprocess.Popen([
                            terminal, "-e", "bash", "-c",
                            f"cd '{project_root}' && echo '🚀 UV Environment Ready' && echo '' && echo 'Available commands:' && echo '  python gui_tester.py' && echo '  python start_discord_bot.py' && echo '  python scripts/init_databases.py' && echo '' && uv run bash"
                        ])
                    break
                except FileNotFoundError:
                    continue
            else:
                print("❌ No terminal emulator found")
                return False
        
        print("✅ Terminal opened in UV environment")
        return True
        
    except Exception as e:
        print(f"❌ Failed to open terminal: {e}")
        return False

def main():
    print("🔧 SD MCP Server - UV Environment Launcher")
    print("=" * 50)
    
    # Check UV installation
    if not check_uv_installed():
        print("\n💡 Install UV: https://docs.astral.sh/uv/getting-started/installation/")
        return 1
    
    # Check UV environment
    if not check_uv_environment():
        print("\n💡 Run 'uv sync' to set up the environment")
        return 1
    
    # Show options
    print("\nSelect an option:")
    print("1. 🖼️  Launch GUI Tester")
    print("2. 💻 Open Terminal in UV Environment") 
    print("3. 📦 Install/Update GUI Dependencies")
    print("4. ❌ Exit")
    
    try:
        choice = input("\nEnter choice (1-4): ").strip()
        
        if choice == "1":
            # Install GUI deps if needed
            try:
                import tkinter
                from PIL import Image
                print("✅ GUI dependencies available")
            except ImportError:
                print("⚠️  GUI dependencies missing, installing...")
                if not install_gui_dependencies():
                    return 1
            
            return 0 if launch_gui_in_uv() else 1
            
        elif choice == "2":
            return 0 if open_uv_terminal() else 1
            
        elif choice == "3":
            return 0 if install_gui_dependencies() else 1
            
        elif choice == "4":
            print("👋 Goodbye!")
            return 0
            
        else:
            print("❌ Invalid choice")
            return 1
            
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
        return 0
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())