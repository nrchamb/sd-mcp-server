#!/usr/bin/env python3
"""
Debug the database initialization process
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent))

def debug_database_init():
    """Debug the database initialization"""
    
    print("🔍 Debugging Database Initialization")
    print("=" * 50)
    
    try:
        from modules.stable_diffusion.content_db import ContentDatabase
        
        # Create a fresh database to see initialization
        import os
        test_db_path = "test_debug.db"
        
        # Remove if exists
        if os.path.exists(test_db_path):
            os.remove(test_db_path)
        
        print(f"📂 Creating fresh database: {test_db_path}")
        
        # Create database and see what happens
        db = ContentDatabase(test_db_path)
        
        # Check what got created
        cursor = db.conn.execute("SELECT COUNT(*) FROM categories")
        category_count = cursor.fetchone()[0]
        print(f"✅ Categories created: {category_count}")
        
        cursor = db.conn.execute("SELECT COUNT(*) FROM words")
        word_count = cursor.fetchone()[0]
        print(f"📝 Words loaded: {word_count}")
        
        cursor = db.conn.execute("SELECT COUNT(*) FROM word_categories")
        mapping_count = cursor.fetchone()[0]
        print(f"🔗 Mappings loaded: {mapping_count}")
        
        # Try to manually call the mapping loader
        print(f"\n🔧 Manually calling _load_initial_word_mappings...")
        db._load_initial_word_mappings()
        
        # Check again
        cursor = db.conn.execute("SELECT COUNT(*) FROM words")
        word_count = cursor.fetchone()[0]
        print(f"📝 Words after manual load: {word_count}")
        
        cursor = db.conn.execute("SELECT COUNT(*) FROM word_categories")
        mapping_count = cursor.fetchone()[0]
        print(f"🔗 Mappings after manual load: {mapping_count}")
        
        # Show sample mappings
        if mapping_count > 0:
            cursor = db.conn.execute("""
                SELECT w.word, c.full_path 
                FROM words w 
                JOIN word_categories wc ON w.id = wc.word_id 
                JOIN categories c ON wc.category_id = c.id 
                LIMIT 5
            """)
            mappings = cursor.fetchall()
            print(f"🎯 Sample mappings:")
            for word, category in mappings:
                print(f"   • {word} → {category}")
        
        db.close()
        
        # Cleanup
        os.remove(test_db_path)
        
    except Exception as e:
        print(f"❌ Debug failed: {e}")
        import traceback
        print(traceback.format_exc())

if __name__ == "__main__":
    debug_database_init()