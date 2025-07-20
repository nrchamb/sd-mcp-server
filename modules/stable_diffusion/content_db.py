"""
Granular Content Database System for Stable Diffusion MCP Server
SQLite-based relational mapping for prompt taxonomy and word classification
"""

import sqlite3
import json
import os
from typing import Dict, List, Set, Tuple, Optional, Any
from pathlib import Path
from dataclasses import dataclass
from enum import Enum
import re

# POS tagging for meaningful word filtering
try:
    import nltk
    from nltk.tokenize import word_tokenize
    from nltk.tag import pos_tag
    NLTK_AVAILABLE = True
except ImportError:
    NLTK_AVAILABLE = False

class CategoryType(Enum):
    SUBJECT = "subject"
    STYLE = "style"
    ENVIRONMENT = "environment"
    SURREAL = "surreal"
    MOTIF = "motif"
    CONTENT_FILTER = "content_filter"

@dataclass
class WordMapping:
    word: str
    category_path: str
    confidence: float
    source: str  # "manual", "auto", "user_added"
    enabled: bool = True

@dataclass
class Category:
    id: int
    name: str
    parent_id: Optional[int]
    category_type: CategoryType
    description: str
    enabled: bool
    full_path: str

class ContentDatabase:
    """SQLite-based content classification and mapping system"""
    
    def __init__(self, db_path: str = "content_mapping.db"):
        self.db_path = db_path
        self.conn = None
        self._init_database()
        self._populate_initial_data()
    
    def _init_database(self):
        """Initialize SQLite database with schema"""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        
        # Enable foreign keys
        self.conn.execute("PRAGMA foreign_keys = ON")
        
        # Create tables
        self.conn.executescript("""
        -- Categories table (hierarchical structure)
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            parent_id INTEGER REFERENCES categories(id),
            category_type TEXT NOT NULL,
            description TEXT,
            enabled BOOLEAN DEFAULT 1,
            full_path TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        -- Words table
        CREATE TABLE IF NOT EXISTS words (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            word TEXT UNIQUE NOT NULL,
            normalized TEXT NOT NULL, -- lowercase, cleaned version
            frequency INTEGER DEFAULT 0,
            first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        -- Word-Category mappings (many-to-many)
        CREATE TABLE IF NOT EXISTS word_categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            word_id INTEGER REFERENCES words(id),
            category_id INTEGER REFERENCES categories(id),
            confidence REAL DEFAULT 1.0,
            source TEXT DEFAULT 'manual', -- manual, auto, user_added
            enabled BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(word_id, category_id)
        );
        
        -- Style enhancement rules
        CREATE TABLE IF NOT EXISTS style_enhancements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id INTEGER REFERENCES categories(id),
            positive_additions TEXT, -- JSON array
            negative_additions TEXT, -- JSON array
            parameter_overrides TEXT, -- JSON object
            priority INTEGER DEFAULT 0,
            enabled BOOLEAN DEFAULT 1
        );
        
        -- Content filter rules
        CREATE TABLE IF NOT EXISTS content_filters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id INTEGER REFERENCES categories(id),
            filter_type TEXT, -- block, warn, require
            severity TEXT, -- low, medium, high, critical
            action TEXT, -- block_generation, censor, warn_user
            enabled BOOLEAN DEFAULT 1
        );
        
        -- Usage analytics
        CREATE TABLE IF NOT EXISTS usage_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            word_id INTEGER REFERENCES words(id),
            category_id INTEGER REFERENCES categories(id),
            prompt_hash TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            generation_success BOOLEAN
        );
        
        -- Indexes for performance
        CREATE INDEX IF NOT EXISTS idx_words_normalized ON words(normalized);
        CREATE INDEX IF NOT EXISTS idx_categories_type ON categories(category_type);
        CREATE INDEX IF NOT EXISTS idx_categories_path ON categories(full_path);
        CREATE INDEX IF NOT EXISTS idx_word_categories_enabled ON word_categories(enabled);
        CREATE INDEX IF NOT EXISTS idx_usage_timestamp ON usage_stats(timestamp);
        """)
        
        self.conn.commit()
    
    def _populate_initial_data(self):
        """Populate with initial granular categories"""
        # Check if already populated
        cursor = self.conn.execute("SELECT COUNT(*) FROM categories")
        if cursor.fetchone()[0] > 0:
            return
        
        # Extremely granular category structure
        categories = [
            # SUBJECT CATEGORIES
            ("subject", None, CategoryType.SUBJECT, "Main subject matter"),
            
            # Person subcategories
            ("person", "subject", CategoryType.SUBJECT, "Human subjects"),
            ("man", "person", CategoryType.SUBJECT, "Adult male"),
            ("woman", "person", CategoryType.SUBJECT, "Adult female"),
            ("child", "person", CategoryType.SUBJECT, "Children"),
            ("boy", "child", CategoryType.SUBJECT, "Male child"),
            ("girl", "child", CategoryType.SUBJECT, "Female child"),
            ("elderly", "person", CategoryType.SUBJECT, "Elderly person"),
            ("teenager", "person", CategoryType.SUBJECT, "Teenage person"),
            
            # Figure/Body subcategories
            ("figure", "person", CategoryType.SUBJECT, "Body type and build"),
            ("tall", "figure", CategoryType.SUBJECT, "Tall height"),
            ("short", "figure", CategoryType.SUBJECT, "Short height"),
            ("athletic", "figure", CategoryType.SUBJECT, "Athletic build"),
            ("slim", "figure", CategoryType.SUBJECT, "Slim build"),
            ("curvy", "figure", CategoryType.SUBJECT, "Curvy figure"),
            ("muscular", "figure", CategoryType.SUBJECT, "Muscular build"),
            ("petite", "figure", CategoryType.SUBJECT, "Petite frame"),
            
            # Hair subcategories
            ("hair", "person", CategoryType.SUBJECT, "Hair characteristics"),
            ("hair_length", "hair", CategoryType.SUBJECT, "Hair length"),
            ("long_hair", "hair_length", CategoryType.SUBJECT, "Long hair"),
            ("short_hair", "hair_length", CategoryType.SUBJECT, "Short hair"),
            ("medium_hair", "hair_length", CategoryType.SUBJECT, "Medium length hair"),
            ("hair_color", "hair", CategoryType.SUBJECT, "Hair color"),
            ("blonde", "hair_color", CategoryType.SUBJECT, "Blonde hair"),
            ("brunette", "hair_color", CategoryType.SUBJECT, "Brown hair"),
            ("black_hair", "hair_color", CategoryType.SUBJECT, "Black hair"),
            ("red_hair", "hair_color", CategoryType.SUBJECT, "Red hair"),
            ("hair_style", "hair", CategoryType.SUBJECT, "Hair styling"),
            ("straight", "hair_style", CategoryType.SUBJECT, "Straight hair"),
            ("curly", "hair_style", CategoryType.SUBJECT, "Curly hair"),
            ("wavy", "hair_style", CategoryType.SUBJECT, "Wavy hair"),
            ("braided", "hair_style", CategoryType.SUBJECT, "Braided hair"),
            ("ponytail", "hair_style", CategoryType.SUBJECT, "Ponytail"),
            
            # Expression subcategories
            ("expression", "person", CategoryType.SUBJECT, "Facial expressions"),
            ("smiling", "expression", CategoryType.SUBJECT, "Smiling expression"),
            ("serious", "expression", CategoryType.SUBJECT, "Serious expression"),
            ("angry", "expression", CategoryType.SUBJECT, "Angry expression"),
            ("sad", "expression", CategoryType.SUBJECT, "Sad expression"),
            ("surprised", "expression", CategoryType.SUBJECT, "Surprised expression"),
            ("laughing", "expression", CategoryType.SUBJECT, "Laughing expression"),
            ("crying", "expression", CategoryType.SUBJECT, "Crying expression"),
            
            # Actions subcategories
            ("action", "person", CategoryType.SUBJECT, "Person activities"),
            ("standing", "action", CategoryType.SUBJECT, "Standing pose"),
            ("sitting", "action", CategoryType.SUBJECT, "Sitting pose"),
            ("running", "action", CategoryType.SUBJECT, "Running action"),
            ("walking", "action", CategoryType.SUBJECT, "Walking action"),
            ("dancing", "action", CategoryType.SUBJECT, "Dancing action"),
            ("jumping", "action", CategoryType.SUBJECT, "Jumping action"),
            ("lying", "action", CategoryType.SUBJECT, "Lying down"),
            
            # CLOTHING CATEGORIES
            ("clothing", "subject", CategoryType.SUBJECT, "Clothing and attire"),
            
            # Upper body clothing
            ("upper_body", "clothing", CategoryType.SUBJECT, "Upper body clothing"),
            ("shirt", "upper_body", CategoryType.SUBJECT, "Shirts"),
            ("t_shirt", "shirt", CategoryType.SUBJECT, "T-shirt"),
            ("dress_shirt", "shirt", CategoryType.SUBJECT, "Dress shirt"),
            ("blouse", "upper_body", CategoryType.SUBJECT, "Blouse"),
            ("sweater", "upper_body", CategoryType.SUBJECT, "Sweater"),
            ("jacket", "upper_body", CategoryType.SUBJECT, "Jacket"),
            ("coat", "upper_body", CategoryType.SUBJECT, "Coat"),
            
            # Lower body clothing
            ("lower_body", "clothing", CategoryType.SUBJECT, "Lower body clothing"),
            ("pants", "lower_body", CategoryType.SUBJECT, "Pants"),
            ("jeans", "pants", CategoryType.SUBJECT, "Jeans"),
            ("trousers", "pants", CategoryType.SUBJECT, "Formal trousers"),
            ("shorts", "lower_body", CategoryType.SUBJECT, "Shorts"),
            ("skirt", "lower_body", CategoryType.SUBJECT, "Skirt"),
            ("mini_skirt", "skirt", CategoryType.SUBJECT, "Mini skirt"),
            ("long_skirt", "skirt", CategoryType.SUBJECT, "Long skirt"),
            
            # Dresses
            ("dress", "clothing", CategoryType.SUBJECT, "Dresses"),
            ("casual_dress", "dress", CategoryType.SUBJECT, "Casual dress"),
            ("formal_dress", "dress", CategoryType.SUBJECT, "Formal dress"),
            ("evening_dress", "dress", CategoryType.SUBJECT, "Evening dress"),
            
            # Underwear
            ("underwear", "clothing", CategoryType.SUBJECT, "Undergarments"),
            ("bra", "underwear", CategoryType.SUBJECT, "Bra"),
            ("panties", "underwear", CategoryType.SUBJECT, "Panties"),
            ("boxers", "underwear", CategoryType.SUBJECT, "Boxer shorts"),
            ("briefs", "underwear", CategoryType.SUBJECT, "Brief underwear"),
            
            # Footwear
            ("footwear", "clothing", CategoryType.SUBJECT, "Shoes and footwear"),
            ("shoes", "footwear", CategoryType.SUBJECT, "Regular shoes"),
            ("boots", "footwear", CategoryType.SUBJECT, "Boots"),
            ("sneakers", "footwear", CategoryType.SUBJECT, "Sneakers"),
            ("heels", "footwear", CategoryType.SUBJECT, "High heels"),
            ("sandals", "footwear", CategoryType.SUBJECT, "Sandals"),
            
            # STYLE CATEGORIES
            ("style", None, CategoryType.STYLE, "Artistic and visual styles"),
            
            # Medium
            ("medium", "style", CategoryType.STYLE, "Artistic medium"),
            ("photography", "medium", CategoryType.STYLE, "Photography"),
            ("painting", "medium", CategoryType.STYLE, "Painting"),
            ("digital_art", "medium", CategoryType.STYLE, "Digital artwork"),
            ("sketch", "medium", CategoryType.STYLE, "Sketch or drawing"),
            ("sculpture", "medium", CategoryType.STYLE, "Sculpture"),
            
            # Artistic movements
            ("art_movement", "style", CategoryType.STYLE, "Artistic movements"),
            ("impressionist", "art_movement", CategoryType.STYLE, "Impressionist style"),
            ("surrealist", "art_movement", CategoryType.STYLE, "Surrealist style"),
            ("cubist", "art_movement", CategoryType.STYLE, "Cubist style"),
            ("renaissance", "art_movement", CategoryType.STYLE, "Renaissance style"),
            ("baroque", "art_movement", CategoryType.STYLE, "Baroque style"),
            
            # Modern styles
            ("modern_style", "style", CategoryType.STYLE, "Modern art styles"),
            ("cyberpunk", "modern_style", CategoryType.STYLE, "Cyberpunk aesthetic"),
            ("steampunk", "modern_style", CategoryType.STYLE, "Steampunk aesthetic"),
            ("art_deco", "modern_style", CategoryType.STYLE, "Art Deco style"),
            ("minimalist", "modern_style", CategoryType.STYLE, "Minimalist style"),
            ("gothic", "modern_style", CategoryType.STYLE, "Gothic style"),
            
            # Quality descriptors
            ("quality", "style", CategoryType.STYLE, "Quality and detail"),
            ("high_quality", "quality", CategoryType.STYLE, "High quality"),
            ("detailed", "quality", CategoryType.STYLE, "Highly detailed"),
            ("masterpiece", "quality", CategoryType.STYLE, "Masterpiece quality"),
            ("professional", "quality", CategoryType.STYLE, "Professional quality"),
            
            # ENVIRONMENT CATEGORIES
            ("environment", None, CategoryType.ENVIRONMENT, "Settings and environments"),
            
            # Indoor/Outdoor
            ("setting_type", "environment", CategoryType.ENVIRONMENT, "Indoor vs outdoor"),
            ("indoor", "setting_type", CategoryType.ENVIRONMENT, "Indoor setting"),
            ("outdoor", "setting_type", CategoryType.ENVIRONMENT, "Outdoor setting"),
            
            # Specific locations
            ("location", "environment", CategoryType.ENVIRONMENT, "Specific locations"),
            ("home", "indoor", CategoryType.ENVIRONMENT, "Home setting"),
            ("office", "indoor", CategoryType.ENVIRONMENT, "Office setting"),
            ("restaurant", "indoor", CategoryType.ENVIRONMENT, "Restaurant"),
            ("school", "indoor", CategoryType.ENVIRONMENT, "School setting"),
            ("park", "outdoor", CategoryType.ENVIRONMENT, "Park setting"),
            ("beach", "outdoor", CategoryType.ENVIRONMENT, "Beach setting"),
            ("forest", "outdoor", CategoryType.ENVIRONMENT, "Forest setting"),
            ("city", "outdoor", CategoryType.ENVIRONMENT, "Urban setting"),
            
            # Time periods
            ("time_period", "environment", CategoryType.ENVIRONMENT, "Historical periods"),
            ("modern", "time_period", CategoryType.ENVIRONMENT, "Modern day"),
            ("medieval", "time_period", CategoryType.ENVIRONMENT, "Medieval period"),
            ("victorian", "time_period", CategoryType.ENVIRONMENT, "Victorian era"),
            ("futuristic", "time_period", CategoryType.ENVIRONMENT, "Future setting"),
            ("ancient", "time_period", CategoryType.ENVIRONMENT, "Ancient times"),
            
            # Lighting
            ("lighting", "environment", CategoryType.ENVIRONMENT, "Lighting conditions"),
            ("natural_light", "lighting", CategoryType.ENVIRONMENT, "Natural lighting"),
            ("artificial_light", "lighting", CategoryType.ENVIRONMENT, "Artificial lighting"),
            ("dramatic_lighting", "lighting", CategoryType.ENVIRONMENT, "Dramatic lighting"),
            ("soft_lighting", "lighting", CategoryType.ENVIRONMENT, "Soft lighting"),
            ("neon", "lighting", CategoryType.ENVIRONMENT, "Neon lighting"),
            
            # SURREAL CATEGORIES
            ("surreal", None, CategoryType.SURREAL, "Surreal and abstract elements"),
            
            # Distortions
            ("distortion", "surreal", CategoryType.SURREAL, "Visual distortions"),
            ("melting", "distortion", CategoryType.SURREAL, "Melting effect"),
            ("twisted", "distortion", CategoryType.SURREAL, "Twisted forms"),
            ("fragmented", "distortion", CategoryType.SURREAL, "Fragmented imagery"),
            ("stretched", "distortion", CategoryType.SURREAL, "Stretched proportions"),
            
            # Impossible elements
            ("impossible", "surreal", CategoryType.SURREAL, "Impossible imagery"),
            ("floating", "impossible", CategoryType.SURREAL, "Floating objects"),
            ("inverted", "impossible", CategoryType.SURREAL, "Inverted reality"),
            ("recursive", "impossible", CategoryType.SURREAL, "Recursive patterns"),
            
            # MOTIF CATEGORIES
            ("motif", None, CategoryType.MOTIF, "Themes and symbolic elements"),
            
            # Mood
            ("mood", "motif", CategoryType.MOTIF, "Emotional mood"),
            ("dark", "mood", CategoryType.MOTIF, "Dark mood"),
            ("cheerful", "mood", CategoryType.MOTIF, "Cheerful mood"),
            ("mysterious", "mood", CategoryType.MOTIF, "Mysterious mood"),
            ("epic", "mood", CategoryType.MOTIF, "Epic mood"),
            ("romantic", "mood", CategoryType.MOTIF, "Romantic mood"),
            
            # Themes
            ("theme", "motif", CategoryType.MOTIF, "Thematic elements"),
            ("love", "theme", CategoryType.MOTIF, "Love theme"),
            ("war", "theme", CategoryType.MOTIF, "War theme"),
            ("nature", "theme", CategoryType.MOTIF, "Nature theme"),
            ("technology", "theme", CategoryType.MOTIF, "Technology theme"),
            
            # CONTENT FILTER CATEGORIES
            ("content_filter", None, CategoryType.CONTENT_FILTER, "Content filtering"),
            
            # NSFW categories
            ("nsfw", "content_filter", CategoryType.CONTENT_FILTER, "NSFW content"),
            ("nudity", "nsfw", CategoryType.CONTENT_FILTER, "Nudity"),
            ("sexual", "nsfw", CategoryType.CONTENT_FILTER, "Sexual content"),
            ("suggestive", "nsfw", CategoryType.CONTENT_FILTER, "Suggestive content"),
            
            # Violence categories
            ("violence", "content_filter", CategoryType.CONTENT_FILTER, "Violent content"),
            ("weapons", "violence", CategoryType.CONTENT_FILTER, "Weapons"),
            ("gore", "violence", CategoryType.CONTENT_FILTER, "Gore"),
            ("fighting", "violence", CategoryType.CONTENT_FILTER, "Fighting"),
        ]
        
        # Insert categories and build path mapping
        category_ids = {}
        
        for name, parent_name, cat_type, description in categories:
            parent_id = category_ids.get(parent_name) if parent_name else None
            
            cursor = self.conn.execute("""
                INSERT INTO categories (name, parent_id, category_type, description)
                VALUES (?, ?, ?, ?)
            """, (name, parent_id, cat_type.value, description))
            
            category_ids[name] = cursor.lastrowid
        
        # Update full_path for all categories
        self._update_category_paths()
        
        # Load initial word mappings
        self._load_initial_word_mappings()
        
        self.conn.commit()
    
    def _update_category_paths(self):
        """Update full_path for all categories"""
        def get_path(category_id, visited=None):
            if visited is None:
                visited = set()
            
            if category_id in visited:
                return ""  # Prevent infinite recursion
            
            visited.add(category_id)
            
            cursor = self.conn.execute("""
                SELECT name, parent_id FROM categories WHERE id = ?
            """, (category_id,))
            
            row = cursor.fetchone()
            if not row:
                return ""
            
            name, parent_id = row['name'], row['parent_id']
            
            if parent_id:
                parent_path = get_path(parent_id, visited.copy())
                return f"{parent_path}/{name}" if parent_path else name
            else:
                return name
        
        # Get all categories
        cursor = self.conn.execute("SELECT id FROM categories")
        category_ids = [row['id'] for row in cursor.fetchall()]
        
        # Update paths
        for cat_id in category_ids:
            path = get_path(cat_id)
            self.conn.execute("""
                UPDATE categories SET full_path = ? WHERE id = ?
            """, (path, cat_id))
    
    def _load_initial_word_mappings(self):
        """Load essential word-category mappings"""
        # Essential meaningful words using actual category paths
        mappings = [
            # Person types
            ("woman", "subject/person/woman", 1.0),
            ("man", "subject/person/man", 1.0),
            ("lady", "subject/person/woman", 0.9),
            ("girl", "subject/person/child/girl", 1.0),
            ("boy", "subject/person/child/boy", 1.0),
            
            # Hair descriptors
            ("hair", "subject/person/hair", 1.0),
            ("long", "subject/person/hair/hair_length/long_hair", 0.8),
            ("short", "subject/person/hair/hair_length/short_hair", 0.8),
            ("blonde", "subject/person/hair/hair_color/blonde", 1.0),
            ("brunette", "subject/person/hair/hair_color/brunette", 1.0),
            
            # Quality descriptors
            ("beautiful", "style/quality/high_quality", 0.8),
            ("elegant", "style/quality/high_quality", 0.8),
            ("detailed", "style/quality/detailed", 1.0),
            ("professional", "style/quality/professional", 1.0),
            ("masterpiece", "style/quality/masterpiece", 1.0),
            
            # Actions
            ("sitting", "subject/person/action/sitting", 1.0),
            ("walking", "subject/person/action/walking", 1.0),
            ("standing", "subject/person/action/standing", 1.0),
            ("running", "subject/person/action/running", 1.0),
            ("dancing", "subject/person/action/dancing", 1.0),
            
            # Clothing
            ("dress", "subject/clothing/dress", 1.0),
            ("wearing", "subject/person/action", 0.6),  # General action
            
            # Locations
            ("park", "environment/setting_type/outdoor/park", 1.0),
            ("beach", "environment/setting_type/outdoor/beach", 1.0),
            ("forest", "environment/setting_type/outdoor/forest", 1.0),
            ("city", "environment/setting_type/outdoor/city", 1.0),
            ("home", "environment/setting_type/indoor/home", 1.0),
            
            # Time/Age descriptors
            ("old", "subject/person/elderly", 0.7),
            ("ancient", "environment/time_period/ancient", 1.0),
            ("modern", "environment/time_period/modern", 1.0),
            ("futuristic", "environment/time_period/futuristic", 1.0),
            
            # Image types and mediums
            ("photo", "style/medium/photography", 1.0),
            ("painting", "style/medium/painting", 1.0),
            ("sketch", "style/medium/sketch", 1.0),
            ("digital", "style/medium/digital_art", 1.0),
            
            # Common prompt words
            ("portrait", "style/medium/photography", 0.7),  # Often used for photo portraits
            ("image", "style/medium/digital_art", 0.5),     # Generic digital content
            ("create", "style/medium/digital_art", 0.3),    # Generic creation term
            ("generate", "style/medium/digital_art", 0.3),  # Generic generation term
            
            # Art styles
            ("gothic", "style/modern_style/gothic", 1.0),
            ("cyberpunk", "style/modern_style/cyberpunk", 1.0),
            ("steampunk", "style/modern_style/steampunk", 1.0),
            ("minimalist", "style/modern_style/minimalist", 1.0),
            
            # Common words mapped to closest available categories
            ("cat", "subject", 0.5),  # Generic subject since no animal category exists
            ("dog", "subject", 0.5),  # Generic subject since no animal category exists
            ("table", "environment/setting_type/indoor", 0.4),  # Indoor furniture
            ("sunset", "environment", 0.6),  # Environmental element
            ("ocean", "environment", 0.6),  # Environmental element
            ("red", "style", 0.4),  # Color as style element
            ("blue", "style", 0.4),  # Color as style element
            ("green", "style", 0.4),  # Color as style element
            ("black", "style", 0.4),  # Color as style element
            ("white", "style", 0.4),  # Color as style element
        ]
        
        # Check if already loaded
        cursor = self.conn.execute("SELECT COUNT(*) FROM word_categories")
        if cursor.fetchone()[0] > 0:
            return
        
        for word, category_path, confidence in mappings:
            self.add_word_mapping(word, category_path, confidence, "initial")
    
    def add_word_mapping(self, word: str, category_path: str, 
                        confidence: float = 1.0, source: str = "manual") -> bool:
        """Add or update word-category mapping"""
        try:
            # Get or create word
            word_id = self._get_or_create_word(word)
            
            # Get category ID
            category_id = self._get_category_by_path(category_path)
            if not category_id:
                return False
            
            # Insert or update mapping
            self.conn.execute("""
                INSERT OR REPLACE INTO word_categories 
                (word_id, category_id, confidence, source)
                VALUES (?, ?, ?, ?)
            """, (word_id, category_id, confidence, source))
            
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error adding word mapping: {e}")
            return False
    
    def _get_or_create_word(self, word: str) -> int:
        """Get existing word ID or create new word"""
        normalized = word.lower().strip()
        
        cursor = self.conn.execute("""
            SELECT id FROM words WHERE normalized = ?
        """, (normalized,))
        
        row = cursor.fetchone()
        if row:
            return row['id']
        
        # Create new word
        cursor = self.conn.execute("""
            INSERT INTO words (word, normalized) VALUES (?, ?)
        """, (word, normalized))
        
        return cursor.lastrowid
    
    def _get_category_by_path(self, path: str) -> Optional[int]:
        """Get category ID by full path"""
        cursor = self.conn.execute("""
            SELECT id FROM categories WHERE full_path = ?
        """, (path,))
        
        row = cursor.fetchone()
        return row['id'] if row else None
    
    def get_word_categories(self, word: str) -> List[Dict[str, Any]]:
        """Get all categories for a word"""
        normalized = word.lower().strip()
        
        cursor = self.conn.execute("""
            SELECT c.full_path, c.category_type, wc.confidence, wc.source, wc.enabled
            FROM words w
            JOIN word_categories wc ON w.id = wc.word_id
            JOIN categories c ON wc.category_id = c.id
            WHERE w.normalized = ? AND wc.enabled = 1
            ORDER BY wc.confidence DESC
        """, (normalized,))
        
        return [dict(row) for row in cursor.fetchall()]
    
    def _filter_meaningful_words(self, prompt: str) -> List[str]:
        """
        Filter words to only include meaningful parts of speech:
        - Nouns (NN, NNS, NNP, NNPS)
        - Adjectives (JJ, JJR, JJS) 
        - Adverbs (RB, RBR, RBS)
        - Verbs (VB, VBD, VBG, VBN, VBP, VBZ)
        
        Filters out articles, prepositions, pronouns, and other filler words.
        """
        if not NLTK_AVAILABLE:
            # Fallback to basic regex if NLTK not available
            return re.findall(r'\b\w+\b', prompt.lower())
        
        try:
            # Download required NLTK data if not present
            try:
                nltk.data.find('tokenizers/punkt_tab')
            except LookupError:
                nltk.download('punkt_tab', quiet=True)
            
            try:
                nltk.data.find('taggers/averaged_perceptron_tagger_eng')
            except LookupError:
                nltk.download('averaged_perceptron_tagger_eng', quiet=True)
            
            # Tokenize and tag parts of speech
            tokens = word_tokenize(prompt.lower())
            pos_tags = pos_tag(tokens)
            
            # Define meaningful POS tags
            meaningful_tags = {
                # Nouns
                'NN', 'NNS', 'NNP', 'NNPS',
                # Adjectives  
                'JJ', 'JJR', 'JJS',
                # Adverbs
                'RB', 'RBR', 'RBS',
                # Verbs
                'VB', 'VBD', 'VBG', 'VBN', 'VBP', 'VBZ'
            }
            
            # Filter to only meaningful words
            meaningful_words = [
                word for word, pos in pos_tags 
                if pos in meaningful_tags and len(word) > 1 and word.isalpha()
            ]
            
            return meaningful_words
            
        except Exception as e:
            # Fallback to basic regex if NLTK processing fails
            print(f"Warning: NLTK processing failed ({e}), using basic tokenization")
            return re.findall(r'\b\w+\b', prompt.lower())
    
    def analyze_prompt(self, prompt: str) -> Dict[str, Any]:
        """Analyze prompt and return categorized words (meaningful words only)"""
        # Filter to only meaningful words (nouns, adjectives, adverbs, verbs)
        words = self._filter_meaningful_words(prompt)
        
        result = {
            "total_words": len(words),
            "categorized_words": {},
            "uncategorized_words": [],
            "categories_found": set(),
            "content_flags": [],
            "filtered_words": words  # Include filtered words for debugging
        }
        
        for word in words:
            categories = self.get_word_categories(word)
            if categories:
                result["categorized_words"][word] = categories
                for cat in categories:
                    result["categories_found"].add(cat["full_path"])
                    # Check for content filter flags
                    if cat["category_type"] == CategoryType.CONTENT_FILTER.value:
                        result["content_flags"].append({
                            "word": word,
                            "category": cat["full_path"],
                            "confidence": cat["confidence"]
                        })
            else:
                result["uncategorized_words"].append(word)
        
        result["categories_found"] = list(result["categories_found"])
        return result
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            self.conn = None
