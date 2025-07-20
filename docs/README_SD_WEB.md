# Stable Diffusion Web MCP Integration

## Overview

This MCP (Model Context Protocol) integration provides intelligent access to Stable Diffusion WebUI through a sophisticated LoRA management system, queue-based generation, and content-aware filtering. The system transforms raw SD WebUI API calls into LLM-friendly tools that provide targeted, actionable intelligence rather than overwhelming data dumps.

## Architecture

### Core Components

```
modules/stable_diffusion/
├── sd_client.py         # SD WebUI API client
├── lora_manager.py      # Intelligent LoRA analysis & database
├── queue_manager.py     # Job queuing & progress tracking  
├── uploader.py          # Image upload & management
├── models.py            # Pydantic data models
└── __init__.py          # Module exports
```

### Key Features

- **🧠 Intelligent LoRA Management**: Auto-categorization, training data analysis, smart prompt matching
- **📋 Queue System**: Priority-based job queuing with progress tracking
- **🔍 Smart Search**: Tag frequency analysis for relevant LoRA suggestions
- **🏷️ Content Detection**: NSFW filtering and content type classification
- **📊 LLM-Optimized**: Concise responses designed for 8B model coherence

## API Endpoints

### Model & Sampler Discovery

#### `get_sd_models_summary()`
Returns concise model summary grouped by categories instead of 51+ full objects.

**Example Response:**
```json
{
  "total_models": 51,
  "categories": {
    "Anime": [
      {"name": "<modelName>", "title": "<modelName>.safetensors"},
      {"name": "n<modelName>", "title": "<modelName>.safetensors"},
      {"name": "...", "title": "and 8 more"}
    ]
  },
  "summary": "51 models across 6 categories"
}
```

#### `search_sd_models(query, limit=5)`
Targeted model search by name.

#### `get_samplers_list()`
Simple list with recommended samplers instead of complex objects.

### LoRA Intelligence System

#### `get_lora_summary()`
**LLM-Friendly Summary** - Manages feeding a large Lora library to the model without overloading the context window.

**Example Response:**
```json
{
  "total_loras": 82,
  "categories": {
    "general": 32,
    "character": 21, 
    "realistic": 13,
    "concept": 8,
    "anime": 6,
    "style": 2
  },
  "top_trigger_words": [
    {"word": "blush", "count": 15},
    {"word": "1girl", "count": 13}
  ],
  "summary_text": "82 LoRAs available across 6 categories"
}
```

#### `suggest_loras_for_prompt(prompt, limit=5)`
**Intelligent Prompt Analysis** using training data frequency.

**Example:**
```python
# Input: "anime girl with cat ears"
# Output: Top 3 LoRAs with confidence scores and matching tags
[
  {
    "name": "animeStyleV4",
    "confidence": "high",
    "score": 0.744,
    "reason": "Strong match on tags: anime, 1girl",
    "category": "anime", 
    "key_triggers": ["anime style", "cat ears"],
    "recommended_weight": 1.0,
    "matching_tags": ["anime", "1girl", "cat_ears"]
  }
]
```

#### `browse_loras_by_category(category, limit=10)`
Browse LoRAs by auto-detected categories.

#### `search_loras_smart(query, max_results=5)`
Relevance-scored search with concise results.

### Image Generation

#### `generate_image(prompt, ...params)`
Direct image generation with full parameter control.

**Key Parameters:**
- `prompt`: Text description
- `negative_prompt`: What to avoid
- `steps`: Generation steps (default: 4)
- `width/height`: Image dimensions (1024x1024 default)
- `sampler_name`: Sampling method ("Euler" default)
- `cfg_scale`: Guidance scale
- `seed`: Reproducibility seed
- `output_path`: Save location

#### `enqueue_image_generation(prompt, ...params, priority=5)`
Queue-based generation for better resource management.

**Returns:**
```json
{
  "job_id": "deb4a1a5-cfc7-4b39-a171-d406b7330eb7",
  "status": "enqueued"
}
```

### Queue Management

#### `get_generation_progress(job_id?)`
- With `job_id`: Get specific job status
- Without: Get current SD progress

#### `get_queue_status()`
Overall queue statistics.

#### `cancel_generation_job(job_id)`
Cancel queued or running jobs.

#### `get_job_history(limit=50)`
Recent job history.

### Orchestration

#### `orchestrate_image_generation(prompt, style_preference="balanced")`
**Multi-step intelligent workflow:**

1. **Prompt Analysis** → Suggest relevant LoRAs
2. **LoRA Validation** → Check for conflicts  
3. **Weight Optimization** → Balance for style preference
4. **Queue Generation** → Enqueue with optimized parameters

**Example Response:**
```json
{
  "prompt": "anime girl with cat ears",
  "steps_completed": ["prompt_analysis", "lora_validation", "weight_optimization", "generation_queued"],
  "lora_suggestions": [...],
  "optimized_loras": [...],
  "job_id": "abc123...",
  "status": "completed"
}
```

## Database Schema

### LoRA Database (SQLite)

```sql
CREATE TABLE loras (
    name TEXT PRIMARY KEY,
    alias TEXT,
    path TEXT,
    filename TEXT,
    weight REAL DEFAULT 1.0,
    category TEXT DEFAULT 'general',
    description TEXT,
    trigger_words TEXT,           -- JSON array
    metadata TEXT,               -- JSON object with content_type, etc.
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Auto-Categorization Logic

**Categories:** anime, realistic, character, style, concept, general

**Detection Methods:**
1. **Name Pattern Analysis**: Keywords in LoRA names
2. **Tag Frequency Analysis**: When `ss_tag_frequency` available
3. **Training Data Heuristics**: Content type detection

### Content Safety

**NSFW Detection Pipeline:**
- Tag frequency analysis for explicit content
- Confidence scoring: safe, suggestive, nsfw
- Configurable thresholds for filtering

## Configuration

### Environment Variables

```bash
SD_BASE_URL=https://localhost:7860      # SD WebUI endpoint
IMAGE_OUT_PATH=/path/to/output            # Image save location  
UPLOAD_URL=https://your-domain.com/upload # Image upload endpoint
NSFW_FILTER=true                          # Enable content filtering
```

### MCP Configuration (mcp.json)

```json
{
  "mcpServers": {
    "SD_Web_MCP": {
      "command": "/Users/user/.local/bin/uv",
      "args": ["--directory", "/path/to/sd-mcp/", "run", "sd_main.py"],
      "env": {
        "SD_BASE_URL": "https://localhost:7860",
        "IMAGE_OUT_PATH": "/path/to/images/",
        "NSFW_FILTER": "true"
      },
      "timeout": 600000
    }
  }
}
```

## Usage Examples

### Basic Image Generation

```python
# Direct generation
result = await generate_image(
    prompt="anime girl, masterpiece, best quality",
    negative_prompt="lowres, bad anatomy",
    steps=20,
    width=1024,
    height=1024
)

# Parse results
images = json.loads(result)
for img in images:
    print(f"Generated: {img['path']}")
```

### Intelligent LoRA Workflow

```python
# 1. Get LoRA overview
summary = await get_lora_summary()
# Output: "82 LoRAs across 6 categories"

# 2. Smart suggestions
suggestions = await suggest_loras_for_prompt("cyberpunk portrait", 3)
# Output: Top 3 relevant LoRAs with confidence scores

# 3. Full orchestration
workflow = await orchestrate_image_generation("cyberpunk portrait", "strong")
# Output: Complete workflow with optimized LoRA selection
```

### Queue Management

```python
# Enqueue job
job_result = await enqueue_image_generation(
    prompt="fantasy landscape",
    priority=3
)
job_id = json.loads(job_result)["job_id"]

# Monitor progress  
progress = await get_generation_progress(job_id)
status = json.loads(progress)["status"]

# Check queue
queue_info = await get_queue_status()
```

## Performance Optimizations

### For 8B Models

1. **Chunked Responses**: Max 5-10 items per response
2. **Relevance Scoring**: Only return meaningful matches
3. **Confidence Levels**: Clear high/medium/low indicators
4. **Contextual Summaries**: "X items across Y categories" format

### Database Indexing

```sql
CREATE INDEX idx_category ON loras(category);
CREATE INDEX idx_trigger_words ON loras(trigger_words);
```

### Caching Strategy

- **Model/Sampler Lists**: Cache for 1 hour
- **LoRA Database**: Sync on-demand or scheduled
- **Generated Images**: Cleanup after 7 days

## Content Safety & Compliance

### NSFW Detection

**Three-Tier System:**
- **Safe**: General audience content
- **Suggestive**: Mature themes, artistic nudity  
- **NSFW**: Explicit sexual content

**Detection Methods:**
1. Tag frequency analysis from training data
2. Filename pattern matching
3. Content classification models (future)

### Upload Pipeline

**Planned CloudFlare Integration:**
```
Generation → NSFW Check → Content Filter → CloudFlare Upload → Proxied URL
```

**Safety Measures:**
- Pre-upload content scanning
- Automatic NSFW flagging
- Rate limiting per user/IP
- Audit logging for generated content

## Troubleshooting

### Common Issues

**Empty LoRA Database:**
```bash
# Force sync
python -c "
import asyncio
from modules.stable_diffusion import LoRAManager, SDClient
async def sync():
    lm = LoRAManager(SDClient())
    count = await lm.sync_with_sd_api()
    print(f'Synced {count} LoRAs')
asyncio.run(sync())
"
```

**SD WebUI Connection Issues:**
- Verify `SD_BASE_URL` is accessible
- Check SD WebUI API is enabled
- Confirm CORS settings allow requests

**Performance Issues:**
- Increase `timeout` in mcp.json for large generations
- Use `enqueue_image_generation` instead of direct calls
- Monitor queue status to prevent overload

### Debug Mode

```python
# Enable detailed logging
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Future Enhancements

### Planned Features

1. **Model Context Protocol v2** compatibility
2. **Advanced LoRA Recommendation Engine** with ML scoring
3. **Real-time Generation Streaming** 
4. **Batch Processing** for multiple prompts
5. **Custom Training Pipeline** integration
6. **Advanced Content Filtering** with computer vision
7. **Multi-User Queue Management**
8. **Generation History & Analytics**

### CloudFlare Integration Roadmap

1. **Phase 1**: Basic image upload proxy
2. **Phase 2**: CDN optimization & caching
3. **Phase 3**: Edge-based content filtering  
4. **Phase 4**: Real-time generation streaming

## Security Considerations

### Current Implementation
- Local database storage
- Environment-based configuration
- Basic NSFW detection

### Production Recommendations
- Encrypt sensitive LoRA metadata
- Implement user authentication
- Add rate limiting and abuse prevention
- Content audit trails
- Regular security updates

---

**Version**: 1.0  
**Last Updated**: 2025-07-14  
**Compatibility**: SD WebUI 1.x, MCP Protocol 1.x+
