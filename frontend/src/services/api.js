import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

const client = axios.create({
  baseURL: `${API_BASE_URL}/api`,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Automatically attach Bearer token from localStorage to all outgoing API requests
client.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

export const api = {
  // Authentication Endpoints
  signup: async (email, password, name) => {
    const res = await client.post('/auth/signup', { email, password, name });
    return res.data;
  },

  login: async (email, password) => {
    const res = await client.post('/auth/login', { email, password });
    return res.data;
  },

  logout: async () => {
    const res = await client.post('/auth/logout');
    return res.data;
  },

  getMe: async () => {
    const res = await client.get('/auth/me');
    return res.data;
  },

  // Protected Shopping & Voice Commands (Identity resolved strictly from JWT token)
  sendVoiceCommand: async (transcript) => {
    const res = await client.post('/commands', { transcript });
    return res.data;
  },

  getShoppingList: async () => {
    const res = await client.get('/shopping-list');
    return res.data;
  },

  addShoppingItem: async (itemData) => {
    const res = await client.post('/shopping-list/items', itemData);
    return res.data;
  },

  updateShoppingItem: async (itemId, updateData) => {
    const res = await client.patch(`/shopping-list/items/${itemId}`, updateData);
    return res.data;
  },

  resolveItemSize: async (itemId, size) => {
    const res = await client.patch(`/shopping-list/items/${itemId}/size`, { size });
    return res.data;
  },

  deleteShoppingItem: async (itemId) => {
    const res = await client.delete(`/shopping-list/items/${itemId}`);
    return res.data;
  },

  checkoutList: async () => {
    const res = await client.post('/shopping-list/checkout');
    return res.data;
  },

  getSmartSuggestions: async () => {
    const res = await client.get('/suggestions');
    return res.data;
  },

  searchProducts: async (query) => {
    const res = await client.get(`/products/search?q=${encodeURIComponent(query)}`);
    return res.data;
  },

  getProductSizes: async (productId) => {
    const res = await client.get(`/products/${productId}/sizes`);
    return res.data;
  }
};
