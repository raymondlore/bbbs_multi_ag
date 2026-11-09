// 비밀번호 안내 화면 (등록 201 직후 1회). 비밀번호는 JS 메모리에만 두고 어디에도 저장하지 않는다.
import { h, state } from '../util.js';

export function noticeView(root, project, password) {
  state.guardUnload = true;
  let pw = password;
  const input = h('input', {
    type: 'text', class: 'password-display', value: pw, readOnly: true,
    id: 'issued-password', 'aria-label': '발급된 수정용 비밀번호', autocomplete: 'off',
  });
  const copyMsg = h('p', { class: 'hint', role: 'status' });
  const copyBtn = h('button', {
    type: 'button', class: 'btn', text: '복사',
    onClick: async () => {
      input.focus();
      input.select();
      let ok = false;
      try {
        if (navigator.clipboard && window.isSecureContext) {
          await navigator.clipboard.writeText(pw);
          ok = true;
        }
      } catch { ok = false; }
      if (!ok) {
        try { ok = document.execCommand('copy'); } catch { ok = false; }
      }
      copyMsg.textContent = ok ? '복사했습니다.' : '자동 복사가 되지 않았습니다. 선택된 비밀번호를 직접 복사하세요.';
    },
  });
  const detailBtn = h('button', {
    type: 'button', class: 'btn btn-primary', text: '상세 보기', disabled: true,
    onClick: () => {
      state.guardUnload = false;
      location.hash = `#/projects/${project.id}`;
    },
  });
  const check = h('input', {
    type: 'checkbox', id: 'saved-check',
    onChange: () => { detailBtn.disabled = !check.checked; },
  });

  root.replaceChildren(
    h('div', { class: 'panel' },
      h('h1', { text: '과제를 등록했습니다', tabindex: '-1' }),
      h('p', { text: `"${project.title}" 과제가 등록되었습니다. 아래 수정용 비밀번호를 지금 보관하세요.` }),
      h('div', { class: 'notice-box' },
        h('strong', { text: '이 비밀번호는 다시 볼 수 없습니다.' }),
        h('p', { text: '분실하면 과제를 수정하거나 삭제할 수 없습니다. 이 화면을 새로고침하거나 벗어나면 사라집니다.' })),
      h('label', { for: 'issued-password', text: '수정용 비밀번호' }),
      h('div', { class: 'password-row' }, input, copyBtn),
      copyMsg,
      h('div', { class: 'check-row' }, check,
        h('label', { for: 'saved-check', text: '비밀번호를 안전한 곳에 보관했습니다.' })),
      h('div', { class: 'btn-row' }, detailBtn)));
  input.focus();
  input.select();

  // 화면을 떠나면 메모리의 비밀번호도 버린다
  return () => { pw = ''; input.value = ''; state.guardUnload = false; };
}
