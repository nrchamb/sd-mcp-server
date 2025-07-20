"""
MCP Tools for Content Guide Management
Provides tools for managing the granular content database and prompt processing
"""

import json
from typing import Dict, List, Any, Optional
from .content_db import ContentDatabase, CategoryType

class ContentGuideManager:
    """Manager for content guides with MCP tool integration"""
    
    def __init__(self, db_path: str = "content_mapping.db"):
        self.db = ContentDatabase(db_path)
        self.safety_level = "safe"  # Can be configured
    
    def analyze_prompt_detailed(self, prompt: str) -> Dict[str, Any]:
        """Detailed prompt analysis with enhancement suggestions"""
        analysis = self.db.analyze_prompt(prompt)
        
        # Add enhancement suggestions
        suggestions = self._generate_enhancement_suggestions(analysis)
        analysis["enhancement_suggestions"] = suggestions
        
        # Add safety assessment
        safety = self._assess_safety(analysis)
        analysis["safety_assessment"] = safety
        
        return analysis
    
    def _generate_enhancement_suggestions(self, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate style and quality enhancement suggestions"""
        suggestions = []
        categories_found = set(analysis["categories_found"])
        
        # Check if we have style categories
        has_style = any("style/" in cat for cat in categories_found)
        if not has_style:
            suggestions.append({
                "type": "style_missing",
                "suggestion": "Consider adding a style (e.g., 'photorealistic', 'anime', 'artistic')",
                "examples": ["photorealistic", "anime style", "oil painting", "digital art"]
            })
        
        # Check if we have quality descriptors
        has_quality = any("style/quality" in cat for cat in categories_found)
        if not has_quality:
            suggestions.append({
                "type": "quality_missing", 
                "suggestion": "Consider adding quality descriptors",
                "examples": ["high quality", "detailed", "masterpiece", "professional"]
            })
        
        # Check if we have lighting
        has_lighting = any("environment/lighting" in cat for cat in categories_found)
        if not has_lighting:
            suggestions.append({
                "type": "lighting_missing",
                "suggestion": "Consider specifying lighting",
                "examples": ["dramatic lighting", "soft lighting", "natural light", "neon lighting"]
            })
        
        # Check for person without expression
        has_person = any("subject/person" in cat for cat in categories_found)
        has_expression = any("expression" in cat for cat in categories_found)
        if has_person and not has_expression:
            suggestions.append({
                "type": "expression_missing",
                "suggestion": "Consider adding facial expression",
                "examples": ["smiling", "serious", "surprised", "mysterious"]
            })
        
        return suggestions
    
    def _assess_safety(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Assess content safety based on flags"""
        content_flags = analysis.get("content_flags", [])
        
        safety_levels = {
            "safe": 0,
            "moderate": 0, 
            "strict": 0
        }
        
        # Count flags by severity
        for flag in content_flags:
            if "nsfw" in flag["category"]:
                safety_levels["strict"] += 1
                safety_levels["moderate"] += 1
            elif "violence" in flag["category"]:
                safety_levels["moderate"] += 1
        
        # Determine overall safety
        if safety_levels["strict"] > 0:
            level = "requires_strict_filtering"
        elif safety_levels["moderate"] > 0:
            level = "requires_moderate_filtering"
        else:
            level = "safe"
        
        return {
            "level": level,
            "flags_count": len(content_flags),
            "recommendations": self._get_safety_recommendations(content_flags)
        }
    
    def _get_safety_recommendations(self, flags: List[Dict]) -> List[str]:
        """Get safety recommendations based on flags"""
        recommendations = []
        
        flag_categories = set(flag["category"] for flag in flags)
        
        if any("nsfw" in cat for cat in flag_categories):
            recommendations.append("Consider removing explicit content terms")
            recommendations.append("Add 'safe for work' or 'appropriate' to prompt")
        
        if any("violence" in cat for cat in flag_categories):
            recommendations.append("Consider removing violent content terms")
            recommendations.append("Focus on peaceful or positive themes")
        
        return recommendations
    
    def get_category_tree(self, category_type: Optional[str] = None) -> Dict[str, Any]:
        """Get hierarchical category tree"""
        query = """
        SELECT id, name, parent_id, category_type, description, full_path, enabled
        FROM categories
        """
        params = []
        
        if category_type:
            query += " WHERE category_type = ?"
            params.append(category_type)
        
        query += " ORDER BY full_path"
        
        cursor = self.db.conn.execute(query, params)
        categories = [dict(row) for row in cursor.fetchall()]
        
        # Build tree structure
        tree = {}
        for cat in categories:
            path_parts = cat["full_path"].split("/")
            current = tree
            
            for part in path_parts:
                if part not in current:
                    current[part] = {"children": {}, "info": None}
                current = current[part]["children"]
            
            # Set info at the leaf
            current_node = tree
            for part in path_parts[:-1]:
                current_node = current_node[part]["children"]
            current_node[path_parts[-1]]["info"] = cat
        
        return tree
    
    def add_word_to_category(self, word: str, category_path: str, 
                           confidence: float = 1.0) -> Dict[str, Any]:
        """Add word to category mapping"""
        success = self.db.add_word_mapping(word, category_path, confidence, "user_added")
        
        return {
            "success": success,
            "word": word,
            "category": category_path,
            "confidence": confidence
        }
    
    def get_word_info(self, word: str) -> Dict[str, Any]:
        """Get detailed information about a word"""
        categories = self.db.get_word_categories(word)
        
        return {
            "word": word,
            "categories": categories,
            "category_count": len(categories),
            "primary_category": categories[0]["full_path"] if categories else None
        }
    
    def suggest_categories_for_word(self, word: str) -> List[Dict[str, Any]]:
        """Suggest potential categories for uncategorized word"""
        suggestions = []
        word_lower = word.lower()
        
        # Simple heuristic-based suggestions
        # This could be enhanced with ML in the future
        
        # Check for common patterns
        if any(term in word_lower for term in ["color", "red", "blue", "green", "yellow", "black", "white"]):
            suggestions.append({
                "category": "style/color",
                "confidence": 0.8,
                "reason": "Color-related term"
            })
        
        if any(term in word_lower for term in ["beautiful", "gorgeous", "pretty", "handsome"]):
            suggestions.append({
                "category": "style/quality",
                "confidence": 0.7,
                "reason": "Aesthetic descriptor"
            })
        
        if word_lower.endswith("ing"):
            suggestions.append({
                "category": "subject/person/action",
                "confidence": 0.6,
                "reason": "Verb ending suggests action"
            })
        
        if any(term in word_lower for term in ["room", "house", "building", "place"]):
            suggestions.append({
                "category": "environment/location",
                "confidence": 0.8,
                "reason": "Location-related term"
            })
        
        return suggestions
    
    def get_usage_statistics(self) -> Dict[str, Any]:
        """Get database usage statistics"""
        # Word count by category
        cursor = self.db.conn.execute("""
        SELECT c.category_type, COUNT(DISTINCT wc.word_id) as word_count
        FROM categories c
        JOIN word_categories wc ON c.id = wc.category_id
        WHERE wc.enabled = 1
        GROUP BY c.category_type
        """)
        
        category_stats = {row['category_type']: row['word_count'] for row in cursor.fetchall()}
        
        # Total words
        cursor = self.db.conn.execute("SELECT COUNT(*) FROM words")
        total_words = cursor.fetchone()[0]
        
        # Total categories
        cursor = self.db.conn.execute("SELECT COUNT(*) FROM categories WHERE enabled = 1")
        total_categories = cursor.fetchone()[0]
        
        # Most common categories
        cursor = self.db.conn.execute("""
        SELECT c.full_path, COUNT(wc.word_id) as word_count
        FROM categories c
        JOIN word_categories wc ON c.id = wc.category_id
        WHERE wc.enabled = 1
        GROUP BY c.id, c.full_path
        ORDER BY word_count DESC
        LIMIT 10
        """)
        
        top_categories = [{"category": row['full_path'], "word_count": row['word_count']} 
                         for row in cursor.fetchall()]
        
        return {
            "total_words": total_words,
            "total_categories": total_categories,
            "words_by_category_type": category_stats,
            "top_categories": top_categories
        }
    
    def export_config(self) -> Dict[str, Any]:
        """Export current configuration as JSON"""
        # Get all categories
        cursor = self.db.conn.execute("""
        SELECT full_path, category_type, description, enabled FROM categories
        ORDER BY full_path
        """)
        categories = [dict(row) for row in cursor.fetchall()]
        
        # Get all word mappings
        cursor = self.db.conn.execute("""
        SELECT w.word, c.full_path, wc.confidence, wc.source, wc.enabled
        FROM words w
        JOIN word_categories wc ON w.id = wc.word_id
        JOIN categories c ON wc.category_id = c.id
        ORDER BY w.word, wc.confidence DESC
        """)
        word_mappings = [dict(row) for row in cursor.fetchall()]
        
        return {
            "version": "1.0",
            "categories": categories,
            "word_mappings": word_mappings,
            "export_timestamp": "NOW()"
        }
    
    def close(self):
        """Close database connection"""
        self.db.close()