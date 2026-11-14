// 공통 유틸: DOM 생성 헬퍼, 상태, 포맷터. 사용자 입력은 항상 textContent/속성으로만 넣는다.

// 화면 간 공유하는 메모리 상태 (저장소에는 아무것도 저장하지 않는다)
export const state = {
  lastList: '#/', // 마지막 목록 화면 해시(필터 유지용)
  guardUnload: false, // 비밀번호 안내 화면에서 이탈 경고
};

const PROP_KEYS = new Set(['value', 'checked', 'disabled', 'hidden', 'readOnly']);

// h('div', {class:'a', text:'..', onClick: fn}, child, ...)
export function h(tag, props = {}, ...children) {
  const el = document.createElement(tag);
  for (const [key, val] of Object.entries(props || {})) {
    if (val === null || val === undefined || val === false) continue;
    if (key === 'class') el.className = val;
    else if (key === 'text') el.textContent = val;
    else if (key.startsWith('on')) el.addEventListener(key.slice(2).toLowerCase(), val);
    else if (PROP_KEYS.has(key)) el[key] = val;
    else el.setAttribute(key, val === true ? '' : String(val));
  }
  append(el, children);
  return el;
}

function append(el, children) {
  for (const c of children) {
    if (c === null || c === undefined || c === false) continue;
    if (Array.isArray(c)) append(el, c);
    else if (c instanceof Node) el.appendChild(c);
    else el.appendChild(document.createTextNode(String(c)));
  }
}

const SVG_NS = 'http://www.w3.org/2000/svg';

// 이미지 없음 대체용 인라인 SVG (DOM으로 생성)
export function placeholderSvg() {
  const svg = document.createElementNS(SVG_NS, 'svg');
  svg.setAttribute('viewBox', '0 0 64 48');
  svg.setAttribute('aria-hidden', 'true');
  svg.setAttribute('focusable', 'false');
  const rect = document.createElementNS(SVG_NS, 'rect');
  for (const [k, v] of Object.entries({ x: 4, y: 4, width: 56, height: 40, rx: 4, fill: 'none', stroke: 'currentColor', 'stroke-width': 2 })) rect.setAttribute(k, v);
  const path = document.createElementNS(SVG_NS, 'path');
  path.setAttribute('d', 'M8 38 L24 22 L34 32 L42 24 L56 38');
  path.setAttribute('fill', 'none');
  path.setAttribute('stroke', 'currentColor');
  path.setAttribute('stroke-width', '2');
  const circle = document.createElementNS(SVG_NS, 'circle');
  for (const [k, v] of Object.entries({ cx: 20, cy: 15, r: 4, fill: 'currentColor' })) circle.setAttribute(k, v);
  svg.append(rect, path, circle);
  return svg;
}

export function formatDate(iso) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  return d.toLocaleDateString('ko-KR', { year: 'numeric', month: 'long', day: 'numeric' });
}

// http/https 링크만 허용. 아니면 null
export function safeHttpUrl(value) {
  if (typeof value !== 'string' || !value) return null;
  try {
    const u = new URL(value);
    return u.protocol === 'http:' || u.protocol === 'https:' ? u.href : null;
  } catch {
    return null;
  }
}

export function clear(el) {
  el.replaceChildren();
}
