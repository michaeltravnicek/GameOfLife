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

// Multipart helper — axios sets the boundary itself when given FormData.
const MULTIPART = { headers: { 'Content-Type': 'multipart/form-data' } };

// --- Auth ---
export const fetchMe = () => api.get('/auth/me/').then((r) => r.data);
export const apiLogin = (identifier, password, remember = false) =>
  api.post('/auth/login/', { identifier, password, remember }).then((r) => r.data);
export const apiLogout = () => api.post('/auth/logout/').then((r) => r.data);
export const apiRegister = (payload) =>
  api.post('/auth/register/', payload).then((r) => r.data);
export const apiPasswordReset = (email) =>
  api.post('/auth/password-reset/', { email }).then((r) => r.data);
export const apiPasswordResetConfirm = (uid, token, newPassword) =>
  api.post('/auth/password-reset/confirm/', { uid, token, new_password: newPassword })
    .then((r) => r.data);
export const updateProfile = (formData) =>
  api.patch('/auth/profile/update/', formData, MULTIPART).then((r) => r.data);
export const uploadAvatar = (file) => {
  const fd = new FormData();
  fd.append('photo', file);
  return api.post('/auth/profile/photo/', fd, MULTIPART).then((r) => r.data);
};

// --- Public profiles ---
export const fetchProfile = (username) =>
  api.get(`/profiles/${username}/`).then((r) => r.data);
export const fetchProfileSeason = (username, seasonId) =>
  api.get(`/profiles/${username}/seasons/${seasonId}/`).then((r) => r.data);

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
export const uploadEventImages = (slug, files) => {
  const fd = new FormData();
  Array.from(files).forEach((f) => fd.append('images', f));
  return api.post(`/events/${slug}/images/`, fd, MULTIPART).then((r) => r.data);
};

// --- Leaderboard / Seasons / Players ---
export const fetchLeaderboard = (seasonId = 'active', { limit } = {}) =>
  api.get('/leaderboard/', { params: { season_id: seasonId, ...(limit ? { limit } : {}) } })
    .then((r) => r.data);
export const fetchSeasons = () => api.get('/seasons/').then((r) => r.data);
export const fetchPlayer = (userId) =>
  api.get(`/players/${userId}/`).then((r) => r.data);

// --- Home (split endpoints; the old /home/ no longer exists) ---
export const fetchHero = () => api.get('/hero/').then((r) => r.data);
export const fetchStats = () => api.get('/stats/').then((r) => r.data);
export const fetchCheckinEvents = () => api.get('/checkin-events/').then((r) => r.data);

// --- Gallery / Categories ---
export const fetchGallery = (params = {}) =>
  api.get('/gallery/', { params }).then((r) => r.data);
export const fetchCategories = () =>
  api.get('/categories/').then((r) => r.data);
export const uploadGalleryPhoto = ({ image, event = '', caption = '' }) => {
  const fd = new FormData();
  fd.append('image', image);
  if (event) fd.append('event', event);
  if (caption) fd.append('caption', caption);
  return api.post('/photos/', fd, MULTIPART).then((r) => r.data);
};
export const togglePhotoLike = (photoId) =>
  api.post(`/photos/${photoId}/like/`).then((r) => r.data);

// --- Admin ---
export const fetchAdminFeedbacks = () =>
  api.get('/admin/feedbacks/').then((r) => r.data);
