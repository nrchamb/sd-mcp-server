"""
Initial word mappings for the content database
This script populates the database with common prompt words and their categories
"""

from content_db import ContentDatabase

def populate_initial_mappings():
    """Populate database with initial word-category mappings"""
    
    db = ContentDatabase("content_mapping.db")
    
    # Person mappings
    person_mappings = [
        # Basic person types
        ("man", "subject/person/man", 1.0),
        ("male", "subject/person/man", 0.9),
        ("guy", "subject/person/man", 0.8),
        ("gentleman", "subject/person/man", 0.9),
        ("woman", "subject/person/woman", 1.0),
        ("female", "subject/person/woman", 0.9),
        ("lady", "subject/person/woman", 0.8),
        ("girl", "subject/person/girl", 1.0),
        ("boy", "subject/person/boy", 1.0),
        ("child", "subject/person/child", 1.0),
        ("kid", "subject/person/child", 0.8),
        ("teenager", "subject/person/teenager", 1.0),
        ("teen", "subject/person/teenager", 0.9),
        ("elderly", "subject/person/elderly", 1.0),
        ("old", "subject/person/elderly", 0.7),
        
        # Figure/body types
        ("tall", "subject/person/figure/tall", 1.0),
        ("short", "subject/person/figure/short", 1.0),
        ("athletic", "subject/person/figure/athletic", 1.0),
        ("fit", "subject/person/figure/athletic", 0.8),
        ("slim", "subject/person/figure/slim", 1.0),
        ("thin", "subject/person/figure/slim", 0.8),
        ("curvy", "subject/person/figure/curvy", 1.0),
        ("voluptuous", "subject/person/figure/curvy", 0.9),
        ("muscular", "subject/person/figure/muscular", 1.0),
        ("buff", "subject/person/figure/muscular", 0.8),
        ("petite", "subject/person/figure/petite", 1.0),
        ("small", "subject/person/figure/petite", 0.6),
        
        # Hair length
        ("long hair", "subject/person/hair/hair_length/long_hair", 1.0),
        ("short hair", "subject/person/hair/hair_length/short_hair", 1.0),
        ("medium hair", "subject/person/hair/hair_length/medium_hair", 1.0),
        
        # Hair colors
        ("blonde", "subject/person/hair/hair_color/blonde", 1.0),
        ("brunette", "subject/person/hair/hair_color/brunette", 1.0),
        ("redhead", "subject/person/hair/hair_color/red_hair", 1.0),
        
        # Hair styles
        ("straight hair", "subject/person/hair/hair_style/straight", 1.0),
        ("curly hair", "subject/person/hair/hair_style/curly", 1.0),
        ("wavy hair", "subject/person/hair/hair_style/wavy", 1.0),
        ("braided", "subject/person/hair/hair_style/braided", 1.0),
        ("ponytail", "subject/person/hair/hair_style/ponytail", 1.0),
        
        # Expressions
        ("smiling", "subject/person/expression/smiling", 1.0),
        ("smile", "subject/person/expression/smiling", 0.9),
        ("serious", "subject/person/expression/serious", 1.0),
        ("angry", "subject/person/expression/angry", 1.0),
        ("mad", "subject/person/expression/angry", 0.8),
        ("sad", "subject/person/expression/sad", 1.0),
        ("surprised", "subject/person/expression/surprised", 1.0),
        ("shocked", "subject/person/expression/surprised", 0.8),
        ("laughing", "subject/person/expression/laughing", 1.0),
        ("crying", "subject/person/expression/crying", 1.0),
        
        # Actions
        ("standing", "subject/person/action/standing", 1.0),
        ("sitting", "subject/person/action/sitting", 1.0),
        ("running", "subject/person/action/running", 1.0),
        ("walking", "subject/person/action/walking", 1.0),
        ("dancing", "subject/person/action/dancing", 1.0),
        ("jumping", "subject/person/action/jumping", 1.0),
        ("lying", "subject/person/action/lying", 1.0),
    ]
    
    # Clothing mappings
    clothing_mappings = [
        # Upper body
        ("shirt", "subject/clothing/upper_body/shirt", 1.0),
        ("t-shirt", "subject/clothing/upper_body/shirt/t_shirt", 1.0),
        ("tshirt", "subject/clothing/upper_body/shirt/t_shirt", 1.0),
        ("dress shirt", "subject/clothing/upper_body/shirt/dress_shirt", 1.0),
        ("blouse", "subject/clothing/upper_body/blouse", 1.0),
        ("sweater", "subject/clothing/upper_body/sweater", 1.0),
        ("hoodie", "subject/clothing/upper_body/sweater", 0.8),
        ("jacket", "subject/clothing/upper_body/jacket", 1.0),
        ("coat", "subject/clothing/upper_body/coat", 1.0),
        
        # Lower body
        ("pants", "subject/clothing/lower_body/pants", 1.0),
        ("jeans", "subject/clothing/lower_body/pants/jeans", 1.0),
        ("trousers", "subject/clothing/lower_body/pants/trousers", 1.0),
        ("shorts", "subject/clothing/lower_body/shorts", 1.0),
        ("skirt", "subject/clothing/lower_body/skirt", 1.0),
        ("miniskirt", "subject/clothing/lower_body/skirt/mini_skirt", 1.0),
        ("mini skirt", "subject/clothing/lower_body/skirt/mini_skirt", 1.0),
        ("long skirt", "subject/clothing/lower_body/skirt/long_skirt", 1.0),
        
        # Dresses
        ("dress", "subject/clothing/dress", 1.0),
        ("gown", "subject/clothing/dress/formal_dress", 0.9),
        ("evening dress", "subject/clothing/dress/evening_dress", 1.0),
        
        # Underwear (content filtered)
        ("bra", "subject/clothing/underwear/bra", 1.0),
        ("panties", "subject/clothing/underwear/panties", 1.0),
        ("underwear", "subject/clothing/underwear", 1.0),
        ("lingerie", "subject/clothing/underwear", 0.9),
        
        # Footwear
        ("shoes", "subject/clothing/footwear/shoes", 1.0),
        ("boots", "subject/clothing/footwear/boots", 1.0),
        ("sneakers", "subject/clothing/footwear/sneakers", 1.0),
        ("heels", "subject/clothing/footwear/heels", 1.0),
        ("high heels", "subject/clothing/footwear/heels", 1.0),
        ("sandals", "subject/clothing/footwear/sandals", 1.0),
    ]
    
    # Style mappings
    style_mappings = [
        # Medium
        ("photography", "style/medium/photography", 1.0),
        ("photo", "style/medium/photography", 0.9),
        ("photograph", "style/medium/photography", 0.9),
        ("painting", "style/medium/painting", 1.0),
        ("digital art", "style/medium/digital_art", 1.0),
        ("sketch", "style/medium/sketch", 1.0),
        ("drawing", "style/medium/sketch", 0.8),
        
        # Art movements
        ("impressionist", "style/art_movement/impressionist", 1.0),
        ("surreal", "style/art_movement/surrealist", 1.0),
        ("cubist", "style/art_movement/cubist", 1.0),
        ("renaissance", "style/art_movement/renaissance", 1.0),
        ("baroque", "style/art_movement/baroque", 1.0),
        
        # Modern styles
        ("cyberpunk", "style/modern_style/cyberpunk", 1.0),
        ("steampunk", "style/modern_style/steampunk", 1.0),
        ("art deco", "style/modern_style/art_deco", 1.0),
        ("minimalist", "style/modern_style/minimalist", 1.0),
        ("gothic", "style/modern_style/gothic", 1.0),
        
        # Quality
        ("high quality", "style/quality/high_quality", 1.0),
        ("detailed", "style/quality/detailed", 1.0),
        ("masterpiece", "style/quality/masterpiece", 1.0),
        ("professional", "style/quality/professional", 1.0),
    ]
    
    # Environment mappings
    environment_mappings = [
        # Settings
        ("indoor", "environment/setting_type/indoor", 1.0),
        ("outdoor", "environment/setting_type/outdoor", 1.0),
        ("inside", "environment/setting_type/indoor", 0.8),
        ("outside", "environment/setting_type/outdoor", 0.8),
        
        # Locations
        ("home", "environment/location/home", 1.0),
        ("house", "environment/location/home", 0.8),
        ("office", "environment/location/office", 1.0),
        ("restaurant", "environment/location/restaurant", 1.0),
        ("school", "environment/location/school", 1.0),
        ("park", "environment/location/park", 1.0),
        ("beach", "environment/location/beach", 1.0),
        ("forest", "environment/location/forest", 1.0),
        ("city", "environment/location/city", 1.0),
        ("urban", "environment/location/city", 0.8),
        
        # Time periods
        ("modern", "environment/time_period/modern", 1.0),
        ("contemporary", "environment/time_period/modern", 0.8),
        ("medieval", "environment/time_period/medieval", 1.0),
        ("victorian", "environment/time_period/victorian", 1.0),
        ("futuristic", "environment/time_period/futuristic", 1.0),
        ("future", "environment/time_period/futuristic", 0.8),
        ("ancient", "environment/time_period/ancient", 1.0),
        
        # Lighting
        ("natural light", "environment/lighting/natural_light", 1.0),
        ("sunlight", "environment/lighting/natural_light", 0.8),
        ("artificial light", "environment/lighting/artificial_light", 1.0),
        ("dramatic lighting", "environment/lighting/dramatic_lighting", 1.0),
        ("soft lighting", "environment/lighting/soft_lighting", 1.0),
        ("neon", "environment/lighting/neon", 1.0),
    ]
    
    # Content filter mappings
    content_filter_mappings = [
        # NSFW terms
        ("nude", "content_filter/nsfw/nudity", 1.0),
        ("naked", "content_filter/nsfw/nudity", 1.0),
        ("nsfw", "content_filter/nsfw", 1.0),
        ("explicit", "content_filter/nsfw/sexual", 1.0),
        ("sexual", "content_filter/nsfw/sexual", 1.0),
        ("erotic", "content_filter/nsfw/sexual", 1.0),
        ("sexy", "content_filter/nsfw/suggestive", 0.8),
        ("suggestive", "content_filter/nsfw/suggestive", 1.0),
        ("provocative", "content_filter/nsfw/suggestive", 0.9),
        ("revealing", "content_filter/nsfw/suggestive", 0.7),
        
        # Violence terms
        ("violence", "content_filter/violence", 1.0),
        ("violent", "content_filter/violence", 1.0),
        ("weapon", "content_filter/violence/weapons", 1.0),
        ("gun", "content_filter/violence/weapons", 1.0),
        ("knife", "content_filter/violence/weapons", 1.0),
        ("sword", "content_filter/violence/weapons", 1.0),
        ("gore", "content_filter/violence/gore", 1.0),
        ("blood", "content_filter/violence/gore", 0.8),
        ("fighting", "content_filter/violence/fighting", 1.0),
        ("fight", "content_filter/violence/fighting", 0.9),
        ("battle", "content_filter/violence/fighting", 0.8),
        ("war", "content_filter/violence/fighting", 0.7),
    ]
    
    # Surreal mappings
    surreal_mappings = [
        ("melting", "surreal/distortion/melting", 1.0),
        ("twisted", "surreal/distortion/twisted", 1.0),
        ("fragmented", "surreal/distortion/fragmented", 1.0),
        ("stretched", "surreal/distortion/stretched", 1.0),
        ("floating", "surreal/impossible/floating", 1.0),
        ("inverted", "surreal/impossible/inverted", 1.0),
        ("recursive", "surreal/impossible/recursive", 1.0),
        ("dreamlike", "surreal", 0.8),
        ("surreal", "surreal", 1.0),
        ("abstract", "surreal", 0.7),
    ]
    
    # Mood/motif mappings
    motif_mappings = [
        ("dark", "motif/mood/dark", 1.0),
        ("cheerful", "motif/mood/cheerful", 1.0),
        ("happy", "motif/mood/cheerful", 0.8),
        ("mysterious", "motif/mood/mysterious", 1.0),
        ("epic", "motif/mood/epic", 1.0),
        ("romantic", "motif/mood/romantic", 1.0),
        ("love", "motif/theme/love", 1.0),
        ("nature", "motif/theme/nature", 1.0),
        ("technology", "motif/theme/technology", 1.0),
        ("tech", "motif/theme/technology", 0.8),
    ]
    
    # Combine all mappings
    all_mappings = (
        person_mappings + clothing_mappings + style_mappings + 
        environment_mappings + content_filter_mappings + 
        surreal_mappings + motif_mappings
    )
    
    # Add all mappings to database
    successful = 0
    failed = 0
    
    for word, category_path, confidence in all_mappings:
        if db.add_word_mapping(word, category_path, confidence, "initial"):
            successful += 1
        else:
            failed += 1
            print(f"Failed to add: {word} -> {category_path}")
    
    print(f"Added {successful} word mappings successfully")
    if failed > 0:
        print(f"Failed to add {failed} mappings")
    
    db.close()

if __name__ == "__main__":
    populate_initial_mappings()