import os
import logging
import atexit
from datetime import datetime

from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit

from database import db, init_db, create_tables, get_database_url
from model import Inventory
from notify import PostgresListener

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global listener instance
postgres_listener = None


def create_app():
    """Create and configure Flask application"""
    app = Flask(__name__)

    # Configuration
    app.config['SQLALCHEMY_DATABASE_URI'] = get_database_url()
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Initialize extensions
    init_db(app)
    socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

    # Register routes
    register_routes(app)
    register_socketio_events(socketio)

    # Initialize database and listener
    with app.app_context():
        initialize_application(socketio)

    return app, socketio


def register_routes(app):
    """Register all Flask routes"""

    @app.route('/')
    def index():
        """Serve the main page"""
        try:
            with open('static/index.html', 'r') as f:
                return f.read()
        except FileNotFoundError:
            return """
                <!DOCTYPE html>
                <html>
                <head>
                <title>Flask Inventory Tracker</title>
                </head>
                <body>
                <h1>Flask Real-Time Inventory Tracker</h1>
                <p>Please create the static/index.html file from the tutorial.</p>
                </body>
                </html>
        """

    @app.route('/api/inventory', methods=['GET'])
    def get_inventory():
        """Get all inventory items"""
        try:
            items = Inventory.query.order_by(Inventory.updated_at.desc()).all()
            return jsonify([item.to_dict() for item in items])
        except Exception as e:
            logger.error(f"Error fetching inventory: {e}")
            return jsonify({'error': 'Failed to fetch inventory'}), 500

    @app.route('/api/inventory', methods=['POST'])
    def create_inventory_item():
        """Create a new inventory item"""
        try:
            data = request.get_json()

            # Validation
            if not data or 'name' not in data or 'quantity' not in data:
                return jsonify({'error': 'Name and quantity are required'}), 400

            if not isinstance(data['quantity'], int) or data['quantity'] < 0:
                return jsonify({'error': 'Quantity must be a non-negative integer'}), 400

            # Create new item
            item = Inventory(
                name=data['name'].strip(),
                quantity=data['quantity']
            )

            db.session.add(item)
            db.session.commit()

            logger.info(f"Created inventory item: {item.name}")
            return jsonify(item.to_dict()), 201

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creating inventory item: {e}")
            return jsonify({'error': 'Failed to create item'}), 500

    @app.route('/api/inventory/<int:item_id>', methods=['PUT'])
    def update_inventory_item(item_id: int):
        """Update an inventory item's quantity"""
        try:
            item = Inventory.query.get_or_404(item_id)
            data = request.get_json()

            # Validation
            if not data or 'quantity' not in data:
                return jsonify({'error': 'Quantity is required'}), 400

            if not isinstance(data['quantity'], int) or data['quantity'] < 0:
                return jsonify({'error': 'Quantity must be a non-negative integer'}), 400

            # Update item
            item.quantity = data['quantity']
            item.updated_at = datetime.utcnow()

            db.session.commit()

            logger.info(f"Updated inventory item: {item.name} (quantity: {item.quantity})")
            return jsonify(item.to_dict())

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error updating inventory item: {e}")
            return jsonify({'error': 'Failed to update item'}), 500

    @app.route('/api/inventory/<int:item_id>', methods=['DELETE'])
    def delete_inventory_item(item_id: int):
        """Delete an inventory item"""
        try:
            item = Inventory.query.get_or_404(item_id)
            item_name = item.name

            db.session.delete(item)
            db.session.commit()

            logger.info(f"Deleted inventory item: {item_name}")
            return jsonify({'message': 'Item deleted successfully'})

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error deleting inventory item: {e}")
            return jsonify({'error': 'Failed to delete item'}), 500

    # Error handlers
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({'error': 'Item not found'}), 404

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return jsonify({'error': 'Internal server error'}), 500


def register_socketio_events(socketio):
    """Register Socket.IO event handlers"""

    @socketio.on('connect')
    def handle_connect():
        logger.info(f"Client connected: {request.sid}")
        emit('connection_status', {'connected': True})

    @socketio.on('disconnect')
    def handle_disconnect():
        logger.info(f"Client disconnected: {request.sid}")


def initialize_application(socketio):
    """Initialize database and start PostgreSQL listener"""
    global postgres_listener

    # Create tables
    create_tables()
    logger.info("Database tables created")

    # Start PostgreSQL listener
    try:
        database_url = get_database_url()
        postgres_listener = PostgresListener(database_url, socketio)
        postgres_listener.start_listening()
    except Exception as e:
        logger.error(f"Failed to start PostgreSQL listener: {e}")


def cleanup():
    """Cleanup function for application shutdown"""
    global postgres_listener
    if postgres_listener:
        postgres_listener.stop_listening()


# Register cleanup function
atexit.register(cleanup)

if __name__ == '__main__':
    # Create static directory if it doesn't exist
    os.makedirs('static', exist_ok=True)

    # Create and run the application
    app, socketio = create_app()

    # Run the application
    socketio.run(
        app,
        host='0.0.0.0',
        port=8000,
        debug=True,
        allow_unsafe_werkzeug=True  # Only for development
    )
