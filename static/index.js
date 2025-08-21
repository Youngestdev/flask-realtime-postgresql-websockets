class InventoryApp {
	constructor() {
		this.socket = null;
		this.inventoryItems = new Map();
		this.isConnected = false;
		this.pendingUpdates = new Set();
		this.init();
	}

	init() {
		this.setupEventListeners();
		this.connectSocket();
		this.loadInitialData();
	}

	setupEventListeners() {
		const form = document.getElementById('add-item-form');
		form.addEventListener('submit', (e) => this.handleAddItem(e));
	}

	connectSocket() {
		// Initialize Socket.IO connection
		this.socket = io();

		this.socket.on('connect', () => {
			console.log('Connected to server');
			this.updateConnectionStatus(true);
		});

		this.socket.on('disconnect', () => {
			console.log('Disconnected from server');
			this.updateConnectionStatus(false);
		});

		this.socket.on('inventory_update', (data) => {
			console.log('Received inventory update:', data);
			this.handleSocketMessage(data);
		});

		this.socket.on('connection_status', (data) => {
			console.log('Connection status:', data);
		});
	}

	updateConnectionStatus(connected) {
		this.isConnected = connected;
		const statusElement = document.getElementById('connection-status');
		if (connected) {
			statusElement.className = 'status connected';
			statusElement.textContent = '🟢 Connected to server';
		} else {
			statusElement.className = 'status disconnected';
			statusElement.textContent = '🔴 Disconnected from server';
		}
	}

	async loadInitialData() {
		try {
			const response = await fetch('/api/inventory');
			if (response.ok) {
				const items = await response.json();
				this.inventoryItems.clear();
				items.forEach(item => {
					this.inventoryItems.set(item.id, item);
				});
				this.renderInventory();
			}
		} catch (error) {
			this.showError('Failed to load inventory data');
		}
	}

	handleSocketMessage(data) {
		const {event, data: itemData} = data;
		switch (event) {
			case 'INSERT':
				this.inventoryItems.set(itemData.id, itemData);
				this.renderInventory();
				this.showNotification(`Added: ${itemData.name}`, 'success');
				break;
			case 'UPDATE':
				this.inventoryItems.set(itemData.id, itemData);
				this.renderInventory();
				this.showNotification(`Updated: ${itemData.name}`, 'info');
				break;
			case 'DELETE':
				this.inventoryItems.delete(itemData.id);
				this.renderInventory();
				this.showNotification(`Deleted: ${itemData.name}`, 'warning');
				break;
			default:
				break;
		}
	}

	async handleAddItem(event) {
		event.preventDefault();
		const nameInput = document.getElementById('item-name');
		const quantityInput = document.getElementById('item-quantity');
		const name = nameInput.value.trim();
		const quantity = parseInt(quantityInput.value);

		if (!name || quantity < 0) {
			this.showError('Please enter a valid item name and quantity');
			return;
		}

		try {
			const response = await fetch('/api/inventory', {
				method: 'POST',
				headers: {'Content-Type': 'application/json'},
				body: JSON.stringify({name, quantity}),
			});

			if (response.ok) {
				nameInput.value = '';
				quantityInput.value = '';
			} else {
				const error = await response.json();
				this.showError(error.error || 'Failed to add item');
			}
		} catch (error) {
			this.showError('Failed to add item');
		}
	}

	async updateItemQuantity(id, newQuantity) {
		if (this.pendingUpdates.has(id)) return;
		this.pendingUpdates.add(id);

		const item = this.inventoryItems.get(id);
		if (item) {
			const originalQuantity = item.quantity;
			item.quantity = newQuantity;
			this.renderInventory();

			try {
				const response = await fetch(`/api/inventory/${id}`, {
					method: 'PUT',
					headers: {'Content-Type': 'application/json'},
					body: JSON.stringify({quantity: newQuantity}),
				});

				if (!response.ok) {
					item.quantity = originalQuantity;
					this.renderInventory();
					const error = await response.json();
					this.showError(error.error || 'Failed to update item');
				}
			} catch (error) {
				item.quantity = originalQuantity;
				this.renderInventory();
				this.showError('Failed to update item');
			} finally {
				this.pendingUpdates.delete(id);
			}
		}
	}

	async deleteItem(id) {
		if (!confirm('Are you sure you want to delete this item?')) return;

		const itemElement = document.querySelector(`[data-item-id="${id}"]`);
		if (itemElement) itemElement.style.opacity = '0.5';

		try {
			const response = await fetch(`/api/inventory/${id}`, {method: 'DELETE'});
			if (!response.ok) {
				if (itemElement) itemElement.style.opacity = '1';
				const error = await response.json();
				this.showError(error.error || 'Failed to delete item');
			}
		} catch (error) {
			if (itemElement) itemElement.style.opacity = '1';
			this.showError('Failed to delete item');
		}
	}

	renderInventory() {
		const container = document.getElementById('inventory-container');
		if (this.inventoryItems.size === 0) {
			container.innerHTML = `
                <div class="empty-state">
                    <h3>No items in inventory</h3>
                    <p>Add your first item using the form above!</p>
                </div>
            `;
			return;
		}

		const sortedItems = Array.from(this.inventoryItems.values())
			.sort((a, b) => new Date(b.updated_at) - new Date(a.updated_at));

		container.innerHTML = sortedItems.map(item => this.renderInventoryItem(item)).join('');
	}

	renderInventoryItem(item) {
		const updatedAt = new Date(item.updated_at).toLocaleString();
		const isUpdating = this.pendingUpdates.has(item.id);
		return `
            <div class="inventory-item ${isUpdating ? 'updating' : ''}" data-item-id="${item.id}">
                <div class="item-info">
                    <div class="item-name">${this.escapeHtml(item.name)}</div>
                    <div class="item-meta">Last updated: ${updatedAt}</div>
                </div>
                <div class="item-actions">
                    <input
                        type="number"
                        class="quantity-input"
                        value="${item.quantity}"
                        min="0"
                        onchange="app.updateItemQuantity(${item.id}, parseInt(this.value))"
                        ${isUpdating ? 'disabled' : ''}
                    >
                    <button
                        class="btn btn-danger btn-small"
                        onclick="app.deleteItem(${item.id})"
                        ${isUpdating ? 'disabled' : ''}
                    >
                        Delete
                    </button>
                </div>
            </div>
        `;
	}

	escapeHtml(text) {
		const div = document.createElement('div');
		div.textContent = text;
		return div.innerHTML;
	}

	showNotification(message, type = 'info') {
		const notification = document.createElement('div');
		notification.className = `notification ${type}`;
		notification.textContent = message;
		notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 12px 20px;
            border-radius: 6px;
            color: white;
            font-weight: 600;
            z-index: 1000;
            animation: slideIn 0.3s ease;
            max-width: 300px;
        `;

		switch (type) {
			case 'success':
				notification.style.background = '#28a745';
				break;
			case 'warning':
				notification.style.background = '#ffc107';
				notification.style.color = '#212529';
				break;
			case 'error':
				notification.style.background = '#dc3545';
				break;
			default:
				notification.style.background = '#17a2b8';
		}

		document.body.appendChild(notification);
		setTimeout(() => {
			notification.style.animation = 'slideOut 0.3s ease';
			setTimeout(() => {
				if (notification.parentNode) {
					notification.parentNode.removeChild(notification);
				}
			}, 300);
		}, 3000);
	}

	showError(message) {
		this.showNotification(message, 'error');
	}
}

// Add CSS animations for notifications
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from {
            transform: translateX(100%);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
    @keyframes slideOut {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(100%);
            opacity: 0;
        }
    }
`;
document.head.appendChild(style);

// Initialize the app
const app = new InventoryApp();