// 상세 화면과 삭제 다이얼로그
import { h, clear, formatDate, safeHttpUrl, state } from '../util.js';
import { getProject, deleteProject } from '../api.js';
import { toast, loadingBox, stateBox, showError, passwordErrorMessage, lockFor } from '../ui.js';

function linkRow(label, value) {
  if (!value) return [];
  const href = safeHttpUrl(value);
  const dd = href
    ? h('a', { href, target: '_blank', rel: 'noopener noreferrer', text: value })
    : h('span', { text: value }); // http/https가 아니면 링크로 만들지 않는다
  return [h('dt', { text: label }), h('dd', {}, dd)];
}

export async function detailView(root, ctx) {
  const cleanups = [];
  root.appendChild(loadingBox());

  async function load() {
    clear(root);
    root.appendChild(loadingBox());
    try {
      const p = await getProject(ctx.id);
      if (!ctx.alive()) return;
      render(p);
    } catch (err) {
      if (!ctx.alive()) return;
      clear(root);
      if (err.status === 404) {
        root.appendChild(stateBox('empty', '과제를 찾을 수 없습니다. 삭제되었거나 없는 과제입니다.',
          [h('a', { class: 'btn', href: state.lastList, text: '목록으로' })]));
      } else {
        showError(root, err, load);
      }
    }
  }

  function render(p) {
    document.title = `${p.title} - AI 과제 게시판`;
    const deleteBtn = h('button', { type: 'button', class: 'btn btn-danger', text: '삭제' });
    deleteBtn.addEventListener('click', () => cleanups.push(openDeleteDialog(p, deleteBtn, ctx)));
    const tags = p.tags && p.tags.length
      ? h('ul', { class: 'chips', 'aria-label': '태그' }, p.tags.map((t) => h('li', { class: 'chip', text: t })))
      : null;
    clear(root);
    root.appendChild(h('article', { class: 'panel' },
      h('h1', { class: 'detail-title', tabindex: '-1', text: p.title }),
      tags,
      p.image_url ? h('div', { class: 'detail-image' }, h('img', { src: p.image_url, alt: `${p.title} 스크린샷` })) : null,
      h('p', { class: 'detail-desc', text: p.description }),
      h('dl', { class: 'info-list' },
        h('dt', { text: '작성자' }), h('dd', { text: p.author }),
        linkRow('배포 URL', p.deploy_url),
        linkRow('저장소 URL', p.repo_url),
        h('dt', { text: '등록일' }), h('dd', { text: formatDate(p.created_at) }),
        p.updated_at && p.updated_at !== p.created_at
          ? [h('dt', { text: '수정일' }), h('dd', { text: formatDate(p.updated_at) })] : null),
      h('div', { class: 'detail-actions' },
        h('a', { class: 'btn', href: state.lastList, text: '목록으로' }),
        h('span', { class: 'spacer' }),
        h('a', { class: 'btn', href: `#/projects/${p.id}/edit`, text: '수정' }),
        deleteBtn)));
  }

  await load();
  return () => cleanups.forEach((fn) => fn());
}

// 삭제 확인 다이얼로그. 403이면 유지하고 재입력을 허용한다. 닫을 때 호출할 정리 함수를 반환
function openDeleteDialog(p, opener, ctx) {
  let stopLock = null;
  const pw = h('input', { type: 'password', id: 'delete-password', autocomplete: 'new-password' });
  const err = h('p', { class: 'field-error', role: 'alert', hidden: true });
  const cancel = h('button', { type: 'button', class: 'btn', text: '취소' });
  const confirm = h('button', { type: 'submit', class: 'btn btn-danger', text: '삭제' });
  let busy = false;

  const form = h('form', {
    novalidate: true,
    onSubmit: async (e) => {
      e.preventDefault();
      if (busy) return;
      err.hidden = true;
      if (!pw.value) { showErr('비밀번호를 입력하세요.'); pw.focus(); return; }
      busy = true;
      confirm.disabled = true;
      try {
        await deleteProject(p.id, pw.value);
        close(false);
        toast('과제를 삭제했습니다.', 'success');
        location.hash = state.lastList;
      } catch (ex) {
        if (ex.status === 404) {
          close(false);
          toast('이미 삭제된 과제입니다.', 'error');
          location.hash = state.lastList;
          return;
        }
        showErr(passwordErrorMessage(ex) || ex.message);
        if (ex.status === 429) {
          stopLock = lockFor(ex.retryAfter, [pw, confirm]);
        } else {
          confirm.disabled = false;
          pw.select();
          pw.focus();
        }
      } finally {
        busy = false;
      }
    },
  },
  h('label', { for: 'delete-password', text: '수정용 비밀번호' }), pw, err,
  h('div', { class: 'btn-row dialog-actions' }, confirm, cancel));

  function showErr(msg) { err.textContent = msg; err.hidden = false; }

  const overlay = h('div', { class: 'overlay' },
    h('div', { class: 'dialog', role: 'dialog', 'aria-modal': 'true', 'aria-labelledby': 'delete-title' },
      h('h2', { id: 'delete-title', text: '과제를 삭제할까요?' }),
      h('p', { text: `"${p.title}" 과제를 삭제하면 되돌릴 수 없습니다. 등록할 때 받은 수정용 비밀번호를 입력하세요.` }),
      form));

  function onKey(e) {
    if (e.key === 'Escape') { close(true); return; }
    if (e.key !== 'Tab') return;
    // 포커스를 다이얼로그 안에 가둔다
    const items = [...overlay.querySelectorAll('input, button')].filter((el) => !el.disabled);
    if (!items.length) return;
    const first = items[0];
    const last = items[items.length - 1];
    if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
  }
  function close(restoreFocus) {
    document.removeEventListener('keydown', onKey);
    if (stopLock) stopLock();
    overlay.remove();
    if (restoreFocus && opener.isConnected) opener.focus();
  }
  cancel.addEventListener('click', () => close(true));
  overlay.addEventListener('mousedown', (e) => { if (e.target === overlay) close(true); });
  document.addEventListener('keydown', onKey);
  document.body.appendChild(overlay);
  pw.focus();
  return () => close(false);
}
