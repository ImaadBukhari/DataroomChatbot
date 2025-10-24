const API_BASE = 'https://dataroom-chatbot-bbum6xs6zq-uc.a.run.app';

class DataroomChatbot {
    constructor() {
        this.elements = {
            status: document.getElementById('status'),
            statusIndicator: document.getElementById('statusIndicator'),
            statusText: document.getElementById('statusText'),
            messages: document.getElementById('messages'),
            messageInput: document.getElementById('messageInput'),
            sendBtn: document.getElementById('sendBtn'),
            fileCount: document.getElementById('fileCount')
        };
        
        this.conversationHistory = [];
        this.init();
    }
    
    async init() {
        this.bindEvents();
        await this.checkStatus();
    }
    
    bindEvents() {
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
        const { statusIndicator, statusText, messageInput, sendBtn, fileCount } = this.elements;
        
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
        
        messageInput.disabled = !isReady;
        sendBtn.disabled = !isReady;
        
        if (isReady) {
            messageInput.placeholder = 'Ask a question about your dataroom...';
        } else {
            messageInput.placeholder = 'Backend not ready...';
        }
    }
    
    
    async sendMessage() {
        const { messageInput, sendBtn } = this.elements;
        const message = messageInput.value.trim();
        
        if (!message) return;
        
        // Add user message to conversation history
        this.conversationHistory.push({ role: 'user', content: message });
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
                body: JSON.stringify({ 
                    message,
                    conversation_history: this.conversationHistory
                })
            });
            
            const data = await response.json();
            
            // Remove loading message
            loadingMessage.remove();
            
            if (response.ok) {
                // Add bot response to conversation history
                this.conversationHistory.push({ role: 'assistant', content: data.response });
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
        
        // Parse markdown formatting for bot messages
        if (type === 'bot') {
            contentDiv.innerHTML = this.parseMarkdown(content);
        } else {
            contentDiv.textContent = content;
        }
        
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
    
    parseMarkdown(text) {
        // Simple markdown parser for basic formatting
        let html = text;
        
        // Convert bullet points
        html = html.replace(/^[\s]*[-*]\s+(.+)$/gm, '<li>$1</li>');
        html = html.replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>');
        
        // Convert numbered lists
        html = html.replace(/^[\s]*\d+\.\s+(.+)$/gm, '<li>$1</li>');
        html = html.replace(/(<li>.*<\/li>)/s, '<ol>$1</ol>');
        
        // Convert bold text
        html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
        
        // Convert italic text
        html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');
        
        // Convert line breaks
        html = html.replace(/\n/g, '<br>');
        
        return html;
    }
}

// Initialize the chatbot when the popup loads
document.addEventListener('DOMContentLoaded', () => {
    new DataroomChatbot();
});
