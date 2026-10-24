import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 60000
})

// 自动附加认证 Token（针对 Docker 环境网页密码访问）
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('ymlmanage_token')
  if (token) {
    config.headers['Authorization'] = `Bearer ${token}`
    config.headers['X-Auth-Token'] = token
  }
  return config
}, (error) => Promise.reject(error))

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response && error.response.status === 401) {
      // 忽略检查登录状态自身的 401
      if (!error.config.url.includes('/auth/login') && !error.config.url.includes('/auth/status')) {
        localStorage.removeItem('ymlmanage_token')
        if (window.__handleAuthExpired) {
          window.__handleAuthExpired()
        }
      }
    }
    return Promise.reject(error)
  }
)

// 认证与安全相关 API (Docker 访问密码控制)
export const getAuthStatus = () => api.get('/auth/status')
export const initAuth = (password, confirm_password) => api.post('/auth/init', { password, confirm_password })
export const loginAuth = (password) => api.post('/auth/login', { password })
export const logoutAuth = () => api.post('/auth/logout')
export const changePassword = (data) => api.post('/auth/change-password', data)

export const getProfiles = () => api.get('/profiles')
export const getProfileDetail = (name) => api.get(`/profiles/${name}`)
export const downloadProfile = (data) => api.post('/profiles/download', data)
export const uploadProfile = (formData) => api.post('/profiles/upload', formData, {
  headers: { 'Content-Type': 'multipart/form-data' }
})
export const createDefaultProfile = (name) => api.post(`/profiles/create-default?name=${encodeURIComponent(name || 'master')}`)
export const deleteProfile = (name) => api.delete(`/profiles/${name}`)
export const getRawYaml = (name) => api.get(`/profiles/${encodeURIComponent(name)}/raw`)
export const saveRawYaml = (name, content) => api.put(`/profiles/${encodeURIComponent(name)}/raw`, { content })
export const getProfileStructure = (name) => api.get(`/profiles/${encodeURIComponent(name)}/structure`)
export const saveProfileStructure = (name, data) => api.put(`/profiles/${encodeURIComponent(name)}/structure`, data)
export const previewProfileYaml = (name, data) => api.post(`/profiles/${encodeURIComponent(name)}/preview-yaml`, data)
export const parseYamlText = (content) => api.post('/profiles/parse-yaml', { content })
export const parseNodeLink = (link) => api.post('/profiles/parse-node', { link })
export const getBackups = (name) => api.get(`/profiles/${name}/backups`)
export const restoreBackup = (name, backup_filename) => api.post(`/profiles/${name}/restore`, { backup_filename })
export const deleteBackup = (name, backup_filename) => api.delete(`/profiles/${name}/backups/${encodeURIComponent(backup_filename)}`)

export const getSources = () => api.get('/sources')
export const addSource = (data) => api.post('/sources', data)
export const updateSource = (id, data) => api.put(`/sources/${id}`, data)
export const deleteSource = (id) => api.delete(`/sources/${id}`)

export const fetchNodes = (data) => api.post('/nodes/fetch', data)
export const fetchNodesStream = (data, signal) => {
  const headers = { 'Content-Type': 'application/json' }
  const token = localStorage.getItem('ymlmanage_token')
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
    headers['X-Auth-Token'] = token
  }
  return fetch('/api/nodes/fetch-stream', {
    method: 'POST',
    headers,
    body: JSON.stringify(data),
    signal
  })
}
export const importNodes = (data) => api.post('/nodes/import', data)
export const testNodesDelay = (data) => api.post('/nodes/test-delays', data)

// 测速与测延迟接口相关 API
export const getTestUrls = () => api.get('/profiles/test-urls')
export const updateProfileTestUrl = (name, test_url) => api.post(`/profiles/${name}/update-test-url`, { test_url })
export const getSystemInfo = () => api.get('/profiles/system-info')

// 远程同步与上传 API (SMB / FTP / WebDAV)
export const getRemoteTargets = () => api.get('/remote/targets')
export const saveRemoteTarget = (data) => api.post('/remote/targets', data)
export const deleteRemoteTarget = (id) => api.delete(`/remote/targets/${id}`)
export const testRemoteConnection = (data) => api.post('/remote/test', data)
export const uploadProfileToRemote = (data) => api.post('/remote/upload', data)
