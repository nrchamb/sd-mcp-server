"""
Enhanced LoRA parsing with improved word/phrase matching
"""

import re
import json
from typing import Dict, List, Set, Any, Tuple
from dataclasses import dataclass

@dataclass
class LoRAMatch:
    """Represents a LoRA match with detailed scoring"""
    name: str
    category: str
    match_type: str
    matching_tags: List[str]
    score: float
    confidence: str
    reason: str

class EnhancedLoRAParser:
    """Enhanced LoRA parser with better tokenization and matching"""
    
    def __init__(self):
        # Technical photography terms
        self.technical_terms = {
            'bokeh', 'dof', 'depth of field', 'macro', 'telephoto', 'wide-angle', 
            'portrait', 'landscape', 'close-up', 'panoramic', 'fisheye', 'tilt-shift',
            'long exposure', 'hdr', 'bracketing', 'focus stacking', 'panning'
        }
        
        # Art and style terms
        self.style_terms = {
            'anime', 'realistic', 'cartoon', 'photorealistic', 'artistic', 'painted',
            'watercolor', 'oil painting', 'acrylic', 'digital art', 'concept art',
            'impressionist', 'abstract', 'minimalist', 'surreal', 'pop art',
            'sketch', 'drawing', 'illustration', 'manga', 'comic book'
        }
        
        # Subject terms
        self.subject_terms = {
            'woman', 'man', 'girl', 'boy', 'person', 'character', 'people',
            'animal', 'cat', 'dog', 'bird', 'horse', 'dragon', 'creature',
            'car', 'vehicle', 'motorcycle', 'plane', 'ship', 'robot', 'mecha',
            'building', 'house', 'castle', 'city', 'landscape', 'forest', 'mountain',
            'flower', 'tree', 'plant', 'nature', 'ocean', 'sky', 'cloud'
        }
        
        # Environment/setting terms
        self.environment_terms = {
            'indoor', 'outdoor', 'studio', 'natural light', 'artificial light',
            'sunset', 'sunrise', 'night', 'day', 'evening', 'morning',
            'cyberpunk', 'steampunk', 'fantasy', 'sci-fi', 'medieval',
            'modern', 'futuristic', 'vintage', 'retro', 'contemporary'
        }
        
        # Synonyms and related terms
        self.synonyms = {
            'beautiful': ['pretty', 'gorgeous', 'stunning', 'attractive', 'lovely'],
            'detailed': ['intricate', 'complex', 'elaborate', 'fine', 'precise'],
            'realistic': ['photorealistic', 'lifelike', 'natural', 'authentic'],
            'anime': ['manga', 'japanese animation', 'cartoon', 'animated'],
            'portrait': ['headshot', 'face', 'bust', 'profile'],
            'landscape': ['scenery', 'vista', 'panorama', 'countryside']
        }
    
    def enhanced_tokenization(self, prompt: str) -> Dict[str, Any]:
        """Enhanced tokenization that preserves phrases and context"""
        
        # Clean and normalize prompt
        cleaned_prompt = re.sub(r'[,\(\)\[\]{}]', ' ', prompt.lower())
        cleaned_prompt = re.sub(r'\s+', ' ', cleaned_prompt).strip()
        
        # Split into words
        words = cleaned_prompt.split()
        
        # Generate phrases (2-4 word combinations)
        phrases = []
        for length in range(2, min(5, len(words) + 1)):
            for i in range(len(words) - length + 1):
                phrase = ' '.join(words[i:i+length])
                phrases.append(phrase)
        
        # Categorize words
        technical_terms = [w for w in words if w in self.technical_terms]
        style_terms = [w for w in words if w in self.style_terms]
        subject_terms = [w for w in words if w in self.subject_terms]
        environment_terms = [w for w in words if w in self.environment_terms]
        
        # Find multi-word technical terms
        prompt_lower = cleaned_prompt
        technical_phrases = [term for term in self.technical_terms if ' ' in term and term in prompt_lower]
        style_phrases = [term for term in self.style_terms if ' ' in term and term in prompt_lower]
        
        return {
            "original_prompt": prompt,
            "cleaned_prompt": cleaned_prompt,
            "words": words,
            "phrases": phrases,
            "technical_terms": technical_terms + technical_phrases,
            "style_terms": style_terms + style_phrases,
            "subject_terms": subject_terms,
            "environment_terms": environment_terms,
            "word_count": len(words),
            "key_concepts": self._extract_key_concepts(words, phrases)
        }
    
    def _extract_key_concepts(self, words: List[str], phrases: List[str]) -> List[str]:
        """Extract key concepts from words and phrases"""
        concepts = []
        
        # Important single words
        important_words = [w for w in words if len(w) > 3 and w not in {
            'with', 'and', 'the', 'a', 'an', 'in', 'on', 'at', 'by', 'for', 'of', 'to'
        }]
        concepts.extend(important_words)
        
        # Important phrases (2-3 words)
        important_phrases = [p for p in phrases if len(p.split()) <= 3]
        concepts.extend(important_phrases)
        
        return concepts
    
    def advanced_tag_matching(self, prompt_tokens: Dict[str, Any], lora_tags: List[str], 
                             lora_metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """Advanced matching algorithm with semantic understanding"""
        
        matches = {
            "exact_matches": [],
            "phrase_matches": [],
            "partial_matches": [],
            "semantic_matches": [],
            "synonym_matches": [],
            "concept_matches": [],
            "total_score": 0.0,
            "weighted_score": 0.0
        }
        
        prompt_words = set(prompt_tokens["words"])
        prompt_phrases = set(prompt_tokens["phrases"])
        key_concepts = set(prompt_tokens["key_concepts"])
        
        # Process each LoRA tag
        for tag in lora_tags:
            tag_lower = tag.lower().replace("_", " ").replace("-", " ")
            tag_words = set(tag_lower.split())
            
            # 1. Exact word matches (highest priority)
            if tag_lower in prompt_words:
                matches["exact_matches"].append(tag)
                matches["total_score"] += 3.0
                matches["weighted_score"] += 3.0
            
            # 2. Phrase matches (high priority)
            elif tag_lower in prompt_phrases:
                matches["phrase_matches"].append(tag)
                matches["total_score"] += 2.5
                matches["weighted_score"] += 2.5
            
            # 3. Concept matches (high priority)
            elif tag_lower in key_concepts:
                matches["concept_matches"].append(tag)
                matches["total_score"] += 2.0
                matches["weighted_score"] += 2.0
            
            # 4. Partial word matches (medium priority)
            elif tag_words.intersection(prompt_words):
                matches["partial_matches"].append(tag)
                overlap_score = len(tag_words.intersection(prompt_words)) / len(tag_words)
                matches["total_score"] += 1.5 * overlap_score
                matches["weighted_score"] += 1.5 * overlap_score
            
            # 5. Semantic matches (medium priority)
            elif self._is_semantic_match(tag_lower, prompt_tokens):
                matches["semantic_matches"].append(tag)
                matches["total_score"] += 1.0
                matches["weighted_score"] += 1.0
            
            # 6. Synonym matches (lower priority)
            elif self._is_synonym_match(tag_lower, prompt_words):
                matches["synonym_matches"].append(tag)
                matches["total_score"] += 0.8
                matches["weighted_score"] += 0.8
        
        # Normalize scores
        total_possible = len(lora_tags) * 3.0  # Max score per tag
        if total_possible > 0:
            matches["normalized_score"] = matches["total_score"] / total_possible
            matches["weighted_normalized_score"] = matches["weighted_score"] / total_possible
        else:
            matches["normalized_score"] = 0.0
            matches["weighted_normalized_score"] = 0.0
        
        # Calculate confidence
        if matches["normalized_score"] > 0.4:
            matches["confidence"] = "high"
        elif matches["normalized_score"] > 0.2:
            matches["confidence"] = "medium"
        else:
            matches["confidence"] = "low"
        
        return matches
    
    def _is_semantic_match(self, tag: str, prompt_tokens: Dict[str, Any]) -> bool:
        """Check if tag semantically matches prompt content"""
        
        # Check if tag belongs to same semantic category
        if tag in self.technical_terms and prompt_tokens["technical_terms"]:
            return True
        if tag in self.style_terms and prompt_tokens["style_terms"]:
            return True
        if tag in self.subject_terms and prompt_tokens["subject_terms"]:
            return True
        if tag in self.environment_terms and prompt_tokens["environment_terms"]:
            return True
        
        return False
    
    def _is_synonym_match(self, tag: str, prompt_words: Set[str]) -> bool:
        """Check if tag matches any synonyms of prompt words"""
        
        for word in prompt_words:
            if word in self.synonyms:
                if tag in self.synonyms[word]:
                    return True
            # Check reverse
            for key, synonyms in self.synonyms.items():
                if word in synonyms and tag == key:
                    return True
        
        return False
    
    def suggest_loras_enhanced(self, prompt: str, lora_data: List[Dict[str, Any]], 
                              limit: int = 5) -> List[LoRAMatch]:
        """Enhanced LoRA suggestion with improved parsing"""
        
        # Enhanced tokenization
        prompt_tokens = self.enhanced_tokenization(prompt)
        
        lora_matches = []
        
        for lora in lora_data:
            name = lora.get("name", "unknown")
            category = lora.get("category", "general")
            
            # Get tags from various sources
            tags = []
            
            # Trigger words
            if lora.get("trigger_words"):
                try:
                    trigger_words = json.loads(lora["trigger_words"]) if isinstance(lora["trigger_words"], str) else lora["trigger_words"]
                    tags.extend(trigger_words)
                except (json.JSONDecodeError, TypeError):
                    pass
            
            # Tags from metadata
            if lora.get("metadata"):
                try:
                    metadata = json.loads(lora["metadata"]) if isinstance(lora["metadata"], str) else lora["metadata"]
                    if "ss_tag_frequency" in metadata:
                        tag_freq = metadata["ss_tag_frequency"]
                        if isinstance(tag_freq, dict):
                            tags.extend(tag_freq.keys())
                except (json.JSONDecodeError, TypeError):
                    pass
            
            # Include name and description as tags
            tags.append(name)
            if lora.get("description"):
                tags.extend(lora["description"].split())
            
            # Perform advanced matching
            if tags:
                match_result = self.advanced_tag_matching(prompt_tokens, tags, lora.get("metadata"))
                
                if match_result["total_score"] > 0.1:  # Only include meaningful matches
                    # Create detailed match object
                    matching_tags = (
                        match_result["exact_matches"] + 
                        match_result["phrase_matches"] + 
                        match_result["concept_matches"]
                    )
                    
                    # Determine primary match type
                    if match_result["exact_matches"]:
                        match_type = "exact"
                    elif match_result["phrase_matches"]:
                        match_type = "phrase"
                    elif match_result["concept_matches"]:
                        match_type = "concept"
                    else:
                        match_type = "partial"
                    
                    # Create reason
                    reason = f"Matches {len(matching_tags)} key terms"
                    if matching_tags:
                        reason += f": {', '.join(matching_tags[:3])}"
                        if len(matching_tags) > 3:
                            reason += f" and {len(matching_tags) - 3} more"
                    
                    lora_match = LoRAMatch(
                        name=name,
                        category=category,
                        match_type=match_type,
                        matching_tags=matching_tags,
                        score=match_result["weighted_normalized_score"],
                        confidence=match_result["confidence"],
                        reason=reason
                    )
                    
                    lora_matches.append(lora_match)
        
        # Sort by score and return top matches
        lora_matches.sort(key=lambda x: x.score, reverse=True)
        return lora_matches[:limit]