class AutoZoneChatbot {
    constructor() {
        this.messagesContainer = document.getElementById('chatbotMessages');
        this.input = document.getElementById('chatInput');
        this.sendBtn = document.getElementById('chatSend');
        this.fab = document.getElementById('chatbotFab');
        this.window = document.getElementById('chatbotWindow');
        this.suggestions = document.getElementById('chatbotSuggestions');
        this.isOpen = false;
        this.isLoading = false;
        this.userType = 'public';
        this.init();
    }

    init() {
        if (!this.messagesContainer) {
            console.log('Chatbot: messages container not found');
            return;
        }
        console.log('Chatbot: initializing...');
        
        this.fab.addEventListener('click', () => this.toggle());
        
        const closeBtn = document.getElementById('chatbotClose');
        if (closeBtn) {
            closeBtn.addEventListener('click', () => this.toggle());
        }
        
        this.sendBtn.addEventListener('click', () => this.sendMessage());
        
        this.input.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });
        
        this.suggestions.addEventListener('click', (e) => {
            if (e.target.classList.contains('suggestion-btn')) {
                const question = e.target.dataset.question;
                this.input.value = question;
                this.sendMessage();
            }
        });
        
        console.log('Chatbot: initialized successfully');
    }

    toggle() {
        console.log('Chatbot: toggle clicked, isOpen:', this.isOpen);
        this.isOpen = !this.isOpen;
        this.fab.classList.toggle('active', this.isOpen);
        this.window.classList.toggle('active', this.isOpen);
        if (this.isOpen) {
            this.input.focus();
        }
    }

    async sendMessage() {
        const message = this.input.value.trim();
        if (!message || this.isLoading) return;
        
        this.input.value = '';
        this.isLoading = true;
        this.sendBtn.disabled = true;
        
        this.addMessage(message, 'user');
        this.showTyping();
        
        try {
            const response = await fetch('/api/chatbot/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCsrfToken()
                },
                body: JSON.stringify({question: message, user_type: this.userType})
            });
            
            const data = await response.json();
            this.hideTyping();
            
            if (data.error && !data.answer) {
                this.addMessage('Error occurred. Please try again.', 'bot');
            } else {
                this.addMessage(data.answer, 'bot');
            }
        } catch (error) {
            this.hideTyping();
            this.addMessage('Connection error. Please try again.', 'bot');
        }
        
        this.isLoading = false;
        this.sendBtn.disabled = false;
    }

    addMessage(content, type) {
        const div = document.createElement('div');
        div.className = 'message ' + type + '-message';
        
        const icon = type === 'bot' ? 'fa-robot' : 'fa-user';
        const avatarHtml = '<div class="message-avatar"><i class="fas ' + icon + '"></i></div>';
        const contentHtml = '<div class="message-content">' + this.formatContent(content) + '</div>';
        
        div.innerHTML = avatarHtml + contentHtml;
        this.messagesContainer.appendChild(div);
        this.scrollToBottom();
    }

    formatContent(content) {
        return content
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\n/g, '<br>');
    }

    showTyping() {
        const div = document.createElement('div');
        div.className = 'message bot-message';
        div.id = 'typingIndicator';
        div.innerHTML = '<div class="message-avatar"><i class="fas fa-robot"></i></div><div class="message-content"><div class="typing-indicator"><span></span><span></span><span></span></div></div>';
        this.messagesContainer.appendChild(div);
        this.scrollToBottom();
    }

    hideTyping() {
        const el = document.getElementById('typingIndicator');
        if (el) el.remove();
    }

    scrollToBottom() {
        this.messagesContainer.scrollTop = this.messagesContainer.scrollHeight;
    }

    getCsrfToken() {
        const name = 'csrftoken';
        let cookieValue = null;
        if (document.cookie) {
            const cookies = document.cookie.split(';');
            for (let c of cookies) {
                c = c.trim();
                if (c.substring(0, name.length + 1) === name + '=') {
                    cookieValue = decodeURIComponent(c.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }
}

document.addEventListener('DOMContentLoaded', function() {
    console.log('Chatbot: DOM loaded');
    if (document.getElementById('chatbotFab')) {
        console.log('Chatbot: FAB found, creating instance');
        window.autoZoneChatbot = new AutoZoneChatbot();
    } else {
        console.log('Chatbot: FAB not found');
    }
});
