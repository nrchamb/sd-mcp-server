#!/usr/bin/env python3
"""
Check for missing dependencies that might cause upload server failures
"""

import sys
import subprocess
import os

def check_dependency(module_name, import_name=None):
    """Check if a Python module is available"""
    if import_name is None:
        import_name = module_name
    
    try:
        __import__(import_name)
        print(f"✅ {module_name}: Available")
        return True
    except ImportError as e:
        print(f"❌ {module_name}: Missing ({e})")
        return False

def check_system_dependencies():
    """Check system-level dependencies"""
    print("🔍 Checking System Dependencies")
    print("=" * 40)
    
    # Check Python version
    python_version = sys.version
    print(f"Python version: {python_version}")
    
    # Check if uvicorn is available
    try:
        result = subprocess.run(["uvicorn", "--version"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            print(f"✅ uvicorn: {result.stdout.strip()}")
        else:
            print(f"❌ uvicorn: Command failed")
    except Exception as e:
        print(f"❌ uvicorn: Not available ({e})")
    
    # Check port availability
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(('0.0.0.0', 8080))
        s.close()
        print(f"✅ Port 8080: Available")
    except Exception as e:
        print(f"❌ Port 8080: In use or blocked ({e})")

def check_python_dependencies():
    """Check Python module dependencies"""
    print("\n🐍 Checking Python Dependencies")
    print("=" * 40)
    
    dependencies = [
        ("fastapi", "fastapi"),
        ("uvicorn", "uvicorn"),
        ("httpx", "httpx"),
        ("pydantic", "pydantic"),
        ("PIL/Pillow", "PIL"),
        ("pathlib", "pathlib"),
        ("asyncio", "asyncio"),
        ("multipart", "python_multipart")
    ]
    
    missing = []
    for dep_name, import_name in dependencies:
        if not check_dependency(dep_name, import_name):
            missing.append(dep_name)
    
    return missing

def test_upload_service_imports():
    """Test if upload service can import properly"""
    print("\n📦 Testing Upload Service Imports")
    print("=" * 40)
    
    try:
        # Change to the correct directory
        original_dir = os.getcwd()
        os.chdir("/Volumes/4TB NVMe/Coding/MCP/sd-mcp-server")
        
        # Try to import the upload service
        sys.path.insert(0, ".")
        import upload_service_production
        print("✅ Upload service imports successfully")
        
        # Test FastAPI app creation
        app = upload_service_production.app
        print("✅ FastAPI app created successfully")
        
        return True
        
    except Exception as e:
        print(f"❌ Upload service import failed: {e}")
        return False
    finally:
        os.chdir(original_dir)

def main():
    print("🔧 Dependency Check for Upload Service")
    print("=" * 50)
    
    # Check system dependencies
    check_system_dependencies()
    
    # Check Python dependencies
    missing_deps = check_python_dependencies()
    
    # Test upload service
    upload_service_ok = test_upload_service_imports()
    
    # Summary
    print("\n📊 SUMMARY")
    print("=" * 20)
    
    if missing_deps:
        print("❌ Missing dependencies:")
        for dep in missing_deps:
            print(f"   - {dep}")
        print("\n💡 Install missing dependencies with:")
        print("   pip install " + " ".join(missing_deps))
    else:
        print("✅ All Python dependencies available")
    
    if not upload_service_ok:
        print("❌ Upload service has import issues")
    else:
        print("✅ Upload service imports correctly")
    
    print("\n🎯 Next steps:")
    if missing_deps:
        print("1. Install missing dependencies")
    if not upload_service_ok:
        print("2. Check upload service code for errors")
    print("3. Test upload service manually")
    print("4. Check firewall/port settings")

if __name__ == "__main__":
    main()