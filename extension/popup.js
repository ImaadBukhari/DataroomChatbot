const API_BASE = 'https://dataroom-chatbot-604369366615.us-central1.run.app';

class DataroomChatbot {
    constructor() {
        this.elements = {
            status: document.getElementById('status'),
            statusIndicator: document.getElementById('statusIndicator'),
            statusText: document.getElementById('statusText'),
            updateBtn: document.getElementById('updateBtn'),
            updateSpinner: document.getElementById('updateSpinner'),
            messages: document.getElementById('messages'),
            messageInput: document.getElementById('messageInput'),
            sendBtn: document.getElementById('sendBtn'),
            fileCount: document.getElementById('fileCount')
        };
        
        this.init();
    }
    
    async init() {
        this.bindEvents();
        await this.checkStatus();
    }
    
    bindEvents() {
        this.elements.updateBtn.addEventListener('click', () => this.updateDataroom());
        this.elements.sendBtn.addEventListener('click', () => this.sendMessage());
        this.elements.messageInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });
    }
    
    async checkStatus() {
        try {
            const response = await fetch(`${API_BASE}/status`);
            const data = await response.json();
            
            this.updateStatusUI(data);
            
        } catch (error) {
            console.error('Error checking status:', error);
            this.updateStatusUI({ 
                status: 'error', 
                indexed_files: 0,
                index_exists: false 
            });
        }
    }
    
    updateStatusUI(status) {
        const { statusIndicator, statusText, updateBtn, messageInput, sendBtn, fileCount } = this.elements;
        
        // Update status indicator
        statusIndicator.className = 'status-indicator';
        if (status.status === 'ready') {
            statusIndicator.classList.add('ready');
            statusText.textContent = 'Ready';
        } else if (status.status === 'error') {
            statusIndicator.classList.add('error');
            statusText.textContent = 'Error connecting to backend';
        } else {
            statusText.textContent = 'Needs update';
        }
        
        // Update file count
        const fileText = status.indexed_files === 1 ? 'file' : 'files';
        fileCount.textContent = `${status.indexed_files} ${fileText} indexed`;
        
        // Enable/disable controls
        const isReady = status.status === 'ready';
        const canUpdate = status.status !== 'error';
        
        updateBtn.disabled = !canUpdate;
        messageInput.disabled = !isReady;
        sendBtn.disabled = !isReady;
        
        if (isReady) {
            messageInput.placeholder = 'Ask a question about your dataroom...';
        } else {
            messageInput.placeholder = 'Update dataroom first...';
        }
    }
    
    async updateDataroom() {
        const { updateBtn, updateSpinner } = this.elements;
        
        try {
            // Show loading state
            updateBtn.disabled = true;
            updateSpinner.classList.add('active');
            this.elements.statusText.textContent = 'Updating...';
            
            const response = await fetch(`${API_BASE}/update`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            
            const data = await response.json();
            
            if (response.ok) {
                this.addMessage(`Successfully updated! Processed ${data.files_processed} files.`, 'bot');
                await this.checkStatus();
            } else {
                throw new Error(data.detail || 'Update failed');
            }
            
        } catch (error) {
            console.error('Error updating dataroom:', error);
            this.addMessage(`Error updating dataroom: ${error.message}`, 'bot');
            this.elements.statusText.textContent = 'Update failed';
        } finally {
            updateBtn.disabled = false;
            updateSpinner.classList.remove('active');
        }
    }
    
    async sendMessage() {
        const { messageInput, sendBtn } = this.elements;
        const message = messageInput.value.trim();
        
        if (!message) return;
        
        // Add user message
        this.addMessage(message, 'user');
        messageInput.value = '';
        
        // Show loading state
        sendBtn.disabled = true;
        const loadingMessage = this.addMessage('Thinking...', 'bot');
        
        try {
            const response = await fetch(`${API_BASE}/chat`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ message })
            });
            
            const data = await response.json();
            
            // Remove loading message
            loadingMessage.remove();
            
            if (response.ok) {
                this.addMessage(data.response, 'bot', data.sources);
            } else {
                throw new Error(data.detail || 'Chat failed');
            }
            
        } catch (error) {
            console.error('Error sending message:', error);
            loadingMessage.querySelector('.message-content').textContent = 
                `Error: ${error.message}`;
        } finally {
            sendBtn.disabled = false;
        }
    }
    
    addMessage(content, type, sources = []) {
        const { messages } = this.elements;
        
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${type}-message`;
        
        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        contentDiv.textContent = content;
        
        messageDiv.appendChild(contentDiv);
        
        // Add sources if provided
        if (sources && sources.length > 0) {
            const sourcesDiv = document.createElement('div');
            sourcesDiv.className = 'sources';
            sourcesDiv.textContent = `Sources: ${sources.join(', ')}`;
            messageDiv.appendChild(sourcesDiv);
        }
        
        messages.appendChild(messageDiv);
        messages.scrollTop = messages.scrollHeight;
        
        return messageDiv;
    }
}

// Initialize the chatbot when the popup loads
document.addEventListener('DOMContentLoaded', () => {
    new DataroomChatbot();
});