// 등록·수정 폼 (같은 폼 재사용). 클라이언트 검증은 편의용이고 최종 검증은 서버가 한다.
import { h, clear, safeHttpUrl } from '../util.js';
import { getProject, createProject, updateProject } from '../api.js';
import { toast, loadingBox, showError, passwordErrorMessage, lockFor } from '../ui.js';
import { noticeView } from './notice.js';

const LIMIT = { title: 100, description: 2000, author: 30, url: 500, tag: 20, tags: 5, image: 2 * 1024 * 1024 };
const TAG_RE = /^[가-힣ㄱ-ㅎㅏ-ㅣA-Za-z0-9 \-_.#+]+$/;
const IMAGE_TYPES = ['image/png', 'image/jpeg', 'image/webp'];

const normSpace = (s) => s.trim().replace(/\s+/g, ' ');

function validUrl(v) {
  return v.length <= LIMIT.url && !/[\s\x00-\x1f\x7f]/.test(v) && safeHttpUrl(v) !== null;
}

export function newView(root, ctx) {
  return buildForm(root, ctx, null);
}

export async function editView(root, ctx) {
  root.appendChild(loadingBox());
  try {
    const project = await getProject(ctx.id);
    if (!ctx.alive()) return undefined;
    clear(root);
    return buildForm(root, ctx, project);
  } catch (err) {
    if (!ctx.alive()) return undefined;
    clear(root);
    if (err.status === 404) {
      showError(root, { message: '과제를 찾을 수 없습니다. 삭제되었거나 없는 과제입니다.' });
      root.appendChild(h('p', {}, h('a', { class: 'btn', href: '#/', text: '목록으로' })));
    } else {
      showError(root, err, () => { clear(root); editView(root, ctx); });
    }
    return undefined;
  }
}

function field(id, labelText, control, { required = false, hint = null, counter = null } = {}) {
  const err = h('p', { class: 'field-error', id: `${id}-error`, hidden: true });
  return {
    err,
    el: h('div', { class: 'field' },
      h('label', { for: id }, labelText, required ? h('span', { class: 'req', 'aria-hidden': 'true', text: ' *' }) : null),
      control, counter, hint ? h('p', { class: 'hint', id: `${id}-hint`, text: hint }) : null, err),
  };
}

function buildForm(root, ctx, project) {
  const edit = project !== null;
  const objectUrls = [];
  const cleanups = [];
  const tags = edit ? [...(project.tags || [])] : [];
  const img = { file: null, remove: false };

  const topError = h('div', { class: 'form-error', role: 'alert', tabindex: '-1', hidden: true });

  const title = h('input', { type: 'text', id: 'title', maxlength: LIMIT.title, value: edit ? project.title : '', autocomplete: 'off' });
  const description = h('textarea', { id: 'description', maxlength: LIMIT.description });
  description.value = edit ? project.description : '';
  const descCounter = h('div', { class: 'counter', 'aria-hidden': 'true' });
  const updateCounter = () => { descCounter.textContent = `${description.value.length} / ${LIMIT.description}`; };
  description.addEventListener('input', updateCounter);
  updateCounter();
  const deployUrl = h('input', { type: 'url', id: 'deploy_url', maxlength: LIMIT.url, value: edit ? project.deploy_url || '' : '', placeholder: 'http://', autocomplete: 'off' });
  const repoUrl = h('input', { type: 'url', id: 'repo_url', maxlength: LIMIT.url, value: edit ? project.repo_url || '' : '', placeholder: 'http://', autocomplete: 'off' });
  const author = h('input', { type: 'text', id: 'author', maxlength: LIMIT.author, value: edit ? project.author : '', autocomplete: 'off' });

  const fTitle = field('title', '과제명', title, { required: true });
  const fDesc = field('description', '설명', description, { required: true, counter: descCounter });
  const fDeploy = field('deploy_url', '배포 URL', deployUrl);
  const fRepo = field('repo_url', '저장소 URL', repoUrl);
  const urlErr = h('p', { class: 'field-error', id: 'urls-error', hidden: true });
  const fAuthor = field('author', '작성자', author, { required: true });

  // 태그 칩 입력
  const tagList = h('ul', { class: 'chips', 'aria-label': '추가한 태그' });
  const tagInput = h('input', { type: 'text', id: 'tag-input', maxlength: LIMIT.tag + 5, autocomplete: 'off', placeholder: '입력 후 Enter 또는 쉼표' });
  const fTags = field('tag-input', '태그', h('div', { class: 'tag-input-wrap' }, tagInput, tagList),
    { hint: `최대 ${LIMIT.tags}개, 각 ${LIMIT.tag}자 이내. Enter 또는 쉼표로 추가합니다.` });

  function renderTags() {
    clear(tagList);
    tags.forEach((t, i) => {
      tagList.appendChild(h('li', { class: 'chip' }, h('span', { text: t }),
        h('button', {
          type: 'button', class: 'chip-remove', text: '×', 'aria-label': `태그 ${t} 삭제`,
          onClick: () => { tags.splice(i, 1); renderTags(); tagInput.focus(); },
        })));
    });
  }
  // 반환값: 오류 문구 또는 null
  function addTag(raw) {
    const t = normSpace(raw);
    if (!t) return null;
    if (tags.some((x) => x.toLowerCase() === t.toLowerCase())) return null;
    if (t.length > LIMIT.tag) return `태그는 ${LIMIT.tag}자 이내로 입력하세요.`;
    if (!TAG_RE.test(t)) return '태그에는 한글·영문·숫자·공백과 - _ . # + 만 사용할 수 있습니다.';
    if (tags.length >= LIMIT.tags) return `태그는 최대 ${LIMIT.tags}개까지 추가할 수 있습니다.`;
    tags.push(t);
    renderTags();
    return null;
  }
  function commitTagInput() {
    const msg = addTag(tagInput.value);
    if (msg) setError(fTags, msg); else { setError(fTags, ''); tagInput.value = ''; }
  }
  tagInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === ',') { e.preventDefault(); commitTagInput(); }
    else if (e.key === 'Backspace' && !tagInput.value && tags.length) { tags.pop(); renderTags(); }
  });
  tagInput.addEventListener('blur', () => { if (tagInput.value.trim()) commitTagInput(); });
  renderTags();

  // 스크린샷
  const fileInput = h('input', { type: 'file', id: 'image', accept: IMAGE_TYPES.join(',') });
  const preview = h('div', { class: 'image-preview' });
  const imageActions = h('div', { class: 'image-actions' });
  const fImage = field('image', '스크린샷', h('div', {}, fileInput, preview, imageActions),
    { hint: 'png, jpg, webp / 최대 2MB / 1장 (선택)' });
  const currentImage = edit ? project.image_url : null;

  function revokeAll() { objectUrls.splice(0).forEach((u) => URL.revokeObjectURL(u)); }
  function renderImage() {
    clear(preview); clear(imageActions);
    if (img.file) {
      const url = URL.createObjectURL(img.file);
      objectUrls.push(url);
      preview.appendChild(h('img', { src: url, alt: '선택한 스크린샷 미리보기' }));
      imageActions.appendChild(h('button', {
        type: 'button', class: 'btn btn-small', text: '선택 취소',
        onClick: () => { img.file = null; fileInput.value = ''; revokeAll(); renderImage(); },
      }));
    } else if (currentImage && !img.remove) {
      preview.appendChild(h('img', { src: currentImage, alt: '현재 스크린샷' }));
      imageActions.appendChild(h('button', {
        type: 'button', class: 'btn btn-small', text: '현재 이미지 제거',
        onClick: () => { img.remove = true; renderImage(); },
      }));
    } else if (currentImage && img.remove) {
      preview.appendChild(h('p', { class: 'hint', text: '저장하면 현재 이미지가 삭제됩니다.' }));
      imageActions.appendChild(h('button', {
        type: 'button', class: 'btn btn-small', text: '제거 취소',
        onClick: () => { img.remove = false; renderImage(); },
      }));
    }
  }
  fileInput.addEventListener('change', () => {
    const f = fileInput.files && fileInput.files[0];
    setError(fImage, '');
    if (!f) { img.file = null; revokeAll(); renderImage(); return; }
    if (!IMAGE_TYPES.includes(f.type)) {
      fileInput.value = ''; img.file = null; revokeAll(); renderImage();
      setError(fImage, 'png, jpg, webp 형식만 올릴 수 있습니다.'); return;
    }
    if (f.size > LIMIT.image) {
      fileInput.value = ''; img.file = null; revokeAll(); renderImage();
      setError(fImage, '이미지는 2MB 이하만 올릴 수 있습니다.'); return;
    }
    revokeAll();
    img.file = f;
    renderImage();
  });
  renderImage();

  // 수정용 비밀번호(수정 모드)
  const password = h('input', { type: 'password', id: 'edit-password', autocomplete: 'new-password' });
  const fPass = edit ? field('edit-password', '수정용 비밀번호', password,
    { required: true, hint: '등록할 때 안내받은 비밀번호입니다. 저장할 때 확인합니다.' }) : null;

  const submitBtn = h('button', { type: 'submit', class: 'btn btn-primary', text: edit ? '수정 저장' : '등록' });
  const waitHint = h('p', { class: 'hint', hidden: true, text: '처리 중입니다. 응답이 늦어도 다시 누르지 마세요.' });

  function setError(f, msg) {
    f.err.textContent = msg || '';
    f.err.hidden = !msg;
    const control = f.el.querySelector('input, textarea');
    if (control && f !== fImage && f !== fTags) {
      if (msg) control.setAttribute('aria-invalid', 'true'); else control.removeAttribute('aria-invalid');
    }
  }
  function setUrlError(msg) {
    urlErr.textContent = msg || '';
    urlErr.hidden = !msg;
  }
  function setTop(msg) {
    topError.textContent = msg || '';
    topError.hidden = !msg;
    if (msg) topError.focus();
  }
  function clearErrors() {
    [fTitle, fDesc, fDeploy, fRepo, fAuthor, fTags, fImage, fPass].forEach((f) => f && setError(f, ''));
    setUrlError(''); setTop('');
  }

  // 클라이언트 검증. 첫 오류 필드 요소를 반환
  function validate() {
    let first = null;
    const bad = (f, ctl, msg) => { setError(f, msg); first = first || ctl; };
    if (!title.value.trim()) bad(fTitle, title, '과제명을 입력하세요.');
    else if (title.value.trim().length > LIMIT.title) bad(fTitle, title, `과제명은 ${LIMIT.title}자 이내로 입력하세요.`);
    const d = description.value.trim();
    if (!d) bad(fDesc, description, '설명을 입력하세요.');
    else if (d.length > LIMIT.description) bad(fDesc, description, `설명은 ${LIMIT.description}자 이내로 입력하세요.`);
    const du = deployUrl.value.trim();
    const ru = repoUrl.value.trim();
    if (!du && !ru) { setUrlError('배포 URL 또는 저장소 URL 중 하나는 입력해야 합니다.'); first = first || deployUrl; }
    if (du && !validUrl(du)) bad(fDeploy, deployUrl, 'http:// 또는 https:// 로 시작하는 올바른 URL을 입력하세요.');
    if (ru && !validUrl(ru)) bad(fRepo, repoUrl, 'http:// 또는 https:// 로 시작하는 올바른 URL을 입력하세요.');
    if (!author.value.trim()) bad(fAuthor, author, '작성자를 입력하세요.');
    else if (author.value.trim().length > LIMIT.author) bad(fAuthor, author, `작성자는 ${LIMIT.author}자 이내로 입력하세요.`);
    if (tagInput.value.trim()) {
      const msg = addTag(tagInput.value);
      if (msg) bad(fTags, tagInput, msg); else tagInput.value = '';
    }
    if (edit && !password.value) bad(fPass, password, '비밀번호를 입력하세요.');
    return first;
  }

  function buildBody() {
    const fd = new FormData();
    fd.append('title', title.value.trim());
    fd.append('description', description.value.trim());
    fd.append('author', author.value.trim());
    // PUT은 전체 교체이므로 빈 URL도 그대로(빈 문자열) 보낸다
    fd.append('deploy_url', deployUrl.value.trim());
    fd.append('repo_url', repoUrl.value.trim());
    tags.forEach((t) => fd.append('tags', t));
    if (img.file) fd.append('image', img.file);
    else if (edit && img.remove) fd.append('remove_image', 'true');
    return fd;
  }

  function showServerError(err) {
    const pwMsg = edit ? passwordErrorMessage(err) : null;
    if (pwMsg) {
      setError(fPass, pwMsg);
      password.focus();
      if (err.status === 429) locked = true;
      if (err.status === 429) cleanups.push(lockFor(err.retryAfter, [password, submitBtn]));
    } else if (err.code === 'IMAGE_TOO_LARGE' || err.code === 'IMAGE_TYPE_UNSUPPORTED' || err.code === 'REQUEST_TOO_LARGE') {
      setError(fImage, err.message);
      fileInput.focus();
    } else {
      setTop(err.message);
    }
  }

  let busy = false;
  let locked = false;
  const form = h('form', {
    novalidate: true,
    onSubmit: async (e) => {
      e.preventDefault();
      if (busy) return;
      clearErrors();
      const first = validate();
      if (first) { first.focus(); return; }
      busy = true;
      locked = false;
      submitBtn.disabled = true;
      submitBtn.textContent = '저장 중…';
      waitHint.hidden = false;
      try {
        if (edit) {
          await updateProject(project.id, buildBody(), password.value);
          if (!ctx.alive()) return;
          toast('과제를 수정했습니다.', 'success');
          location.hash = `#/projects/${project.id}`;
        } else {
          const res = await createProject(buildBody());
          if (!ctx.alive()) return;
          revokeAll();
          const pw = res.edit_password;
          const cleanupNotice = noticeView(root, res.project, pw);
          cleanups.push(cleanupNotice);
        }
      } catch (err) {
        if (!ctx.alive()) return;
        showServerError(err);
      } finally {
        busy = false;
        if (ctx.alive() && form.isConnected) {
          if (!locked) submitBtn.disabled = false;
          submitBtn.textContent = edit ? '수정 저장' : '등록';
          waitHint.hidden = true;
        }
      }
    },
  },
  topError,
  fTitle.el, fDesc.el,
  h('fieldset', { class: 'field' },
    h('legend', { class: 'label', text: '링크 (둘 중 하나 이상 입력)' }),
    h('div', { class: 'field-group' }, fDeploy.el, fRepo.el), urlErr),
  fAuthor.el, fTags.el, fImage.el,
  fPass ? fPass.el : null,
  h('div', { class: 'btn-row' }, submitBtn,
    h('a', { class: 'btn', href: edit ? `#/projects/${project.id}` : '#/', text: '취소' })),
  waitHint);

  root.appendChild(h('div', { class: 'panel' },
    h('h1', { text: edit ? '과제 수정' : '과제 등록', tabindex: '-1', class: 'page-title' }), form));
  if (edit) root.querySelector('.panel').insertBefore(
    h('p', { class: 'hint', text: '수정은 전체 교체입니다. 비운 링크·태그는 삭제됩니다.' }), form);

  return () => { revokeAll(); cleanups.forEach((fn) => fn()); };
}
