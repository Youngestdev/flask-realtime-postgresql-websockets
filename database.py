import os
from flask_sqlalchemy import SQLAlchemy

# Initialize SQLAlchemy (will be bound to Flask app later)
db = SQLAlchemy()


def init_db(app):
    """Initialize database with Flask app"""
    db.init_app(app)


def create_tables():
    """Create database tables"""
    db.create_all()


def get_database_url():
    """Get database URL from environment or use default"""
    return os.getenv(
        'DATABASE_URL',
        'postgresql://localhost/inventory_db'
    )
