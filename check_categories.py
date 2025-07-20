#!/usr/bin/env python3
"""
Check exact category structure in the content database
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent))

from modules.stable_diffusion.content_db import ContentDatabase

def show_category_structure():
    """Show the complete category structure"""
    
    db = ContentDatabase("test_content.db")
    
    # Get all categories organized by type
    cursor = db.conn.execute("""
        SELECT full_path, category_type, description 
        FROM categories 
        ORDER BY category_type, full_path
    """)
    
    categories_by_type = {}
    for row in cursor.fetchall():
        cat_type = row[1]
        if cat_type not in categories_by_type:
            categories_by_type[cat_type] = []
        categories_by_type[cat_type].append((row[0], row[2]))
    
    for cat_type, categories in categories_by_type.items():
        print(f"\n📂 {cat_type.upper()} CATEGORIES:")
        for path, desc in categories:
            print(f"   {path}")
        
    db.close()
    
    # Cleanup
    import os
    try:
        os.remove("test_content.db")
    except:
        pass

if __name__ == "__main__":
    show_category_structure()