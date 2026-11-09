// API 클라이언트 (docs/api.md 기준). 모든 오류는 ApiError로 던진다.
const BASE = '/api/v1';

export class ApiError extends Error {
  constructor(status, code, message, retryAfter = null) {
    super(message);
    this.status = status;
    this.code = code;
    this.retryAfter = retryAfter; // 초 단위(429일 때)
  }
}

async function request(path, { method = 'GET', body, password } = {}) {
  const headers = {};
  if (password !== undefined) {
    // 헤더는 ASCII만 가능. 서버 발급 비밀번호는 ASCII이므로 그 외는 불일치로 처리
    if (!/^[\x20-\x7E]*$/.test(password)) {
      throw new ApiError(403, 'PASSWORD_MISMATCH', '비밀번호가 일치하지 않습니다.');
    }
    headers['X-Edit-Password'] = password;
  }
  let res;
  try {
    res = await fetch(BASE + path, { method, body, headers });
  } catch {
    throw new ApiError(0, 'NETWORK_ERROR', '서버에 연결할 수 없습니다. 잠시 후 다시 시도하세요.');
  }
  if (res.status === 204) return null;
  let data = null;
  try {
    data = await res.json();
  } catch {
    data = null;
  }
  if (!res.ok) {
    const err = (data && data.error) || {};
    const ra = parseInt(res.headers.get('Retry-After') || '', 10);
    throw new ApiError(
      res.status,
      err.code || 'UNKNOWN_ERROR',
      err.message || '요청을 처리하지 못했습니다.',
      Number.isFinite(ra) ? ra : null,
    );
  }
  return data;
}

export function listProjects({ page = 1, q = '', tag = '' } = {}) {
  const p = new URLSearchParams({ page: String(page) });
  if (q) p.set('q', q);
  if (tag) p.set('tag', tag);
  return request(`/projects?${p}`);
}

export const listTags = () => request('/tags');
export const getProject = (id) => request(`/projects/${encodeURIComponent(id)}`); // project 객체 자체를 반환
export const createProject = (formData) => request('/projects', { method: 'POST', body: formData });
export const updateProject = (id, formData, password) =>
  request(`/projects/${encodeURIComponent(id)}`, { method: 'PUT', body: formData, password });
export const deleteProject = (id, password) =>
  request(`/projects/${encodeURIComponent(id)}`, { method: 'DELETE', password });
