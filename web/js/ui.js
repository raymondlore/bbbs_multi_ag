// 공통 UI: 토스트, 오류 박스, 비밀번호 오류 문구
import { h, clear } from './util.js';

export function toast(message, kind = 'info') {
  const box = document.getElementById('toasts');
  const item = h('div', { class: `toast toast-${kind}`, text: message });
  box.appendChild(item);
  setTimeout(() => item.remove(), 4500);
}

// 로딩·빈·오류 상태 박스
export function stateBox(kind, message, actions = []) {
  return h('div', { class: `state-box state-${kind}`, role: kind === 'error' ? 'alert' : null },
    h('p', { text: message }), actions.length ? h('div', { class: 'state-actions' }, actions) : null);
}

export function loadingBox() {
  return stateBox('loading', '불러오는 중입니다…');
}

export function showError(container, err, retry) {
  clear(container);
  const actions = retry ? [h('button', { type: 'button', class: 'btn', text: '다시 시도', onClick: retry })] : [];
  container.appendChild(stateBox('error', err.message || '오류가 발생했습니다.', actions));
}

// 비밀번호 관련 오류(401/403/429)를 사용자 문구로 변환. 해당 없으면 null
export function passwordErrorMessage(err) {
  if (err.status === 401) return '비밀번호를 입력하세요.';
  if (err.status === 403) return '비밀번호가 일치하지 않습니다.';
  if (err.status === 429) {
    const minutes = err.retryAfter ? Math.max(1, Math.ceil(err.retryAfter / 60)) : 15;
    return `시도 횟수를 초과했습니다. 잠시 후(약 ${minutes}분) 다시 시도하세요.`;
  }
  return null;
}

// 429 잠금 시간 동안 요소를 비활성화하고, 해제 타이머 정리 함수를 반환
export function lockFor(seconds, elements) {
  elements.forEach((el) => { el.disabled = true; });
  const timer = setTimeout(() => elements.forEach((el) => { el.disabled = false; }), (seconds || 900) * 1000);
  return () => clearTimeout(timer);
}
