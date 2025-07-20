#!/usr/bin/env python3
"""
Startup script for Discord bot and MCP HTTP server
"""

import os
import sys
import asyncio
import subprocess
import signal
import time
import json
from pathlib import Path

# Add project root to path for imports
sys.path.append(str(Path(__file__).parent))
from modules.config import load_mcp_environment

def load_environment_from_mcp():
    """Load environment variables from MCP.json using configurable path"""
    try:
        # Use the new configurable MCP config loader
        success = load_mcp_environment()
        
        if success:
            print("✅ Loaded environment variables from MCP.json")
        else:
            print("⚠️ Could not load MCP.json - using environment variables")
            
        return success
        
    except Exception as e:
        print(f"❌ Could not load MCP.json: {e}")
        return False

def check_environment():
    """Check required environment variables"""
    # Core required variables for Discord bot
    required_vars = [
        'DISCORD_BOT_TOKEN',
        'SD_BASE_URL',
        'CHEVERETO_BASE_URL'
    ]
    
    # Optional variables that will be checked and warned about
    optional_vars = [
        'CHEVERETO_USER_API_KEY',
        'CHEVERETO_GUEST_API_KEY'
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print(f"❌ Missing required environment variables: {', '.join(missing_vars)}")
        print("\n📋 Set these in your environment or mcp.json:")
        print("  DISCORD_BOT_TOKEN=your_discord_bot_token")
        print("  SD_BASE_URL=your_sd_webui_url")
        print("  CHEVERETO_BASE_URL=your_chevereto_url")
        return False
    
    # Check optional variables and warn
    missing_optional = []
    for var in optional_vars:
        if not os.getenv(var):
            missing_optional.append(var)
    
    if missing_optional:
        print(f"⚠️ Optional variables not set: {', '.join(missing_optional)}")
        print("   System will use fallback modes (guest uploads, local storage)")
    
    # Show configuration status
    print("\n📊 Configuration Status:")
    print(f"  Discord Bot: {'✅' if os.getenv('DISCORD_BOT_TOKEN') else '❌'}")
    print(f"  SD WebUI: {'✅' if os.getenv('SD_BASE_URL') else '❌'}")
    print(f"  Chevereto Base: {'✅' if os.getenv('CHEVERETO_BASE_URL') else '❌'}")
    print(f"  User API Key: {'✅' if os.getenv('CHEVERETO_USER_API_KEY') else '⚠️ Guest mode'}")
    print(f"  Guest API Key: {'✅' if os.getenv('CHEVERETO_GUEST_API_KEY') else '⚠️ Local storage'}")
    print(f"  NSFW Filter: {'✅' if os.getenv('NSFW_FILTER', 'false').lower() == 'true' else '⚠️ Disabled'}")
    
    print("\n💡 Optional variables:")
    print("  MCP_HTTP_HOST=127.0.0.1")
    print("  MCP_HTTP_PORT=8000")
    
    return True

def start_mcp_http_server():
    """Start MCP HTTP server"""
    print("🚀 Starting MCP HTTP Server...")
    
    # Set environment variables from existing SD server config
    env = os.environ.copy()
    
    # Start the HTTP server with uv run
    process = subprocess.Popen([
        "/Users/nickchamberlain/.local/bin/uv", "run", "python", "mcp_http_server.py"
    ], env=env)
    
    # Wait a moment for server to start
    time.sleep(2)
    
    return process

def start_discord_bot():
    """Start Discord bot"""
    print("🤖 Starting Discord Bot...")
    
    # Set environment variables
    env = os.environ.copy()
    env['MCP_SERVER_URL'] = f"http://{os.getenv('MCP_HTTP_HOST', '127.0.0.1')}:{os.getenv('MCP_HTTP_PORT', '8000')}"
    
    # Start the bot with uv run to ensure proper environment
    process = subprocess.Popen([
        "/Users/nickchamberlain/.local/bin/uv", "run", "python", "discord_bot.py"
    ], env=env)
    
    return process

def main():
    """Main startup function"""
    print("🎮 SD MCP Server Discord Bot Startup")
    print("=" * 50)
    
    # Load environment from MCP.json first
    if not load_environment_from_mcp():
        print("⚠️  Falling back to system environment variables")
    
    # Check environment
    if not check_environment():
        sys.exit(1)
    
    # Change to project directory
    os.chdir(Path(__file__).parent)
    
    # Start MCP HTTP server
    mcp_process = start_mcp_http_server()
    
    # Start Discord bot
    bot_process = start_discord_bot()
    
    print("\n✅ Both services started!")
    print("📊 Status:")
    print(f"  MCP HTTP Server: PID {mcp_process.pid}")
    print(f"  Discord Bot: PID {bot_process.pid}")
    print("\n🔗 Access:")
    print(f"  MCP HTTP API: http://{os.getenv('MCP_HTTP_HOST', '127.0.0.1')}:{os.getenv('MCP_HTTP_PORT', '8000')}")
    print("  Discord Bot: Check your Discord server")
    print("\n🛑 Press Ctrl+C to stop both services")
    
    def signal_handler(signum, frame):
        """Handle shutdown signal"""
        print("\n🛑 Shutting down services...")
        mcp_process.terminate()
        bot_process.terminate()
        
        # Wait for processes to exit
        mcp_process.wait()
        bot_process.wait()
        
        print("✅ Services stopped")
        sys.exit(0)
    
    # Register signal handler
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Keep running until interrupted
    try:
        while True:
            time.sleep(1)
            
            # Check if processes are still running
            if mcp_process.poll() is not None:
                print("❌ MCP HTTP Server stopped unexpectedly")
                bot_process.terminate()
                sys.exit(1)
            
            if bot_process.poll() is not None:
                print("❌ Discord Bot stopped unexpectedly")
                mcp_process.terminate()
                sys.exit(1)
    except KeyboardInterrupt:
        signal_handler(signal.SIGINT, None)

if __name__ == "__main__":
    main()