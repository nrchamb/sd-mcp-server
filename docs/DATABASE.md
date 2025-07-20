# Database Structure 🗄️

## Overview

The system uses 6 SQLite databases storing data in plain text. All databases are created by `scripts/init_databases.py`.

## Database Files

### `discord_llm.db` - Conversations & Personalities

**conversations**
```sql
CREATE TABLE conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    context_key TEXT NOT NULL,              -- Guild:Channel:Thread:User identifier  
    user_id TEXT NOT NULL,                  -- Discord user ID
    role TEXT NOT NULL,                     -- 'user' or 'assistant'
    content TEXT NOT NULL,                  -- Message content
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    personality_name TEXT DEFAULT 'default' -- Personality used for this message
);
```

**personalities**
```sql
CREATE TABLE personalities (
    name TEXT PRIMARY KEY,                  -- Internal name (e.g., 'uwu')
    display_name TEXT NOT NULL,             -- Display name (e.g., 'UwU Bot')
    system_prompt TEXT NOT NULL,           -- LLM system prompt
    image_injection_prompt TEXT,           -- Special prompt for image generation
    description TEXT,                      -- User-facing description
    emoji TEXT,                           -- Discord emoji
    category TEXT DEFAULT 'chat',         -- 'chat' or other categories
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**user_personalities**
```sql
CREATE TABLE user_personalities (
    user_id TEXT PRIMARY KEY,              -- Discord user ID
    personality_name TEXT NOT NULL,        -- Current personality
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (personality_name) REFERENCES personalities (name)
);
```

**admin_actions**
```sql
CREATE TABLE admin_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    admin_id TEXT NOT NULL,                -- Admin user ID
    target_user_id TEXT NOT NULL,          -- Target user ID
    action_type TEXT NOT NULL,             -- 'timeout', 'suspend', 'lock_personality'
    reason TEXT,                          -- Action reason
    duration_minutes INTEGER,             -- For timeouts
    metadata TEXT,                        -- JSON metadata
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### `discord_users.db` - Discord User Management

**discord_users**
```sql
CREATE TABLE discord_users (
    discord_id TEXT PRIMARY KEY,           -- Discord user ID
    username TEXT NOT NULL,               -- Discord username
    discriminator TEXT,                   -- Discord discriminator (legacy)
    avatar_url TEXT,                      -- Avatar URL
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**user_folders**
```sql
CREATE TABLE user_folders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    discord_id TEXT NOT NULL,             -- Discord user ID
    folder_name TEXT NOT NULL,            -- Folder name
    chevereto_album_id TEXT,              -- Chevereto album ID
    description TEXT,                     -- Folder description
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (discord_id) REFERENCES discord_users (discord_id),
    UNIQUE(discord_id, folder_name)
);
```

### `chevereto_users.db` - Image Hosting Users

**chevereto_users**
```sql
CREATE TABLE chevereto_users (
    user_id TEXT PRIMARY KEY,              -- Discord ID or username
    api_key TEXT NOT NULL,                -- Chevereto API key (PLAIN TEXT)
    username TEXT,                        -- Chevereto username
    default_album_id TEXT,                -- Default album
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**personal_api_keys**
```sql
CREATE TABLE personal_api_keys (
    discord_id TEXT PRIMARY KEY,           -- Discord user ID
    api_key TEXT NOT NULL,                -- Personal API key (PLAIN TEXT)
    username TEXT,                        -- Chevereto username
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### `lora_database.db` - LoRA Management

**loras**
```sql
CREATE TABLE loras (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,            -- LoRA name
    filename TEXT NOT NULL,               -- File name
    description TEXT,                     -- Description
    tags TEXT,                           -- Comma-separated tags
    category TEXT,                       -- Category (style, character, etc.)
    strength_min REAL DEFAULT 0.5,       -- Minimum strength
    strength_max REAL DEFAULT 1.0,       -- Maximum strength  
    strength_default REAL DEFAULT 0.8,   -- Default strength
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### `content_mapping.db` - Content Classification

**content_categories**
```sql
CREATE TABLE content_categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_path TEXT NOT NULL UNIQUE,   -- e.g., 'subject/person/hair/color'
    description TEXT,                     -- Category description
    parent_id INTEGER,                    -- Parent category ID
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (parent_id) REFERENCES content_categories (id)
);
```

**content_words**
```sql
CREATE TABLE content_words (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    word TEXT NOT NULL,                   -- Word or phrase
    category_id INTEGER NOT NULL,         -- Category ID
    confidence REAL DEFAULT 1.0,         -- Confidence score (0.0-1.0)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (category_id) REFERENCES content_categories (id),
    UNIQUE(word, category_id)
);
```

## Data Relationships

### Conversation Context Keys
Format: `{guild_id}:{channel_id}:{thread_id}:{user_id}`

**Examples:**
```
123456789:987654321:None:555666777     # Guild channel
123456789:987654321:111222333:None     # Thread in guild
None:None:None:555666777               # Direct message
```

### Personality Switching
1. User selects personality via `/personality` command
2. Record stored in `user_personalities` table
3. All future conversations use this personality
4. Image generation temporarily switches to `image_injection_prompt`

### Content Classification Flow
1. Prompt analyzed → words extracted
2. Words matched against `content_words` table
3. Categories determined via `content_categories` relationships
4. Content score calculated from confidence values

## Database Operations

### Conversation Isolation
```python
# Each context gets separate conversation thread
context_key = f"{guild_id}:{channel_id}:{thread_id}:{user_id}"

# Messages stored with context
INSERT INTO conversations (context_key, user_id, role, content, personality_name)
VALUES (?, ?, ?, ?, ?)
```

### Personality Management
```python
# Set user personality
INSERT OR REPLACE INTO user_personalities (user_id, personality_name)
VALUES (?, ?)

# Get current personality
SELECT p.* FROM personalities p 
JOIN user_personalities up ON p.name = up.personality_name
WHERE up.user_id = ?
```

### LoRA Intelligence
```python
# Find LoRAs for prompt
SELECT * FROM loras 
WHERE tags LIKE '%anime%' OR description LIKE '%anime%'
ORDER BY strength_default DESC
```

## Database Initialization

All databases created by:
```bash
python scripts/init_databases.py
```

**Built-in Data:**
- **6 personalities** (Fun Discord Bot, UwU, Sarcastic, Professional, Helpful, Creative)
- **161 content categories** (subject, style, environment classifications)
- **Sample LoRAs** (anime_style, realistic_portrait, fantasy_art)

## Data Storage Notes

**Plain Text Storage:**
- API keys stored unencrypted
- Conversation content stored unencrypted  
- No password hashing or encryption

**Local Only:**
- All databases stored locally
- No external database connections
- No data transmitted except via configured APIs

**Cleanup:**
- Old conversations auto-cleaned if `LLM_AUTO_CLEAN_ENABLED=true`
- Database size managed via automatic cleanup
- No manual maintenance required

## Database Access

**Direct Access:**
```bash
sqlite3 discord_llm.db "SELECT * FROM personalities;"
sqlite3 content_mapping.db "SELECT * FROM content_categories LIMIT 10;"
```

**Backup:**
```bash
cp *.db backups/
# Databases automatically excluded from git via .gitignore
```

**Reset:**
```bash
rm *.db
python scripts/init_databases.py
```

This is the complete database structure. All data is local SQLite with no encryption.