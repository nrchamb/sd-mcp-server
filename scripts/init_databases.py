#!/usr/bin/env python3
"""
Database Initialization Script
Creates all required databases and tables for the SD MCP Server
"""

import os
import sys
import sqlite3
import logging
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from modules.llm.llm_database import LLMDatabase
from modules.stable_diffusion.content_db import ContentDatabase

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_chevereto_users_db():
    """Create Chevereto users database"""
    db_path = "chevereto_users.db"
    logger.info(f"Creating Chevereto users database: {db_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Chevereto users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chevereto_users (
            user_id TEXT PRIMARY KEY,
            api_key TEXT NOT NULL,
            username TEXT,
            default_album_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Personal API keys for Discord users
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS personal_api_keys (
            discord_id TEXT PRIMARY KEY,
            api_key TEXT NOT NULL,
            username TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.commit()
    conn.close()
    logger.info(f"✅ Created {db_path}")

def create_discord_users_db():
    """Create Discord users database"""
    db_path = "discord_users.db"
    logger.info(f"Creating Discord users database: {db_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Discord users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS discord_users (
            discord_id TEXT PRIMARY KEY,
            username TEXT NOT NULL,
            discriminator TEXT,
            avatar_url TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # User folders table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_folders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            discord_id TEXT NOT NULL,
            folder_name TEXT NOT NULL,
            chevereto_album_id TEXT,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (discord_id) REFERENCES discord_users (discord_id),
            UNIQUE(discord_id, folder_name)
        )
    """)
    
    conn.commit()
    conn.close()
    logger.info(f"✅ Created {db_path}")

def create_lora_database():
    """Create LoRA database with sample data"""
    db_path = "lora_database.db"
    logger.info(f"Creating LoRA database: {db_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # LoRA table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS loras (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            filename TEXT NOT NULL,
            description TEXT,
            tags TEXT,
            category TEXT,
            strength_min REAL DEFAULT 0.5,
            strength_max REAL DEFAULT 1.0,
            strength_default REAL DEFAULT 0.8,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Add some sample LoRAs
    sample_loras = [
        ("anime_style", "anime_style.safetensors", "Anime art style", "anime,style,art", "style", 0.6, 1.0, 0.8),
        ("realistic_portrait", "realistic_portrait.safetensors", "Realistic portrait style", "realistic,portrait,photography", "style", 0.4, 0.9, 0.7),
        ("fantasy_art", "fantasy_art.safetensors", "Fantasy art style", "fantasy,art,digital", "style", 0.5, 1.0, 0.8),
    ]
    
    cursor.executemany("""
        INSERT OR IGNORE INTO loras 
        (name, filename, description, tags, category, strength_min, strength_max, strength_default)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, sample_loras)
    
    conn.commit()
    conn.close()
    logger.info(f"✅ Created {db_path} with {len(sample_loras)} sample LoRAs")

def initialize_all_databases():
    """Initialize all required databases"""
    logger.info("🚀 Initializing SD MCP Server databases...")
    
    # Create basic databases
    create_chevereto_users_db()
    create_discord_users_db()
    create_lora_database()
    
    # Initialize LLM database (includes personality system)
    logger.info("Creating LLM conversation database...")
    llm_db = LLMDatabase()
    # This automatically creates the database and loads personalities
    logger.info("✅ Created discord_llm.db with personality system")
    
    # Initialize content database
    logger.info("Creating content classification database...")
    content_db = ContentDatabase()
    # This automatically creates the database and loads content mappings
    logger.info("✅ Created content_mapping.db with classification system")
    
    # Create LoRA database in modules/stable_diffusion/
    modules_lora_path = Path("modules/stable_diffusion/lora_database.db")
    if not modules_lora_path.exists():
        logger.info(f"Creating {modules_lora_path}...")
        conn = sqlite3.connect(str(modules_lora_path))
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS loras (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                filename TEXT NOT NULL,
                description TEXT,
                tags TEXT,
                category TEXT,
                strength_min REAL DEFAULT 0.5,
                strength_max REAL DEFAULT 1.0,
                strength_default REAL DEFAULT 0.8,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.close()
        logger.info(f"✅ Created {modules_lora_path}")
    
    logger.info("🎉 All databases initialized successfully!")
    logger.info("\n📋 Created databases:")
    logger.info("   • chevereto_users.db - Image hosting user management")
    logger.info("   • discord_users.db - Discord bot user tracking")
    logger.info("   • discord_llm.db - LLM conversations and personalities")
    logger.info("   • lora_database.db - LoRA management")
    logger.info("   • modules/stable_diffusion/lora_database.db - LoRA tools")
    logger.info("   • modules/stable_diffusion/content_mapping.db - Content classification")
    
    logger.info("\n🔧 Next steps:")
    logger.info("   1. Configure your mcp.json with environment variables")
    logger.info("   2. Start Stable Diffusion WebUI with --api flag")
    logger.info("   3. Run: python start_discord_bot.py")

if __name__ == "__main__":
    initialize_all_databases()