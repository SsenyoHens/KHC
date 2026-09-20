const API_BASE_URL = 'http://localhost:8000/api';

export async function apiRequest(path, options = {}) {
  const token = localStorage.getItem('saad_token');

  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {}),
  };

  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(errorText || 'Request failed');
  }

  return response.json();
}

export default API_BASE_URL;
