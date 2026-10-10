import os
from dotenv import load_dotenv

# Load environment variables from root .env file
backend_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(backend_dir)
env_path = os.path.join(project_root, '.env')
load_dotenv(dotenv_path=env_path, override=True)


class Config:
    """Base application configuration."""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'nexora-secret-key-2024-change-in-production')
    
    # Database configuration (defaults to SQLite instance in backend)
    BASE_DIR = os.path.dirname(backend_dir)
    INSTANCE_DIR = os.path.join(backend_dir, 'instance')
    os.makedirs(INSTANCE_DIR, exist_ok=True)
    
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL', 
        f'sqlite:///{os.path.join(INSTANCE_DIR, "nexora.db")}'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Uploads configuration
    UPLOADS_DIR = os.path.join(BASE_DIR, 'uploads')
    os.makedirs(os.path.join(UPLOADS_DIR, 'course_thumbnails'), exist_ok=True)
    os.makedirs(os.path.join(UPLOADS_DIR, 'profile_images'), exist_ok=True)
    os.makedirs(os.path.join(UPLOADS_DIR, 'temp'), exist_ok=True)
    
    # Supabase credentials
    SUPABASE_URL = os.environ.get('SUPABASE_URL', '')
    SUPABASE_ANON_KEY = os.environ.get('SUPABASE_ANON_KEY', '')
    SUPABASE_SERVICE_ROLE_KEY = os.environ.get('SUPABASE_SERVICE_ROLE_KEY', '')
