"""
Nexora Learning Platform - Main Flask Application (Backend)
Entry point for the production server.
"""

import os
import sys
from dotenv import load_dotenv
from flask import Flask, render_template, send_from_directory, request, redirect, session, jsonify, url_for
from flask_cors import CORS

backend_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(backend_dir)
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# Load environment variables from root .env file
env_path = os.path.join(project_root, '.env')
load_dotenv(dotenv_path=env_path, override=True)

from config import Config
from models import db
from routes import api_blueprint


def validate_google_env(app):
    google_vars = ['GOOGLE_CLIENT_ID', 'GOOGLE_CLIENT_SECRET', 'GOOGLE_REDIRECT_URI']
    missing_vars = []
    
    print("--- GOOGLE OAUTH ENVIRONMENT CONFIGURATION CHECK ---")
    for var in google_vars:
        val = os.getenv(var, '').strip()
        if not val:
            print(f"[ENV CHECK] {var}: MISSING")
            app.logger.warning(f"[ENV CHECK] {var}: MISSING")
            missing_vars.append(var)
        elif 'your_google' in val.lower():
            print(f"[ENV CHECK] {var}: PLACEHOLDER DEFAULT ('{val}')")
            app.logger.warning(f"[ENV CHECK] {var}: PLACEHOLDER DEFAULT")
            missing_vars.append(var)
        else:
            print(f"[ENV CHECK] {var}: SUCCESSFULLY LOADED")
            app.logger.info(f"[ENV CHECK] {var}: SUCCESSFULLY LOADED")

    if missing_vars:
        print(f"ERROR: Missing Google OAuth credentials in .env: {', '.join(missing_vars)}")
        app.logger.error(f"Missing Google OAuth credentials in .env: {', '.join(missing_vars)}")
    else:
        print("SUCCESS: All Google OAuth credentials loaded successfully.")
        app.logger.info("All Google OAuth credentials loaded successfully.")
    print("-----------------------------------------------------")


def create_app():
    template_dir = os.path.abspath(os.path.join(project_root, 'frontend', 'templates'))
    static_dir = os.path.abspath(os.path.join(project_root, 'frontend', 'static'))
    uploads_dir = os.path.abspath(os.path.join(project_root, 'uploads'))

    app = Flask(
        __name__,
        template_folder=template_dir,
        static_folder=static_dir
    )

    app.config.from_object(Config)

    # Allow cross-origin requests
    CORS(app, supports_credentials=True, resources={r"/api/*": {"origins": "*"}})

    # Initialize Extensions
    db.init_app(app)

    # Register Blueprints
    app.register_blueprint(api_blueprint, url_prefix='/api')

    # Validate Google OAuth environment variables
    validate_google_env(app)
    
    # Route for serving uploaded media (thumbnails, profile images, videos)
    @app.route('/uploads/<path:filename>')
    def serve_upload(filename):
        return send_from_directory(uploads_dir, filename)

    # Fallback route matching GOOGLE_REDIRECT_URI in .env
    @app.route('/auth/google/callback')
    def google_auth_callback_fallback():
        qs = request.query_string.decode('utf-8')
        return redirect(f"/api/auth/google/callback?{qs}" if qs else "/api/auth/google/callback")

    # Serve Frontend Single Page Application
    @app.route('/')
    def index():
        return render_template('index.html')

    # Create Tables on App Context Startup
    with app.app_context():
        db.create_all()

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, port=5000)
