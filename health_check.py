#!/usr/bin/env python3
"""
Health check system for SD MCP Server components
"""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional
import httpx
from datetime import datetime

# Add project root to path
sys.path.append(str(Path(__file__).parent))
from modules.config import load_mcp_environment

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('HealthCheck')

class HealthChecker:
    """Health check system for all components"""
    
    def __init__(self):
        # Load environment from MCP.json if available
        self.load_environment_from_mcp()
        
        self.components = {
            'sd_webui': {
                'name': 'Stable Diffusion WebUI',
                'url': os.getenv('SD_BASE_URL', 'http://localhost:7860'),
                'endpoints': ['/sdapi/v1/txt2img', '/sdapi/v1/options'],
                'critical': True
            },
            'chevereto': {
                'name': 'Chevereto Image Hosting',
                'url': os.getenv('CHEVERETO_BASE_URL', ''),
                'endpoints': ['/api/1/upload'],
                'critical': False
            },
            'mcp_http': {
                'name': 'MCP HTTP Server',
                'url': f"http://{os.getenv('MCP_HTTP_HOST', '127.0.0.1')}:{os.getenv('MCP_HTTP_PORT', '8000')}",
                'endpoints': ['/health', '/tools/get_models'],
                'critical': False
            },
            'discord_bot': {
                'name': 'Discord Bot',
                'url': None,  # Discord bot doesn't have HTTP endpoint
                'endpoints': [],
                'critical': False
            }
        }
        
        self.timeout = 10  # seconds
    
    def load_environment_from_mcp(self):
        """Load environment variables from MCP.json using configurable path"""
        try:
            # Use the new configurable MCP config loader
            success = load_mcp_environment()
            
            if success:
                logger.info("✅ Loaded environment variables from MCP.json")
            else:
                logger.warning("⚠️ Could not load MCP.json")
                logger.info("📝 Using default environment variables")
                
        except Exception as e:
            logger.warning(f"⚠️ Could not load MCP.json: {e}")
            logger.info("📝 Using default environment variables")
    
    async def check_component(self, component_name: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Check health of a single component"""
        result = {
            'name': config['name'],
            'status': 'unknown',
            'available': False,
            'response_time': None,
            'error': None,
            'details': {}
        }
        
        if not config['url']:
            result['status'] = 'disabled'
            result['error'] = 'No URL configured'
            return result
        
        try:
            start_time = datetime.now()
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # Check main URL
                response = await client.get(config['url'])
                
                response_time = (datetime.now() - start_time).total_seconds()
                result['response_time'] = response_time
                
                if response.status_code == 200 or (response.status_code == 302 and component_name == 'chevereto'):
                    result['status'] = 'healthy'
                    result['available'] = True
                    result['details']['http_status'] = response.status_code
                    if response.status_code == 302:
                        result['details']['redirect_note'] = 'Chevereto login redirect (normal)'
                    
                    # Check specific endpoints if configured
                    endpoint_results = {}
                    for endpoint in config['endpoints']:
                        try:
                            ep_response = await client.get(f"{config['url']}{endpoint}")
                            endpoint_results[endpoint] = {
                                'status': ep_response.status_code,
                                'available': ep_response.status_code < 500
                            }
                        except Exception as e:
                            endpoint_results[endpoint] = {
                                'status': 'error',
                                'error': str(e),
                                'available': False
                            }
                    
                    result['details']['endpoints'] = endpoint_results
                else:
                    result['status'] = 'unhealthy'
                    result['error'] = f"HTTP {response.status_code}"
                    result['details']['http_status'] = response.status_code
                    
        except httpx.TimeoutException:
            result['status'] = 'timeout'
            result['error'] = f"Timeout after {self.timeout}s"
        except httpx.ConnectError:
            result['status'] = 'unavailable'
            result['error'] = 'Connection failed'
        except Exception as e:
            result['status'] = 'error'
            result['error'] = str(e)
        
        return result
    
    async def check_all_components(self) -> Dict[str, Any]:
        """Check health of all components"""
        results = {}
        
        # Check all components concurrently
        tasks = []
        for component_name, config in self.components.items():
            if component_name == 'discord_bot':
                # Special handling for Discord bot
                results[component_name] = await self.check_discord_bot()
            else:
                tasks.append(self.check_component(component_name, config))
        
        # Wait for all HTTP checks to complete
        component_results = await asyncio.gather(*tasks)
        
        # Map results back to component names
        http_components = [name for name in self.components.keys() if name != 'discord_bot']
        for i, component_name in enumerate(http_components):
            results[component_name] = component_results[i]
        
        return results
    
    async def check_discord_bot(self) -> Dict[str, Any]:
        """Check Discord bot health (placeholder)"""
        # This would require Discord bot to report its status
        # For now, assume it's healthy if process is running
        return {
            'name': 'Discord Bot',
            'status': 'unknown',
            'available': None,
            'response_time': None,
            'error': 'Health check not implemented',
            'details': {}
        }
    
    def get_system_status(self, component_results: Dict[str, Any]) -> Dict[str, Any]:
        """Get overall system status"""
        total_components = len(component_results)
        healthy_components = sum(1 for result in component_results.values() 
                               if result['status'] == 'healthy')
        available_components = sum(1 for result in component_results.values() 
                                 if result['available'])
        
        # Check critical components
        critical_components = [name for name, config in self.components.items() 
                             if config['critical']]
        critical_healthy = sum(1 for name in critical_components 
                             if component_results.get(name, {}).get('status') == 'healthy')
        
        # Determine overall status
        if critical_healthy == len(critical_components):
            if healthy_components == total_components:
                overall_status = 'healthy'
            else:
                overall_status = 'degraded'
        else:
            overall_status = 'unhealthy'
        
        return {
            'overall_status': overall_status,
            'healthy_components': healthy_components,
            'total_components': total_components,
            'available_components': available_components,
            'critical_components_healthy': critical_healthy,
            'critical_components_total': len(critical_components),
            'can_generate_images': component_results.get('sd_webui', {}).get('available', False),
            'can_upload_images': component_results.get('chevereto', {}).get('available', False),
            'can_use_discord': component_results.get('discord_bot', {}).get('available', False),
            'timestamp': datetime.now().isoformat()
        }

class FailureHandler:
    """Handle various failure scenarios"""
    
    @staticmethod
    def handle_sd_unavailable() -> Dict[str, Any]:
        """Handle SD WebUI unavailability"""
        return {
            'error': 'Stable Diffusion WebUI is not available',
            'suggestions': [
                'Check if SD WebUI is running',
                'Verify SD_BASE_URL configuration',
                'Check network connectivity',
                'Try restarting SD WebUI'
            ],
            'fallback': 'Image generation is not possible'
        }
    
    @staticmethod
    def handle_chevereto_unavailable() -> Dict[str, Any]:
        """Handle Chevereto unavailability"""
        return {
            'error': 'Chevereto image hosting is not available',
            'suggestions': [
                'Check Chevereto server status',
                'Verify CHEVERETO_BASE_URL configuration',
                'Check API key validity',
                'Use local storage as fallback'
            ],
            'fallback': 'Images will be stored locally only'
        }
    
    @staticmethod
    def handle_discord_unavailable() -> Dict[str, Any]:
        """Handle Discord bot unavailability"""
        return {
            'error': 'Discord bot is not available',
            'suggestions': [
                'Check Discord bot token',
                'Verify bot permissions',
                'Check network connectivity',
                'Try restarting the bot'
            ],
            'fallback': 'Use MCP server directly through LM Studio'
        }
    
    @staticmethod
    def handle_mcp_http_unavailable() -> Dict[str, Any]:
        """Handle MCP HTTP server unavailability"""
        return {
            'error': 'MCP HTTP server is not available',
            'suggestions': [
                'Check if MCP HTTP server is running',
                'Verify port configuration',
                'Check for port conflicts',
                'Try restarting the server'
            ],
            'fallback': 'Discord bot cannot communicate with SD server'
        }

async def main():
    """Main health check function"""
    print("🔍 SD MCP Server Health Check")
    print("=" * 50)
    
    health_checker = HealthChecker()
    
    # Check all components
    component_results = await health_checker.check_all_components()
    
    # Get system status
    system_status = health_checker.get_system_status(component_results)
    
    # Display results
    print(f"\n📊 Overall Status: {system_status['overall_status'].upper()}")
    print(f"✅ Healthy Components: {system_status['healthy_components']}/{system_status['total_components']}")
    print(f"🔧 Critical Components: {system_status['critical_components_healthy']}/{system_status['critical_components_total']}")
    
    print("\n🔍 Component Details:")
    for component_name, result in component_results.items():
        status_icon = {
            'healthy': '✅',
            'degraded': '⚠️',
            'unhealthy': '❌',
            'unavailable': '🔴',
            'timeout': '⏱️',
            'error': '💥',
            'disabled': '⚫',
            'unknown': '❓'
        }.get(result['status'], '❓')
        
        print(f"  {status_icon} {result['name']}: {result['status']}")
        if result['error']:
            print(f"    Error: {result['error']}")
        if result['response_time']:
            print(f"    Response time: {result['response_time']:.2f}s")
    
    # Show capabilities
    print("\n🎯 System Capabilities:")
    print(f"  🎨 Image Generation: {'✅' if system_status['can_generate_images'] else '❌'}")
    print(f"  📤 Image Upload: {'✅' if system_status['can_upload_images'] else '❌'}")
    print(f"  🤖 Discord Bot: {'✅' if system_status['can_use_discord'] else '❌'}")
    
    # Show failures and suggestions
    failure_handler = FailureHandler()
    
    for component_name, result in component_results.items():
        if result['status'] not in ['healthy', 'disabled']:
            print(f"\n⚠️ {result['name']} Issues:")
            
            if component_name == 'sd_webui':
                advice = failure_handler.handle_sd_unavailable()
            elif component_name == 'chevereto':
                advice = failure_handler.handle_chevereto_unavailable()
            elif component_name == 'discord_bot':
                advice = failure_handler.handle_discord_unavailable()
            elif component_name == 'mcp_http':
                advice = failure_handler.handle_mcp_http_unavailable()
            else:
                advice = {'suggestions': ['Check component configuration']}
            
            for suggestion in advice.get('suggestions', []):
                print(f"  💡 {suggestion}")
            
            if 'fallback' in advice:
                print(f"  🔄 Fallback: {advice['fallback']}")
    
    # Return status for scripts
    return system_status['overall_status'] == 'healthy'

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)