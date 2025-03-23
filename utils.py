import os
from supabase import create_client

def get_supabase_client():
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_KEY')
    
    if not supabase_url or not supabase_key:
        raise ValueError("Please set both SUPABASE_URL and SUPABASE_KEY environment variables")
    
    supabase_client = create_client(supabase_url, supabase_key)
    return supabase_client