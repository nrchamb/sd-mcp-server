# Discord Integration 🤖

## Commands Reference

### Image Generation Commands

**`/sd-generate`** - Direct image generation
```
/sd-generate prompt:"anime girl with blue hair" 
             negative_prompt:"blurry, low quality"
             steps:25 
             width:1024 
             height:1024 
             cfg_scale:7.0
```

**`/sd-assist`** - LLM-guided generation (placeholder)
```
/sd-assist prompt:"help me create a fantasy landscape"
```

### Conversation Commands

**`/chat`** - Chat with current personality
```
/chat message:"How are you today?"
```

**`/personality`** - Switch AI personalities
```
/personality
# Shows button interface with 6 personalities
```

**`/clear-chat`** - Clear conversation history
```
/clear-chat
# Clears conversation for current context (channel/thread/DM)
```

### User Management Commands

**`/sd-settings`** - View your settings
```
/sd-settings
# Shows Chevereto account status, folder count
```

**`/sd-setup`** - Account setup interface
```
/sd-setup
# Shows setup options with buttons
```

**`/sd-api-key`** - Set personal Chevereto API key
```
/sd-api-key api_key:"your_personal_api_key" username:"your_username"
```

**`/sd-remove-key`** - Remove personal API key
```
/sd-remove-key
# Falls back to guest mode
```

**`/sd-register`** - Register as test user
```
/sd-register
# Creates entry in discord_users table
```

### Admin Commands

**`/timeout-user`** - Timeout user from AI features
```
/timeout-user user:@username minutes:60 reason:"Spam"
```

**`/suspend-user`** - Suspend user from AI features  
```
/suspend-user user:@username reason:"Policy violation"
```

**`/lock-personality`** - Lock user to specific personality
```
/lock-personality user:@username personality:"professional"
```

### Utility Commands

**`/test`** - Simple test command
```
/test
# Returns "Bot is working!" message
```

## Personality System

### Built-in Personalities

**Fun Discord Bot** (default)
- Emoji: 🎉
- Style: Playful, teasing, uses Discord slang
- Image prompt: Adds "fun, colorful, vibrant" to image requests

**UwU Bot**
- Emoji: 🥺  
- Style: Kawaii, adorable, uses "uwu" speech patterns
- Image prompt: Adds "cute, kawaii, anime style" to image requests

**Sarcastic Bot**
- Emoji: 😏
- Style: Witty, sarcastic humor, dry responses
- Image prompt: Adds "dramatic, moody lighting" to image requests

**Professional Assistant**
- Emoji: 💼
- Style: Business-focused, formal, direct
- Image prompt: Adds "professional, clean, high quality" to image requests

**Helpful Assistant**  
- Emoji: 🤝
- Style: Direct, informative, no-nonsense
- Image prompt: Adds "clear, detailed, photorealistic" to image requests

**Creative Companion**
- Emoji: 🎨
- Style: Imaginative, artistic, creative suggestions
- Image prompt: Adds "artistic, creative, unique style" to image requests

### Personality Switching

**Per-User Persistence:**
- Each user has one personality across all channels/threads/DMs
- Personality stored in `user_personalities` table
- Survives bot restarts

**Image Generation Override:**
- Chat personality temporarily switches to `image_injection_prompt` during image generation
- Returns to chat personality after generation
- Allows personality-specific image enhancement

**Admin Controls:**
- Admins can lock users to specific personalities
- Locked users cannot change personality via `/personality` command
- Admin actions logged in `admin_actions` table

## Conversation Management

### Context Isolation

**Guild Channels:**
- Each channel has separate conversation thread
- Context: `{guild_id}:{channel_id}:None:None`

**Threads:**  
- Each thread has separate conversation thread
- Context: `{guild_id}:{channel_id}:{thread_id}:None`

**Direct Messages:**
- Each user has separate DM conversation thread
- Context: `None:None:None:{user_id}`

### Message Handling

**Bot Mentions:**
```python
@bot mention "Can you help me?"
# Triggers conversation in any channel
```

**Thread Conversations:**
```python
# Any message in a thread the bot participated in
# triggers conversation continuation
```

**Rate Limiting:**
- Default: 10 messages per minute per user
- Configurable via `CHAT_RATE_LIMIT_PER_MINUTE`
- Prevents spam and abuse

### Memory Management

**Auto-Cleanup:**
- Old conversations auto-deleted if `LLM_AUTO_CLEAN_ENABLED=true`
- Configurable retention period
- Prevents database bloat

**Manual Cleanup:**
- `/clear-chat` command clears current context
- Admin commands can clear user conversations
- Database reset via `scripts/init_databases.py`

## Image Upload Integration

### Chevereto Integration

**Guest Mode:** (default)
- Anonymous uploads with 30-minute expiry
- Uses `CHEVERETO_GUEST_API_KEY`
- No account required

**Personal API Mode:**
- User sets personal Chevereto API key via `/sd-api-key`
- Permanent uploads to user's account
- Can create folders/albums

**User Registration:**
- `/sd-register` creates Discord user entry
- Links Discord ID to Chevereto account
- Enables folder management

### Upload Workflow

1. **Image Generation** → SD WebUI creates image
2. **Content Filtering** → NudeNet scans (if enabled)
3. **Upload Decision** → Chevereto vs Local based on configuration
4. **URL Generation** → Returns public URL or local path
5. **Discord Response** → Embedded image or attachment

### Upload Modes

**Chevereto Priority:**
```
✅ Chevereto upload → Public URL in embed
❌ Chevereto fails → Local attachment fallback
```

**Local Priority:**
```
✅ Local storage → Discord attachment
❌ Local fails → Error message
```

## Error Handling

### Command Errors

**LLM Unavailable:**
```
❌ LLM features are not available.
```

**Generation Failed:**
```
❌ Generation failed: SD WebUI connection error
💡 Suggestion: Check SD WebUI status
```

**Rate Limited:**
```
❌ Rate limit exceeded. Please wait.
```

### Graceful Degradation

**Missing Chevereto:** Falls back to local storage
**Missing LLM:** Commands show unavailable message  
**Missing SD WebUI:** Generation commands fail with suggestions
**Database Issues:** Retry with exponential backoff

## Bot Permissions

### Required Permissions
- Send Messages
- Use Slash Commands
- Embed Links  
- Attach Files
- Read Message History

### Optional Permissions
- Manage Messages (for admin commands)
- Timeout Members (for user timeouts)
- Add Reactions (for interactive features)

## Configuration

### Environment Variables
```bash
# Required for Discord
DISCORD_BOT_TOKEN=your_bot_token

# Optional integrations
SD_BASE_URL=http://localhost:7860
LM_STUDIO_BASE_URL=http://localhost:1234
CHEVERETO_BASE_URL=https://your-instance.com
CHEVERETO_GUEST_API_KEY=your_guest_key

# Feature toggles
ENABLE_DISCORD=true
NSFW_FILTER=false
CHAT_RATE_LIMIT_PER_MINUTE=10
```

### Bot Startup
```bash
# Standalone bot
python start_discord_bot.py

# Integrated with MCP
# Add DISCORD_BOT_TOKEN to MCP environment
```

## Natural Language Integration

### Automatic Image Detection
```
User: "generate a sunset over mountains"
Bot: [Detects image intent] → [Generates image] → [Returns with personality]
```

### Conversation Flow
```
User: /personality (selects UwU)
User: /chat message:"Create an image of a cat"
Bot: [UwU personality] + [Image generation] + [UwU response style]
```

The Discord integration provides a complete chat interface with personality-driven conversations and seamless image generation.