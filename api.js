import axios from 'axios'

const api = axios.create({ baseURL: 'http://127.0.0.1:5000/api' })
export const searchProduct = (product) => api.get('/search', { params: { product } })
export const getReviews = (product) => api.get('/reviews', { params: product ? { product } : {} })
export const getAnalytics = (product) => api.get(`/analytics/${encodeURIComponent(product)}`)
export const getProducts = () => api.get('/products')
export const getOverview = () => api.get('/analytics/overview')
export const analyzeSentiment = (text) => api.post('/sentiment/analyze', { text })
export const startScraper = (product) => api.post('/scraper/start', { product })
export const getHistory = () => api.get('/history')
export const getFavorites = () => api.get('/favorites')
export const toggleFavorite = (product) => api.post('/favorites', product)
export default api
