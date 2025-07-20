# LoRA Intelligence System 🎨

## Overview

The LoRA system provides intelligent LoRA selection, conflict detection, and prompt enhancement for Stable Diffusion generation. All data stored in local SQLite database.

## Database Structure

### loras Table
```sql
CREATE TABLE loras (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,            -- "anime_style_v2"
    filename TEXT NOT NULL,               -- "anime_style_v2.safetensors"
    description TEXT,                     -- "High quality anime art style"
    tags TEXT,                           -- "anime,style,art,cartoon"
    category TEXT,                       -- "style", "character", "concept"
    strength_min REAL DEFAULT 0.5,       -- Minimum recommended strength
    strength_max REAL DEFAULT 1.0,       -- Maximum recommended strength  
    strength_default REAL DEFAULT 0.8,   -- Default strength
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Sample LoRA Data
```sql
-- Style LoRAs
INSERT INTO loras (name, filename, description, tags, category, strength_min, strength_max, strength_default)
VALUES 
('anime_style', 'anime_style.safetensors', 'Anime art style', 'anime,style,art', 'style', 0.6, 1.0, 0.8),
('realistic_portrait', 'realistic_portrait.safetensors', 'Realistic portrait style', 'realistic,portrait,photography', 'style', 0.4, 0.9, 0.7),
('fantasy_art', 'fantasy_art.safetensors', 'Fantasy art style', 'fantasy,art,digital', 'style', 0.5, 1.0, 0.8);

-- Character LoRAs  
INSERT INTO loras (name, filename, description, tags, category, strength_min, strength_max, strength_default)
VALUES
('character_miku', 'miku_v3.safetensors', 'Hatsune Miku character', 'miku,vocaloid,character,anime', 'character', 0.7, 1.0, 0.9),
('character_zelda', 'zelda_botw.safetensors', 'Princess Zelda BOTW', 'zelda,nintendo,character,fantasy', 'character', 0.6, 0.9, 0.8);

-- Concept LoRAs
INSERT INTO loras (name, filename, description, tags, category, strength_min, strength_max, strength_default)
VALUES
('cyberpunk_city', 'cyberpunk_env.safetensors', 'Cyberpunk environment', 'cyberpunk,city,neon,futuristic', 'concept', 0.5, 0.8, 0.6),
('magical_effects', 'magic_fx.safetensors', 'Magical spell effects', 'magic,effects,fantasy,spells', 'concept', 0.4, 0.7, 0.5);
```

## LoRA Categories

### Style LoRAs
- **Purpose**: Overall art style and rendering
- **Examples**: anime_style, realistic_portrait, oil_painting
- **Strength**: Usually 0.6-1.0
- **Conflicts**: Multiple style LoRAs can conflict

### Character LoRAs
- **Purpose**: Specific characters or people
- **Examples**: character_miku, celebrity_name, fictional_character
- **Strength**: Usually 0.7-1.0 for strong character features
- **Conflicts**: Multiple character LoRAs usually conflict

### Concept LoRAs
- **Purpose**: Specific concepts, objects, or environments
- **Examples**: cyberpunk_city, magical_effects, specific_clothing
- **Strength**: Usually 0.4-0.8
- **Conflicts**: Usually compatible with other concepts

### Pose/Action LoRAs
- **Purpose**: Specific poses or actions
- **Examples**: sitting_pose, dancing, specific_hand_positions
- **Strength**: Usually 0.5-0.8
- **Conflicts**: Multiple pose LoRAs can conflict

## MCP Tools

### get_lora_summary()
```python
result = await get_lora_summary()

# Returns:
{
    "total_loras": 25,
    "categories": {
        "style": 8,
        "character": 10,
        "concept": 5,
        "pose": 2
    },
    "popular_loras": [
        {"name": "anime_style", "category": "style", "usage_count": 150},
        {"name": "realistic_portrait", "category": "style", "usage_count": 120}
    ]
}
```

### search_loras_smart()
```python
result = await search_loras_smart(
    query="anime girl",
    max_results=5
)

# Returns:
{
    "matches": [
        {
            "name": "anime_style",
            "filename": "anime_style.safetensors",
            "description": "High quality anime art style",
            "category": "style",
            "strength_default": 0.8,
            "relevance_score": 0.95,
            "match_reason": "Style match for 'anime'"
        },
        {
            "name": "character_miku", 
            "filename": "miku_v3.safetensors",
            "description": "Hatsune Miku character",
            "category": "character",
            "strength_default": 0.9,
            "relevance_score": 0.75,
            "match_reason": "Character match for 'anime girl'"
        }
    ],
    "suggestions": [
        "Consider anime_style LoRA for overall style",
        "Add specific character LoRA if you want a particular character"
    ]
}
```

### suggest_loras_for_prompt()
```python
result = await suggest_loras_for_prompt(
    prompt="cyberpunk street with neon lights",
    limit=3
)

# Returns:
{
    "suggested_loras": [
        {
            "name": "cyberpunk_city",
            "strength": 0.7,
            "reason": "Matches 'cyberpunk' and 'neon' keywords",
            "category": "concept"
        },
        {
            "name": "neon_effects",
            "strength": 0.5, 
            "reason": "Enhances neon lighting effects",
            "category": "concept"
        }
    ],
    "prompt_analysis": {
        "detected_style": "cyberpunk",
        "detected_elements": ["street", "neon", "lights"],
        "recommended_combination": "cyberpunk_city:0.7, neon_effects:0.5"
    }
}
```

### validate_lora_combination()
```python
result = await validate_lora_combination([
    {"name": "anime_style", "strength": 0.8},
    {"name": "realistic_portrait", "strength": 0.7},
    {"name": "character_miku", "strength": 0.9}
])

# Returns:
{
    "valid": False,
    "conflicts": [
        {
            "loras": ["anime_style", "realistic_portrait"],
            "conflict_type": "style_conflict",
            "severity": "high",
            "explanation": "Anime and realistic styles conflict"
        }
    ],
    "suggestions": [
        "Remove either anime_style or realistic_portrait",
        "Consider using anime_style with character_miku for consistent style"
    ],
    "recommended_combination": [
        {"name": "anime_style", "strength": 0.8},
        {"name": "character_miku", "strength": 0.9}
    ]
}
```

## Smart LoRA Selection

### Keyword Matching
```python
# Prompt analysis
prompt = "beautiful anime girl with long hair"
keywords = ["anime", "girl", "beautiful", "long", "hair"]

# LoRA matching
matches = {
    "anime_style": ["anime"] → score: 1.0,
    "character_miku": ["anime", "girl"] → score: 0.8,
    "long_hair_style": ["long", "hair"] → score: 0.6
}
```

### Category Scoring
```python
# Style detection
if "anime" in prompt:
    style_preference = "anime"
    boost_anime_loras(+0.3)

if "realistic" in prompt:
    style_preference = "realistic" 
    boost_realistic_loras(+0.3)

# Character detection
if specific_character_mentioned:
    boost_character_loras(+0.5)
```

### Conflict Detection
```python
conflicts = {
    "style_conflicts": [
        ["anime_style", "realistic_portrait"],
        ["cartoon_style", "photorealistic"]
    ],
    "character_conflicts": [
        ["character_miku", "character_zelda"]  # Multiple characters
    ],
    "strength_conflicts": [
        # High strength LoRAs that don't work well together
        {"loras": ["strong_style_a", "strong_style_b"], "max_combined_strength": 1.2}
    ]
}
```

## LoRA Management

### Adding New LoRAs
```python
# Via database
INSERT INTO loras (name, filename, description, tags, category, strength_min, strength_max, strength_default)
VALUES ('new_style', 'new_style.safetensors', 'New art style', 'style,new,art', 'style', 0.5, 1.0, 0.7);

# Via MCP tool
result = await add_lora_to_database(
    name="new_style",
    filename="new_style.safetensors", 
    description="New art style",
    tags="style,new,art",
    category="style",
    strength_default=0.7
)
```

### LoRA Discovery
```python
# Scan SD WebUI for LoRA files
discovered_loras = scan_webui_loras()

# Auto-add missing LoRAs
for lora in discovered_loras:
    if not lora_exists_in_db(lora.filename):
        add_lora_placeholder(lora)
```

### Strength Optimization
```python
# Analyze generation results to optimize strengths
def optimize_lora_strength(lora_name, prompt, generation_quality):
    current_strength = get_lora_strength(lora_name)
    
    if generation_quality < 0.7:
        # Reduce strength if quality is poor
        new_strength = max(current_strength - 0.1, 0.3)
    elif generation_quality > 0.9:
        # Can potentially increase strength
        new_strength = min(current_strength + 0.05, 1.0)
    
    update_lora_strength(lora_name, new_strength)
```

## Integration with Content System

### Combined Analysis
```python
# Analyze prompt with both content and LoRA systems
prompt = "anime girl in school uniform"

# Content analysis
content_categories = analyze_content(prompt)
# → subject/person/woman, subject/clothing/uniform, style/medium/anime

# LoRA analysis  
suggested_loras = suggest_loras_from_content(content_categories)
# → anime_style (from style/medium/anime), school_uniform_lora (from clothing/uniform)

# Combined enhancement
enhanced_prompt = prompt + ", " + format_lora_string(suggested_loras)
# → "anime girl in school uniform <lora:anime_style:0.8> <lora:school_uniform:0.6>"
```

### Smart Recommendations
```python
def get_smart_lora_recommendations(prompt, content_analysis):
    recommendations = []
    
    # Style LoRAs from content analysis
    if "style/medium/anime" in content_analysis:
        recommendations.append(("anime_style", 0.8, "Matches detected anime style"))
    
    # Character LoRAs from detected characters
    if "character_specific" in content_analysis:
        recommendations.append(("character_lora", 0.9, "Matches detected character"))
    
    # Concept LoRAs from environment/objects
    if "environment/cyberpunk" in content_analysis:
        recommendations.append(("cyberpunk_city", 0.6, "Enhances cyberpunk environment"))
    
    return validate_lora_combination(recommendations)
```

## Performance Optimization

### Database Indexing
```sql
-- Index for fast searches
CREATE INDEX idx_loras_tags ON loras(tags);
CREATE INDEX idx_loras_category ON loras(category);
CREATE INDEX idx_loras_name ON loras(name);
```

### Caching Strategy
```python
# Cache frequently used LoRAs
lora_cache = {
    "popular_loras": load_popular_loras(),
    "category_mappings": load_category_mappings(),
    "conflict_rules": load_conflict_rules()
}

# Cache search results
search_cache = LRUCache(maxsize=100)
```

### Batch Operations
```python
# Batch LoRA analysis for multiple prompts
prompts = ["anime girl", "realistic portrait", "cyberpunk city"]
batch_results = batch_analyze_loras(prompts)

# Batch validation
lora_combinations = [combination1, combination2, combination3]
batch_validation = batch_validate_combinations(lora_combinations)
```

## Configuration

### LoRA Settings
```bash
# Environment variables
LORA_AUTO_SUGGEST=true              # Auto-suggest LoRAs for prompts
LORA_CONFLICT_CHECK=true            # Check for LoRA conflicts
LORA_DEFAULT_STRENGTH=0.8           # Default LoRA strength
MAX_LORAS_PER_PROMPT=3              # Maximum LoRAs per generation
```

### Quality Settings
```bash
LORA_QUALITY_THRESHOLD=0.7          # Minimum quality for recommendations
LORA_RELEVANCE_THRESHOLD=0.5        # Minimum relevance for suggestions
ENABLE_LORA_LEARNING=false          # Learn from generation results
```

The LoRA system provides intelligent LoRA selection and management for optimal Stable Diffusion results.