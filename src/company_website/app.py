from flask import Flask

from .config import Config
from .db import init_db, init_legacy_db
from .auth import auth_bp, login_manager
from .routes import main_bp


def create_app():
    if not Config.SECRET_KEY:
        raise RuntimeError('SECRET_KEY must be configured before starting the application.')

    app = Flask(__name__)
    app.config.from_object(Config)

    from flask_wtf.csrf import CSRFProtect
    CSRFProtect(app)

    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message_category = 'error'

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)

    @app.after_request
    def add_security_headers(response):
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; object-src 'none'; frame-ancestors 'none'; "
            "base-uri 'self'; form-action 'self'; "
            "script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'"
        )
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
        return response

    init_db()
    init_legacy_db()

    return app
