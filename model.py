from datetime import datetime
from pydantic import BaseModel

from typing import Dict, Any

from database import db


class Inventory(db.Model):
	__tablename__ = 'inventory'

	id = db.Column(db.Integer, primary_key=True)
	name = db.Column(db.String, nullable=False)
	quantity = db.Column(db.Integer, nullable=False)
	updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

	def to_dict(self) -> Dict[str, Any]:
		"""Convert model instance to dictionary"""
		return {
			'id': self.id,
			'name': self.name,
			'quantity': self.quantity,
			'updated_at': self.updated_at.isoformat() if self.updated_at else None
		}

	def __repr__(self):
		return f'<Inventory {self.name}: {self.quantity}>'
