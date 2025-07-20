# Content Classification System 📊

## Overview

The system uses a 161-category SQLite database to analyze and enhance prompts. All processing is local - no external API calls.

## Category Structure

### Subject Categories
```
subject/
├── person/
│   ├── man, woman, child, teenager, elderly
│   ├── figure/ → tall, short, athletic, slim, curvy, muscular
│   ├── hair/
│   │   ├── color/ → blonde, brunette, red_hair, black_hair, white_hair
│   │   ├── length/ → long_hair, short_hair, medium_hair, very_long_hair
│   │   └── style/ → straight, curly, wavy, braided, ponytail, twin_tails
│   ├── expression/ → smiling, serious, angry, sad, surprised, neutral
│   └── action/ → standing, sitting, running, walking, dancing, lying
├── clothing/
│   ├── upper_body/ → shirt, blouse, sweater, jacket, coat, tank_top
│   ├── lower_body/ → pants, shorts, skirt, dress, jeans
│   ├── underwear/ → bra, panties, boxers, briefs
│   ├── footwear/ → shoes, boots, sneakers, heels, sandals
│   └── accessories/ → hat, glasses, jewelry, watch, bag
└── animal/
    ├── domestic/ → cat, dog, horse, cow, sheep
    ├── wild/ → lion, tiger, elephant, wolf, bear
    └── fantasy/ → dragon, unicorn, phoenix
```

### Style Categories
```
style/
├── medium/ → photography, painting, digital_art, sketch, 3d_render
├── art_movement/ → impressionist, surrealist, cubist, renaissance, baroque
├── modern_style/ → cyberpunk, steampunk, art_deco, minimalist, vintage
├── quality/ → high_quality, detailed, masterpiece, professional, 4k, 8k
└── technique/ → oil_painting, watercolor, pencil_drawing, digital_painting
```

### Environment Categories
```
environment/
├── setting_type/ → indoor, outdoor
├── location/ → home, office, park, beach, forest, city, mountains
├── time_period/ → modern, medieval, victorian, futuristic, ancient
├── weather/ → sunny, rainy, cloudy, snowy, stormy
└── lighting/ → natural_light, dramatic_lighting, soft_lighting, neon, sunset
```

### Content Filter Categories
```
content_filter/
├── nsfw/
│   ├── nudity/ → topless, nude, naked, revealing
│   ├── sexual/ → erotic, sexual, intimate, seductive
│   └── suggestive/ → suggestive, provocative, sensual
└── violence/ → weapons, gore, fighting, blood, war
```

## How It Works

### 1. Prompt Analysis
```python
prompt = "a beautiful woman with long blonde hair wearing a red dress"

# Tokenize and clean
words = ["beautiful", "woman", "long", "blonde", "hair", "wearing", "red", "dress"]

# Match against database
matches = {
    "woman": "subject/person/woman",
    "blonde": "subject/person/hair/color/blonde", 
    "hair": "subject/person/hair",
    "dress": "subject/clothing/dress"
}
```

### 2. Category Detection
```python
categories_found = {
    "subject/person/woman": confidence=1.0,
    "subject/person/hair/color/blonde": confidence=1.0,
    "subject/clothing/dress": confidence=1.0
}

missing_categories = {
    "style": ["No style specified"],
    "quality": ["No quality tags"],
    "lighting": ["No lighting specified"]
}
```

### 3. Enhancement Suggestions
```python
suggestions = {
    "style": "photorealistic",
    "quality": "high quality, detailed",
    "lighting": "natural lighting",
    "enhancement": "professional photography"
}

enhanced_prompt = original + ", " + ", ".join(suggestions.values())
```

### 4. Safety Assessment
```python
nsfw_score = calculate_nsfw_content(categories_found)
safety_level = "safe" | "moderate" | "explicit"

if nsfw_score > threshold:
    action = "filter" | "warn" | "allow"
```

## Database Schema

### content_categories
```sql
CREATE TABLE content_categories (
    id INTEGER PRIMARY KEY,
    category_path TEXT NOT NULL UNIQUE,    -- "subject/person/hair/color"
    description TEXT,                      -- "Hair color variations"
    parent_id INTEGER,                     -- Parent category reference
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (parent_id) REFERENCES content_categories (id)
);
```

### content_words
```sql
CREATE TABLE content_words (
    id INTEGER PRIMARY KEY,
    word TEXT NOT NULL,                    -- "blonde"
    category_id INTEGER NOT NULL,          -- Reference to category
    confidence REAL DEFAULT 1.0,          -- Match confidence (0.0-1.0)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (category_id) REFERENCES content_categories (id),
    UNIQUE(word, category_id)
);
```

## API Usage

### MCP Tools

**analyze_prompt_content()**
```python
result = await analyze_prompt_content(
    prompt="anime girl with blue hair",
    negative_prompt="blurry"
)

# Returns:
{
    "categories_found": {
        "subject/person/woman": 0.9,
        "subject/person/hair/color/blue": 1.0,
        "style/medium/anime": 1.0
    },
    "missing_categories": ["quality", "lighting"],
    "suggestions": {
        "quality": "high quality, detailed",
        "lighting": "soft lighting"
    },
    "safety_assessment": {
        "safety_level": "safe",
        "nsfw_score": 0.1
    }
}
```

**enhanced_prompt_generation()**
```python
result = await enhanced_prompt_generation(
    prompt="cat sitting on table",
    apply_suggestions=True,
    safety_filter=True
)

# Returns:
{
    "original_prompt": "cat sitting on table",
    "enhanced_prompt": "cat sitting on table, photorealistic, high quality, detailed, natural lighting",
    "added_elements": ["photorealistic", "high quality", "detailed", "natural lighting"],
    "safety_level": "safe"
}
```

**get_content_categories()**
```python
# Get all categories
categories = await get_content_categories()

# Get specific category type
subject_categories = await get_content_categories(category_type="subject")
```

### Direct Database Access

**Search Content:**
```python
from modules.stable_diffusion.content_db import ContentDatabase

db = ContentDatabase()

# Analyze prompt
analysis = db.analyze_prompt("beautiful woman in red dress")

# Search words
words = db.search_words("hair")

# Get category hierarchy
categories = db.get_category_hierarchy("subject/person")
```

## Adding New Content

### Add New Category
```python
db = ContentDatabase()
db.add_category(
    category_path="subject/vehicle/motorcycle",
    description="Motorcycles and bikes",
    parent_path="subject/vehicle"
)
```

### Add New Words
```python
db.add_words_to_category([
    ("motorcycle", "subject/vehicle/motorcycle", 1.0),
    ("bike", "subject/vehicle/motorcycle", 0.9),
    ("harley", "subject/vehicle/motorcycle", 0.8)
])
```

### Bulk Import
```python
# Via SQL
INSERT INTO content_categories (category_path, description, parent_id)
VALUES ('subject/food', 'Food items', 
        (SELECT id FROM content_categories WHERE category_path = 'subject'));

INSERT INTO content_words (word, category_id, confidence)
VALUES ('pizza', (SELECT id FROM content_categories WHERE category_path = 'subject/food'), 1.0),
       ('burger', (SELECT id FROM content_categories WHERE category_path = 'subject/food'), 1.0);
```

## Configuration

### Content Filtering Levels
```bash
# Environment variables
CONTENT_FILTER_LEVEL=moderate     # safe, moderate, strict
NSFW_THRESHOLD=0.7               # 0.0-1.0 (lower = more strict)
AUTO_ENHANCE_PROMPTS=true        # Automatically enhance prompts
SAFETY_FILTER_ENABLED=true       # Enable safety filtering
```

### Enhancement Settings
```bash
# What to auto-add to prompts
AUTO_ADD_QUALITY=true            # Add quality tags
AUTO_ADD_STYLE=true              # Add style suggestions
AUTO_ADD_LIGHTING=true           # Add lighting suggestions
DEFAULT_STYLE=photorealistic     # Default style if none specified
```

## Performance

### Database Size
- **161 categories** organized hierarchically
- **~2000 words** mapped to categories
- **SQLite file size**: ~500KB
- **Analysis time**: <10ms per prompt

### Caching
- Category mappings cached in memory
- Word lookups use SQLite indexes
- No external API calls - all local processing

### Optimization
```python
# Pre-load common categories
db.cache_common_categories()

# Batch word lookups
words = ["cat", "dog", "mouse"]
results = db.batch_analyze_words(words)

# Use confidence thresholds
matches = db.find_matches(words, min_confidence=0.8)
```

## Examples

### Basic Analysis
```
Input: "cat"
Categories: subject/animal/domestic/cat
Suggestions: Add quality, style, lighting
Enhanced: "cat, photorealistic, high quality, detailed, natural lighting"
```

### Complex Analysis
```
Input: "anime girl with long blue hair in school uniform"
Categories:
- subject/person/woman (0.9)
- subject/person/hair/color/blue (1.0)
- subject/person/hair/length/long (1.0)
- subject/clothing/uniform (1.0)
- style/medium/anime (1.0)

Missing: lighting, quality enhancement
Enhanced: "anime girl with long blue hair in school uniform, high quality, detailed, soft lighting"
```

### NSFW Detection
```
Input: "topless woman on beach"
Categories:
- subject/person/woman (1.0)
- subject/clothing/topless (1.0) → content_filter/nsfw/nudity
- environment/location/beach (1.0)

Safety Level: explicit
Action: Filter or warn based on user settings
```

The content system provides intelligent prompt analysis and enhancement without any external dependencies.