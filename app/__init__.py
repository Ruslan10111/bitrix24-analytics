"""Bitrix24 Analytics — Marketplace-ready management dashboard."""

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
import os

db = SQLAlchemy()
migrate = Migrate()


def create_app():
    app = Flask(
        __name__,
        template_folder=os.path.join(os.path.dirname(__file__), '..', 'templates'),
        static_folder=os.path.join(os.path.dirname(__file__), '..', 'static'),
    )

    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-change-me')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///app.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['BITRIX24_CLIENT_ID'] = os.getenv('BITRIX24_CLIENT_ID', '')
    app.config['BITRIX24_CLIENT_SECRET'] = os.getenv('BITRIX24_CLIENT_SECRET', '')
    app.config['APP_BASE_URL'] = os.getenv('APP_BASE_URL', 'http://localhost:5000')

    db.init_app(app)
    migrate.init_app(app, db)

    from . import routes
    app.register_blueprint(routes.bp)

    @app.after_request
    def allow_iframe(response):
        # Remove X-Frame-Options to allow embedding in Bitrix24 iframe
        response.headers.pop('X-Frame-Options', None)
        return response

    with app.app_context():
        db.create_all()

    return app
