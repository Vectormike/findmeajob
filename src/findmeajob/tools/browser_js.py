READ_FIELDS = r"""
() => {
  document.querySelectorAll('[data-fmaj]').forEach((el) => el.removeAttribute('data-fmaj'));
  const labelOf = (el) => {
    if (el.id) {
      const label = document.querySelector(`label[for="${CSS.escape(el.id)}"]`);
      if (label && label.innerText.trim()) return label.innerText.trim();
    }
    const wrap = el.closest('label');
    if (wrap && wrap.innerText.trim()) return wrap.innerText.trim();
    return (el.getAttribute('aria-label') || el.placeholder || el.name || '').trim();
  };
  const questionOf = (el) => {
    const legend = el.closest('fieldset')?.querySelector('legend');
    if (legend) return legend.innerText.trim();
    const group = el.closest('[role="radiogroup"], [role="group"], .field, .form-group, li, div');
    const heading = group?.querySelector('label:not(:has(input)), p, span, h3, h4');
    return heading ? heading.innerText.trim() : labelOf(el);
  };
  const visible = (el) => {
    const style = getComputedStyle(el);
    const box = el.getBoundingClientRect();
    return !el.disabled && style.display !== 'none' && style.visibility !== 'hidden' && box.width > 0 && box.height > 0;
  };
  const fields = [];
  const groups = {};
  let n = 0;
  const selector = [
    'input', 'textarea', 'select', '[contenteditable="true"]',
    '[role="combobox"]', '[role="checkbox"]', '[role="radio"]'
  ].join(',');
  const seen = new Set();
  for (const el of document.querySelectorAll(selector)) {
    if (seen.has(el) || !visible(el)) continue;
    seen.add(el);
    if (el.matches('[role="combobox"]')) {
      el.querySelectorAll('input').forEach((child) => seen.add(child));
    }
    if (el.getAttribute('role') === 'radio') {
      const group = el.closest('[role="radiogroup"]') || el.parentElement;
      if (seen.has(group)) continue;
      seen.add(group);
      const options = [...group.querySelectorAll('[role="radio"]')].filter(visible);
      const id = `g${n++}`;
      fields.push({
        id,
        type: 'radio',
        label: group.getAttribute('aria-label') || questionOf(el),
        required: group.getAttribute('aria-required') === 'true',
        options: options.map((option) => {
          const optionId = `f${n++}`;
          option.setAttribute('data-fmaj', optionId);
          seen.add(option);
          return {
            id: optionId,
            label: (option.getAttribute('aria-label') || option.innerText || '').trim()
          };
        })
      });
      continue;
    }
    const type = (el.getAttribute('type') || el.tagName).toLowerCase();
    if (['hidden', 'submit', 'button', 'reset', 'image', 'search'].includes(type)) continue;
    const id = `f${n++}`;
    el.setAttribute('data-fmaj', id);
    if (type === 'radio') {
      const name = el.name || id;
      if (!groups[name]) {
        groups[name] = { id: `g_${name}`, type: 'radio', label: questionOf(el), required: el.required, options: [] };
        fields.push(groups[name]);
      }
      groups[name].options.push({ id, label: labelOf(el) || el.value });
      continue;
    }
    const required = el.required || el.getAttribute('aria-required') === 'true';
    const field = { id, type, label: labelOf(el), required };
    if (el.matches('[contenteditable="true"]')) field.type = 'contenteditable';
    if (el.getAttribute('role') === 'checkbox') field.type = 'checkbox';
    if (el.getAttribute('role') === 'combobox' || el.getAttribute('aria-autocomplete')) {
      field.type = 'combobox';
      const list = el.getAttribute('aria-controls');
      const root = list ? document.getElementById(list) : document.querySelector('[role="listbox"]');
      field.options = root
        ? [...root.querySelectorAll('[role="option"]')].map((o) => ({
            id: o.id || o.innerText.trim(),
            label: o.innerText.trim()
          }))
        : [];
    }
    if (type === 'select' || el.tagName === 'SELECT') {
      field.type = 'select';
      field.options = [...el.options].map((o) => ({ id: o.value, label: o.text.trim() })).filter((o) => o.label);
    }
    fields.push(field);
  }
  return fields;
}
"""

READ_ERRORS = r"""
() => {
  const messages = new Set();
  for (const el of document.querySelectorAll(':invalid, [aria-invalid="true"]')) {
    const label = el.getAttribute('aria-label') || el.name || el.id || 'field';
    const described = (el.getAttribute('aria-describedby') || '').split(/\s+/).filter(Boolean);
    const text = described.map((id) => document.getElementById(id)?.innerText || '').filter(Boolean).join(' ');
    messages.add(`${label}: ${text || el.validationMessage || 'invalid value'}`);
  }
  const errorSelector = [
    '[role="alert"]', '.error', '.field-error', '.validation-error', '[data-automation-id*="error"]'
  ].join(',');
  for (const el of document.querySelectorAll(errorSelector)) {
    const text = el.innerText?.trim();
    if (text && el.getBoundingClientRect().height > 0) messages.add(text);
  }
  return [...messages].slice(0, 20);
}
"""

SUCCESS_WORDS = ("thank you", "thanks for applying", "application received", "submitted", "we have received")
