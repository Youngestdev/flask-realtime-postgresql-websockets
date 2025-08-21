import json
import threading
import logging
import select
import psycopg2

logger = logging.getLogger(__name__)


class PostgresListener:
    def __init__(self, database_url: str, socketio=None):
        self.database_url = database_url
        self.connection = None
        self.running = False
        self.thread = None
        self.socketio = socketio

    def connect(self):
        """Connect to PostgreSQL for listening"""
        try:
            self.connection = psycopg2.connect(self.database_url)
            self.connection.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
            logger.info("Connected to PostgreSQL for notifications")
        except Exception as e:
            logger.error(f"Failed to connect to PostgreSQL: {e}")
            raise

    def start_listening(self):
        """Start listening to PostgreSQL notifications in a separate thread"""
        if self.running:
            return

        self.running = True
        self.thread = threading.Thread(target=self._listen_loop, daemon=True)
        self.thread.start()
        logger.info("Started PostgreSQL notification listener")

    def stop_listening(self):
        """Stop listening to PostgreSQL notifications"""
        self.running = False
        if self.connection:
            self.connection.close()
        logger.info("Stopped PostgreSQL notification listener")

    def set_socketio(self, socketio):
        """Set the SocketIO instance for broadcasting"""
        self.socketio = socketio

    def _listen_loop(self):
        """Main listening loop"""
        try:
            if not self.connection:
                self.connect()

            # Listen to the inventory channel
            cursor = self.connection.cursor()
            cursor.execute("LISTEN inventory_channel;")

            logger.info("Listening for PostgreSQL notifications on inventory_channel")

            while self.running:
                if select.select([self.connection], [], [], 1) == ([], [], []):
                    continue

                self.connection.poll()
                while self.connection.notifies:
                    notify = self.connection.notifies.pop(0)
                    try:
                        payload = json.loads(notify.payload)
                        logger.info(f"Received notification: {payload}")

                        # Broadcast to all connected WebSocket clients
                        if self.socketio:
                            self.socketio.emit('inventory_update', payload, namespace='/')

                    except Exception as e:
                        logger.error(f"Error processing notification: {e}")

        except Exception as e:
            logger.error(f"Error in PostgreSQL listener: {e}")
        finally:
            if self.connection:
                self.connection.close()
