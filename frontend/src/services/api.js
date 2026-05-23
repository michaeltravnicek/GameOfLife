import axios from 'axios';

function readCookie(name) {
  const match = document.cookie.match(new RegExp('(^| )' + name + '=([^;]+)'));
  return match ? decodeURIComponent(match[2]) : null;
}

const api = axios.create({
  baseURL: '/api',
  withCredentials: true,
  xsrfCookieName: 'csrftoken',
  xsrfHeaderName: 'X-CSRFToken',
});

// Make sure the CSRF token is sent on every unsafe request, even when axios's
// xsrfCookieName fallback isn't enough (e.g., cross-origin in dev).
api.interceptors.request.use((config) => {
  const method = (config.method || 'get').toLowerCase();
  if (['post', 'put', 'patch', 'delete'].includes(method)) {
    const token = readCookie('csrftoken');
    if (token) config.headers['X-CSRFToken'] = token;
  }
  return config;
});

export default api;

// --- Auth ---
export const fetchMe = () => api.get('/auth/me/').then((r) => r.data);
export const apiLogin = (identifier, password, remember = false) =>
  api.post('/auth/login/', { identifier, password, remember }).then((r) => r.data);
export const apiLogout = () => api.post('/auth/logout/').then((r) => r.data);
export const apiRegister = (payload) =>
  api.post('/auth/register/', payload).then((r) => r.data);
export const apiPasswordReset = (email) =>
  api.post('/auth/password-reset/', { email }).then((r) => r.data);
export const fetchProfile = (username) =>
  api.get(`/auth/profile/${username}/`).then((r) => r.data);
export const updateProfile = (formData) =>
  api.patch('/auth/profile/update/', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }).then((r) => r.data);

// --- Events ---
export const fetchEvents = (params = {}) =>
  api.get('/events/', { params }).then((r) => r.data);
export const fetchEventDetail = (slug) =>
  api.get(`/events/${slug}/`).then((r) => r.data);
export const toggleRsvp = (slug) =>
  api.post(`/events/${slug}/rsvp/`).then((r) => r.data);
export const submitFeedback = (slug, rating, comment) =>
  api.post(`/events/${slug}/feedback/`, { rating, comment }).then((r) => r.data);
export const apiCheckin = (slug, latitude, longitude) =>
  api.post(`/events/${slug}/checkin/`, { latitude, longitude }).then((r) => r.data);

// --- Leaderboard / Home / Gallery ---
export const fetchLeaderboard = (period = 'total') =>
  api.get('/leaderboard/', { params: { period } }).then((r) => r.data);
export const fetchHome = () => api.get('/home/').then((r) => r.data);
export const fetchGallery = (params = {}) =>
  api.get('/gallery/', { params }).then((r) => r.data);
export const fetchCategories = () =>
  api.get('/categories/').then((r) => r.data);
