class ApiClient {
    constructor(baseURL = '') {
        this.baseURL = baseURL;
    }

    async get(endpoint) {
        const response = await fetch(`${this.baseURL}${endpoint}`);
        if (!response.ok) {
            const text = await response.text();
            throw new Error(text);
        }
        return response.json();
    }

    async post(endpoint, data = {}) {
        const response = await fetch(`${this.baseURL}${endpoint}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        });
        if (!response.ok) {
            const text = await response.text();
            throw new Error(text);
        }
        return response.json();
    }

    async put(endpoint, data) {
        const response = await fetch(`${this.baseURL}${endpoint}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        });
        if (!response.ok) {
            const text = await response.text();
            throw new Error(text);
        }
        return response.json();
    }

    async delete(endpoint) {
        const response = await fetch(`${this.baseURL}${endpoint}`, {
            method: 'DELETE',
        });
        if (!response.ok) {
            const text = await response.text();
            throw new Error(text);
        }
        return response.json();
    }

    async uploadFile(endpoint, file) {
        const formData = new FormData();
        formData.append('file', file);
        const response = await fetch(`${this.baseURL}${endpoint}`, {
            method: 'POST',
            body: formData,
        });
        if (!response.ok) {
            const text = await response.text();
            throw new Error(text);
        }
        return response.json();
    }

    async downloadFile(endpoint, filename) {
        const response = await fetch(`${this.baseURL}${endpoint}`);
        if (!response.ok) {
            const text = await response.text();
            throw new Error(text);
        }
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
    }
}

const api = new ApiClient('/api');
