"""
LLM ↔ SD Integration - Prompt Enhancement
Allows LLM to enhance user prompts and trigger SD generation

INTEGRATION FEATURES:
- Prompt enhancement and optimization
- Auto-generation triggers from chat
- Style recommendations
- Technical parameter suggestions
"""

import json
import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass

from .base_provider import LLMMessage, MessageRole
from .llm_manager import LLMManager

logger = logging.getLogger('PromptEnhancement')

@dataclass
class EnhancedPrompt:
    """Enhanced prompt with SD parameters"""
    original_prompt: str
    enhanced_prompt: str
    negative_prompt: str
    style_suggestions: List[str]
    technical_params: Dict[str, Any]
    reasoning: str
    confidence: float

class PromptEnhancer:
    """LLM-powered prompt enhancement for SD generation"""
    
    def __init__(self, llm_manager: LLMManager):
        self.llm_manager = llm_manager
        
        # System prompt for prompt enhancement
        self.enhancement_prompt = """You are an expert at creating high-quality Stable Diffusion prompts. Your task is to enhance user prompts to generate better images.

ENHANCEMENT GUIDELINES:
1. Keep the original intent and core concept
2. Add relevant style descriptors (e.g., "masterpiece", "highly detailed", "8k resolution")
3. Include technical quality terms (e.g., "professional photography", "cinematic lighting")
4. Suggest appropriate art styles when relevant
5. Add composition and framing details
6. Include material/texture descriptions when applicable

NEGATIVE PROMPT GUIDELINES:
- Include common unwanted elements: "blurry, low quality, pixelated, jpeg artifacts"
- Add anatomy fixes: "deformed, extra limbs, missing limbs, bad anatomy"
- Include style-specific negatives based on the desired output

TECHNICAL PARAMETERS:
- steps: 20-50 (complex scenes need more)
- cfg_scale: 7-12 (higher for stronger prompt adherence)
- width/height: Consider aspect ratio for subject
- sampler suggestions when relevant

RESPONSE FORMAT:
Respond with a JSON object containing:
{
    "enhanced_prompt": "improved version of the prompt",
    "negative_prompt": "appropriate negative prompt",
    "style_suggestions": ["style1", "style2"],
    "technical_params": {
        "steps": 25,
        "cfg_scale": 8,
        "width": 512,
        "height": 768
    },
    "reasoning": "explanation of changes made",
    "confidence": 0.85
}

IMPORTANT: Only respond with the JSON object, no additional text."""

    async def enhance_prompt(self, user_prompt: str, context: Optional[str] = None) -> Optional[EnhancedPrompt]:
        """Enhance a user prompt for better SD generation"""
        try:
            # Build enhancement request
            messages = [
                LLMMessage(role=MessageRole.SYSTEM, content=self.enhancement_prompt),
                LLMMessage(
                    role=MessageRole.USER, 
                    content=f"Original prompt: {user_prompt}\n\nContext: {context or 'None'}\n\nPlease enhance this prompt."
                )
            ]
            
            # Get LLM response
            response = await self.llm_manager.chat(
                messages,
                temperature=0.3,  # Lower temperature for more consistent technical output
                max_tokens=1000
            )
            
            if not response.success:
                logger.error(f"LLM enhancement failed: {response.error}")
                return None
            
            # Parse JSON response
            try:
                data = json.loads(response.content.strip())
                
                return EnhancedPrompt(
                    original_prompt=user_prompt,
                    enhanced_prompt=data.get('enhanced_prompt', user_prompt),
                    negative_prompt=data.get('negative_prompt', ''),
                    style_suggestions=data.get('style_suggestions', []),
                    technical_params=data.get('technical_params', {}),
                    reasoning=data.get('reasoning', ''),
                    confidence=data.get('confidence', 0.5)
                )
                
            except json.JSONDecodeError:
                logger.error(f"Failed to parse LLM response as JSON: {response.content}")
                
                # Fallback: try to extract enhanced prompt from text
                lines = response.content.strip().split('\n')
                enhanced = user_prompt
                for line in lines:
                    if line.strip() and not line.startswith('{') and not line.startswith('}'):
                        enhanced = line.strip()
                        break
                
                return EnhancedPrompt(
                    original_prompt=user_prompt,
                    enhanced_prompt=enhanced,
                    negative_prompt="low quality, blurry, deformed",
                    style_suggestions=[],
                    technical_params={'steps': 25, 'cfg_scale': 8},
                    reasoning="Fallback enhancement",
                    confidence=0.3
                )
                
        except Exception as e:
            logger.error(f"Error enhancing prompt: {e}")
            return None
    
    async def detect_generation_intent(self, message: str) -> Optional[Dict[str, Any]]:
        """Detect if user wants to generate an image from their message"""
        
        # Keywords that indicate image generation intent
        generation_keywords = [
            'generate', 'create', 'make', 'draw', 'paint', 'render',
            'image of', 'picture of', 'art of', 'illustration of',
            'show me', 'can you make', 'i want to see',
            '/imagine', '/gen', '/img'
        ]
        
        # Art style keywords
        style_keywords = [
            'anime', 'realistic', 'cartoon', 'photorealistic', 'digital art',
            'oil painting', 'watercolor', 'sketch', 'concept art', 'pixel art',
            'cyberpunk', 'steampunk', 'fantasy', 'sci-fi', 'abstract'
        ]
        
        message_lower = message.lower()
        
        # Check for explicit generation commands
        if any(keyword in message_lower for keyword in generation_keywords):
            # Extract potential prompt
            prompt = message
            
            # Remove common generation prefixes
            for prefix in ['generate', 'create', 'make', 'draw', 'paint', 'render']:
                if message_lower.startswith(prefix):
                    prompt = message[len(prefix):].strip()
                    break
            
            # Remove common phrases
            prompt = prompt.replace('an image of', '').replace('a picture of', '').replace('art of', '')
            prompt = prompt.replace('show me', '').replace('can you make', '').replace('i want to see', '')
            prompt = prompt.strip()
            
            if prompt:
                return {
                    'intent': 'generate',
                    'prompt': prompt,
                    'confidence': 0.8,
                    'has_style': any(style in message_lower for style in style_keywords)
                }
        
        # Check for style descriptions that might indicate image intent
        if any(style in message_lower for style in style_keywords):
            if len(message.split()) > 3:  # Substantial description
                return {
                    'intent': 'possible_generate',
                    'prompt': message,
                    'confidence': 0.4,
                    'has_style': True
                }
        
        return None

class ChatImageIntegration:
    """Integrates LLM chat with SD image generation"""
    
    def __init__(self, llm_manager: LLMManager, mcp_server_caller=None):
        self.llm_manager = llm_manager
        self.prompt_enhancer = PromptEnhancer(llm_manager)
        self.mcp_server_caller = mcp_server_caller
        
        self.integration_enabled = bool(mcp_server_caller)
        
        if not self.integration_enabled:
            logger.warning("SD integration disabled - no MCP server caller provided")
    
    async def process_chat_message(self, message: str, user_id: str) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        """
        Process chat message for potential image generation
        Returns: (chat_response, generation_data)
        """
        if not self.integration_enabled:
            return None, None
        
        # Detect generation intent
        intent_data = await self.prompt_enhancer.detect_generation_intent(message)
        
        if not intent_data:
            return None, None
        
        # Handle explicit generation requests
        if intent_data['intent'] == 'generate':
            return await self._handle_generation_request(intent_data['prompt'], user_id)
        
        # Handle possible generation (ask user)
        elif intent_data['intent'] == 'possible_generate' and intent_data['confidence'] > 0.3:
            return await self._suggest_generation(intent_data['prompt'], user_id)
        
        return None, None
    
    async def _handle_generation_request(self, prompt: str, user_id: str) -> Tuple[str, Dict[str, Any]]:
        """Handle explicit image generation request"""
        try:
            # Enhance the prompt
            enhanced = await self.prompt_enhancer.enhance_prompt(prompt)
            
            if not enhanced:
                return "❌ Sorry, I couldn't enhance your prompt. Please try again.", None
            
            # Prepare generation parameters
            generation_params = {
                'prompt': enhanced.enhanced_prompt,
                'negative_prompt': enhanced.negative_prompt,
                **enhanced.technical_params
            }
            
            # Build response
            response = f"🎨 **Generating image for:** {prompt}\n\n"
            response += f"**Enhanced prompt:** {enhanced.enhanced_prompt}\n"
            
            if enhanced.reasoning:
                response += f"**Changes made:** {enhanced.reasoning}\n"
            
            if enhanced.style_suggestions:
                response += f"**Style notes:** {', '.join(enhanced.style_suggestions)}\n"
            
            response += f"**Confidence:** {enhanced.confidence:.0%}\n\n"
            response += "⏳ Starting generation..."
            
            return response, {
                'action': 'generate',
                'params': generation_params,
                'enhanced_prompt': enhanced
            }
            
        except Exception as e:
            logger.error(f"Error handling generation request: {e}")
            return f"❌ Error processing generation request: {e}", None
    
    async def _suggest_generation(self, prompt: str, user_id: str) -> Tuple[str, Dict[str, Any]]:
        """Suggest image generation for ambiguous prompts"""
        try:
            # Enhance the prompt to see if it's viable
            enhanced = await self.prompt_enhancer.enhance_prompt(prompt)
            
            if not enhanced or enhanced.confidence < 0.4:
                return None, None
            
            # Build suggestion response
            response = f"💡 **I could generate an image for:** \"{prompt}\"\n\n"
            response += f"**Enhanced version:** {enhanced.enhanced_prompt}\n"
            response += f"**Confidence:** {enhanced.confidence:.0%}\n\n"
            response += "React with 🎨 to generate this image!"
            
            return response, {
                'action': 'suggest',
                'params': {
                    'prompt': enhanced.enhanced_prompt,
                    'negative_prompt': enhanced.negative_prompt,
                    **enhanced.technical_params
                },
                'enhanced_prompt': enhanced
            }
            
        except Exception as e:
            logger.error(f"Error suggesting generation: {e}")
            return None, None
    
    async def enhance_user_prompt(self, prompt: str, context: Optional[str] = None) -> Optional[EnhancedPrompt]:
        """Public method to enhance prompts"""
        return await self.prompt_enhancer.enhance_prompt(prompt, context)