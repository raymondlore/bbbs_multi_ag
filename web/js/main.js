// 앱 진입점: 해시 라우터
import { h, state } from './util.js';
import { stateBox } from './ui.js';
import { listView } from './views/list.js';
import { newView, editView } from './views/form.js';
import { detailView } from './views/detail.js';

const app = document.getElementById('app');
let renderId = 0;
let cleanup = null;

function parseHash() {
  const raw = location.hash.slice(1) || '/';
  const [path, qs = ''] = raw.split('?');
  return { path, query: new URLSearchParams(qs) };
}

function match(path) {
  if (path === '/' || path === '') return { view: listView, title: '과제 목록' };
  if (path === '/new') return { view: newView, title: '과제 등록' };
  let m = path.match(/^\/projects\/(\d+)$/);
  if (m) return { view: detailView, title: '과제 상세', id: m[1] };
  m = path.match(/^\/projects\/(\d+)\/edit$/);
  if (m) return { view: editView, title: '과제 수정', id: m[1] };
  return null;
}

async function render() {
  const id = ++renderId;
  if (cleanup) { try { cleanup(); } catch { /* 무시 */ } cleanup = null; }
  state.guardUnload = false;
  const { path, query } = parseHash();
  app.replaceChildren();
  const route = match(path);
  window.scrollTo(0, 0);
  if (!route) {
    document.title = '찾을 수 없음 - AI 과제 게시판';
    app.appendChild(stateBox('empty', '페이지를 찾을 수 없습니다.', [h('a', { class: 'btn', href: '#/', text: '목록으로' })]));
    return;
  }
  document.title = `${route.title} - AI 과제 게시판`;
  if (path === '/' || path === '') state.lastList = location.hash || '#/';
  const ctx = { id: route.id, query, alive: () => id === renderId };
  const result = await route.view(app, ctx);
  if (typeof result === 'function') {
    if (ctx.alive()) cleanup = result; else result();
  }
}

window.addEventListener('hashchange', render);
// 비밀번호 안내 화면에서 새로고침·탭 닫기 경고
window.addEventListener('beforeunload', (e) => {
  if (state.guardUnload) { e.preventDefault(); e.returnValue = ''; }
});
render();
