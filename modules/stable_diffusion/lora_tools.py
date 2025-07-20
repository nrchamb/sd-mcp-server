#!/usr/bin/env python3
"""
LoRA management tools - only loaded when needed
"""

import json
from typing import Dict, Any, List

# Dependencies injected by lazy loader
lora_manager = None
sd_client = None

def set_dependencies(manager, client):
    """Set dependencies when module is loaded"""
    global lora_manager, sd_client
    lora_manager = manager
    sd_client = client

async def search_loras(query: str, limit: int = 10) -> str:
    """Search for LoRA models using enhanced caching"""
    try:
        # Use cached search for better performance
        results = await lora_manager.search_loras_cached(query, limit=limit)
        
        if not results:
            return json.dumps({
                "query": query,
                "results": [],
                "total_found": 0,
                "message": f"No LoRA models found matching '{query}'",
                "suggestions": [
                    "Try broader search terms",
                    "Check spelling and try synonyms", 
                    "Use get_all_loras() to see available LoRAs"
                ]
            })
        
        # Enhance results with usage information
        enhanced_results = []
        for lora in results:
            enhanced_results.append({
                "name": lora.name,
                "description": lora.description,
                "category": lora.category,
                "trigger_words": lora.trigger_words,
                "weight_suggestions": [0.6, 0.8, 1.0, 1.2],
                "usage_example": f"<lora:{lora.name}:0.8>",
                "filename": lora.filename,
                "weight": lora.weight
            })
        
        return json.dumps({
            "query": query,
            "results": enhanced_results,
            "total_found": len(results),
            "limit_applied": limit,
            "usage_tips": {
                "syntax": "<lora:name:weight>",
                "typical_weights": "0.6-1.2 range, 0.8 is common starting point",
                "multiple_loras": "You can use multiple LoRAs in one prompt"
            }
        }, indent=2)
        
    except Exception as e:
        return json.dumps({
            "error": f"LoRA search failed: {str(e)}",
            "query": query
        })

async def get_all_loras() -> str:
    """Get all available LoRA models"""
    try:
        all_loras = await lora_manager.get_all_loras()
        
        # Group by categories if available
        categories = {}
        uncategorized = []
        
        for lora in all_loras:
            category = lora.get("category", "").lower()
            if category:
                if category not in categories:
                    categories[category] = []
                categories[category].append(lora)
            else:
                uncategorized.append(lora)
        
        return json.dumps({
            "total_loras": len(all_loras),
            "categories": {
                **categories,
                **({"uncategorized": uncategorized} if uncategorized else {})
            },
            "category_summary": {cat: len(loras) for cat, loras in categories.items()},
            "usage_note": "Use search_loras() with specific terms for better results"
        }, indent=2)
        
    except Exception as e:
        return json.dumps({"error": f"Failed to get LoRAs: {str(e)}"})

async def get_lora_suggestions(prompt: str) -> str:
    """Get LoRA suggestions for a given prompt"""
    try:
        suggestions = await lora_manager.get_lora_suggestions(prompt)
        
        if not suggestions:
            return json.dumps({
                "prompt": prompt,
                "suggestions": [],
                "message": "No specific LoRA suggestions for this prompt",
                "general_tip": "Try searching for style-specific or character-specific LoRAs"
            })
        
        return json.dumps({
            "prompt": prompt,
            "suggestions": suggestions,
            "total_suggestions": len(suggestions),
            "next_steps": [
                "Review suggestions above",
                "Use search_loras() to find specific LoRAs",
                "Add to prompt using <lora:name:weight> syntax"
            ]
        }, indent=2)
        
    except Exception as e:
        return json.dumps({
            "error": f"Failed to get LoRA suggestions: {str(e)}",
            "prompt": prompt
        })

async def validate_lora_usage(prompt_with_loras: str) -> str:
    """Validate LoRA usage in a prompt"""
    try:
        validation = await lora_manager.validate_lora_usage(prompt_with_loras)
        
        return json.dumps({
            "prompt": prompt_with_loras,
            "validation": validation,
            "is_valid": validation.get("is_valid", False),
            "issues": validation.get("issues", []),
            "suggestions": validation.get("suggestions", []),
            "parsed_loras": validation.get("parsed_loras", [])
        }, indent=2)
        
    except Exception as e:
        return json.dumps({
            "error": f"LoRA validation failed: {str(e)}",
            "prompt": prompt_with_loras
        })

async def get_popular_loras(category: str = "", limit: int = 20) -> str:
    """Get popular/frequently used LoRA models"""
    try:
        popular = await lora_manager.get_popular_loras(category, limit)
        
        return json.dumps({
            "category": category or "all",
            "popular_loras": popular,
            "total_found": len(popular),
            "note": "Popularity based on usage frequency and ratings"
        }, indent=2)
        
    except Exception as e:
        return json.dumps({
            "error": f"Failed to get popular LoRAs: {str(e)}",
            "category": category
        })