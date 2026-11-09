// 목록 화면: 검색, 태그 칩 필터(단일), 페이지네이션. 상태는 해시 쿼리(#/?q=&tag=&page=)에 보존
import { h, clear, placeholderSvg, formatDate } from '../util.js';
import { listProjects, listTags } from '../api.js';
import { stateBox, loadingBox, showError } from '../ui.js';

function parseQuery(query) {
  let page = parseInt(query.get('page') || '1', 10);
  if (!Number.isFinite(page) || page < 1) page = 1;
  return { q: (query.get('q') || '').slice(0, 100), tag: query.get('tag') || '', page };
}

export function listHash({ q = '', tag = '', page = 1 } = {}) {
  const p = new URLSearchParams();
  if (q) p.set('q', q);
  if (tag) p.set('tag', tag);
  if (page > 1) p.set('page', String(page));
  const s = p.toString();
  return s ? `#/?${s}` : '#/';
}

function projectCard(item) {
  const thumb = h('div', { class: 'thumb' });
  if (item.image_url) {
    thumb.appendChild(h('img', { src: item.image_url, alt: item.title, loading: 'lazy' }));
  } else {
    thumb.appendChild(placeholderSvg());
  }
  const tags = item.tags && item.tags.length
    ? h('ul', { class: 'chips', 'aria-label': '태그' }, item.tags.map((t) => h('li', { class: 'chip', text: t })))
    : null;
  return h('li', { class: 'card' },
    h('a', { class: 'card-link', href: `#/projects/${item.id}` },
      thumb,
      h('div', { class: 'card-body' },
        h('h2', { class: 'card-title', text: item.title }),
        h('p', { class: 'card-summary', text: item.summary }),
        tags,
        h('p', { class: 'meta', text: `${item.author} · ${formatDate(item.created_at)}` }))));
}

// 이전/다음 + 번호 최대 5개
function pagination(page, totalPages, make) {
  const nav = h('nav', { class: 'pagination', 'aria-label': '페이지 이동' });
  const link = (label, target, opts = {}) => h('a', {
    class: 'btn', href: make(target), text: label,
    'aria-current': opts.current ? 'page' : null,
    'aria-label': opts.aria || null,
  });
  const disabled = (label) => h('span', { class: 'btn', 'aria-disabled': 'true', text: label });
  nav.appendChild(page > 1 ? link('이전', page - 1) : disabled('이전'));
  let start = Math.max(1, page - 2);
  const end = Math.min(totalPages, start + 4);
  start = Math.max(1, end - 4);
  for (let n = start; n <= end; n += 1) {
    nav.appendChild(link(String(n), n, { current: n === page, aria: `${n}페이지` }));
  }
  nav.appendChild(page < totalPages ? link('다음', page + 1) : disabled('다음'));
  return nav;
}

export async function listView(root, ctx) {
  const cur = parseQuery(ctx.query);
  const go = (next) => { location.hash = listHash(next); };

  const searchInput = h('input', {
    type: 'search', id: 'q', value: cur.q, maxlength: 100,
    placeholder: '과제명·설명 검색', 'aria-label': '과제 검색',
  });
  const searchForm = h('form', {
    class: 'toolbar', role: 'search',
    onSubmit: (e) => { e.preventDefault(); go({ q: searchInput.value.trim(), tag: cur.tag, page: 1 }); },
  }, searchInput, h('button', { type: 'submit', class: 'btn btn-primary', text: '검색' }));

  const tagBox = h('div', { class: 'tag-filter', hidden: true });
  const body = h('div', { 'aria-live': 'polite' });
  root.append(
    h('div', { class: 'page-head' },
      h('h1', { text: 'AI 과제 목록', tabindex: '-1' }),
      h('a', { class: 'btn btn-primary', href: '#/new', text: '과제 등록' })),
    searchForm, tagBox, body);

  function renderTags(tags) {
    const names = tags.map((t) => t.name);
    const list = cur.tag && !names.some((n) => n.toLowerCase() === cur.tag.toLowerCase())
      ? [{ name: cur.tag, count: 0 }, ...tags] : tags;
    clear(tagBox);
    if (!list.length) { tagBox.hidden = true; return; }
    tagBox.hidden = false;
    const ul = h('ul', { class: 'chips', 'aria-label': '태그 필터' });
    for (const t of list) {
      const active = t.name.toLowerCase() === cur.tag.toLowerCase();
      ul.appendChild(h('li', {},
        h('button', {
          type: 'button', class: active ? 'chip chip-active' : 'chip',
          'aria-pressed': active ? 'true' : 'false',
          text: t.count ? `${t.name} (${t.count})` : t.name,
          // 재클릭하면 해제
          onClick: () => go({ q: cur.q, tag: active ? '' : t.name, page: 1 }),
        })));
    }
    tagBox.appendChild(ul);
  }

  function renderItems(data) {
    clear(body);
    const filtered = cur.q || cur.tag;
    if (data.total === 0) {
      if (filtered) {
        body.appendChild(stateBox('empty', '조건에 맞는 과제가 없습니다.',
          [h('a', { class: 'btn', href: '#/', text: '검색·필터 초기화' })]));
      } else {
        body.appendChild(stateBox('empty', '아직 등록된 과제가 없습니다. 첫 과제를 등록해 보세요.',
          [h('a', { class: 'btn btn-primary', href: '#/new', text: '과제 등록' })]));
      }
      return;
    }
    if (!data.items.length) {
      body.appendChild(stateBox('empty', '해당 페이지에 과제가 없습니다.',
        [h('a', { class: 'btn', href: listHash({ q: cur.q, tag: cur.tag, page: 1 }), text: '첫 페이지로' })]));
      return;
    }
    const totalPages = Math.max(1, Math.ceil(data.total / data.page_size));
    body.append(
      h('p', { class: 'result-count', text: `총 ${data.total}건 · ${data.page}/${totalPages} 페이지` }),
      h('ul', { class: 'card-grid' }, data.items.map(projectCard)),
      totalPages > 1 ? pagination(data.page, totalPages, (n) => listHash({ q: cur.q, tag: cur.tag, page: n })) : null);
  }

  async function load() {
    clear(body);
    body.appendChild(loadingBox());
    try {
      const data = await listProjects(cur);
      if (!ctx.alive()) return;
      renderItems(data);
    } catch (err) {
      if (!ctx.alive()) return;
      showError(body, err, load);
    }
  }

  // 태그 목록 실패는 치명적이지 않으므로 필터만 숨긴다
  listTags().then((r) => { if (ctx.alive()) renderTags(r.items || []); }).catch(() => {});
  await load();
}
