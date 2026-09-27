// OneTech Studio: gönderim öncesi yerel istem denetimi.
(() => {
    const INPUT_SELECTOR = '#prompt-textarea, rich-textarea [contenteditable="true"], .ql-editor[contenteditable="true"], textarea, [contenteditable="true"]';
    const SEND_SELECTOR = 'button[data-testid="send-button"], button[data-testid="send-button"] *, button[aria-label*="Send"], button[aria-label*="send"], button[aria-label*="Gönder"], button[aria-label*="gönder"], button.send-button';
    let processing = false;
    let bypassNext = false;

    function inputFor(target) {
        const direct = target?.closest?.('textarea, [contenteditable="true"]');
        return direct || document.querySelector(INPUT_SELECTOR);
    }

    function inputText(input) {
        return input?.tagName === 'TEXTAREA' ? input.value : (input?.innerText || input?.textContent || '');
    }

    function findSendButton() {
        return document.querySelector(SEND_SELECTOR)?.closest('button') || null;
    }

    function replaceInput(input, value) {
        input.focus();
        if (input.tagName === 'TEXTAREA') {
            const setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value').set;
            setter.call(input, value);
            input.dispatchEvent(new Event('input', { bubbles: true, composed: true }));
            return;
        }
        const selection = window.getSelection();
        const range = document.createRange();
        range.selectNodeContents(input);
        selection.removeAllRanges();
        selection.addRange(range);
        if (!document.execCommand('insertText', false, value)) input.textContent = value;
        input.dispatchEvent(new InputEvent('input', { bubbles: true, composed: true, inputType: 'insertText', data: value }));
    }

    function submitAfterReview(input, triggerButton) {
        const button = triggerButton?.isConnected ? triggerButton : findSendButton();
        if (button && !button.disabled) {
            bypassNext = true;
            button.click();
            setTimeout(() => { bypassNext = false; }, 250);
        } else if (input.closest('form')?.requestSubmit) {
            input.closest('form').requestSubmit();
        } else {
            showReview({ message: 'Bu sayfada gönder düğmesi bulunamadı. OneTech bu gönderimi otomatik tamamlayamadı.' },
                input, null, true);
        }
    }

    function make(tag, className, text) {
        const element = document.createElement(tag);
        element.className = className;
        if (text !== undefined) element.textContent = text;
        return element;
    }

    function showReview(data, input, triggerButton, serviceError = false) {
        if (document.getElementById('onetech-review-host')) return;
        const host = document.createElement('div');
        host.id = 'onetech-review-host';
        host.style.cssText = 'position:fixed;inset:0;z-index:2147483647;';
        const shadow = host.attachShadow({ mode: 'open' });
        const style = document.createElement('style');
        style.textContent = `
          *{box-sizing:border-box} .overlay{min-height:100vh;background:#07131dd9;backdrop-filter:blur(6px);display:grid;place-items:center;padding:18px;font-family:Inter,Segoe UI,Arial,sans-serif;color:#edf8f6}
          .card{width:min(620px,100%);background:#102337;border:1px solid #356175;border-radius:18px;box-shadow:0 24px 70px #0008;padding:24px}
          .top{display:flex;justify-content:space-between;align-items:flex-start;gap:16px}.brand{color:#70e4d0;font-size:11px;font-weight:800;letter-spacing:.15em;text-transform:uppercase}
          h2{font-size:21px;line-height:1.2;margin:8px 0 5px}p{color:#b3c9d2;font-size:13px;line-height:1.5;margin:8px 0 18px}
          .risk{border:1px solid #355669;background:#193247;border-radius:12px;padding:10px 14px;text-align:center;min-width:90px;font-size:23px;font-weight:800;color:#6bd9c7}
          .risk small{display:block;font-size:10px;color:#a9bfca;font-weight:700;letter-spacing:.06em}.risk.exposed{color:#f7b479}
          .preview{background:#091824;border:1px solid #29475a;border-radius:12px;padding:16px;white-space:pre-wrap;line-height:1.7;max-height:250px;overflow:auto;font-size:14px;overflow-wrap:anywhere}
          .token{border:1px solid #64d7c4;border-radius:6px;background:#1a514d;color:#d9fff7;padding:2px 5px;cursor:pointer;font:inherit}.token.off{border-color:#eaa46f;background:#5e3b30;color:#fff4e9}
          .actions{display:flex;justify-content:flex-end;gap:10px;margin-top:18px}.actions button{border-radius:9px;padding:10px 16px;font-weight:700;cursor:pointer;font-size:13px}
          .secondary{background:transparent;border:1px solid #5a7484;color:#dce9e9}.primary{background:#68dcc9;border:1px solid #68dcc9;color:#09202a}.primary:disabled{opacity:.55;cursor:not-allowed}
          .notice{color:#f2bb91;font-size:12px;margin-top:12px}`;
        shadow.appendChild(style);
        const overlay = make('div', 'overlay');
        const card = make('div', 'card');
        const top = make('div', 'top');
        const heading = make('div', '');
        heading.append(make('div', 'brand', '◈ OneTech Studio'), make('h2', '', serviceError ? 'Yerel servis çalışmıyor' : 'Gönderim öncesi kontrol'));
        const risk = make('div', 'risk');
        top.append(heading, risk);
        const description = make('p', '', serviceError
            ? 'İstem gönderilmedi. OneTech Studio başlatıcısını çalıştırıp tekrar deneyin.'
            : 'Bulunan hassas alanları açıp kapatabilirsiniz. İşaretli alanlar maskelenerek gönderilir.');
        const preview = make('div', 'preview');
        const notice = make('div', 'notice');
        const actions = make('div', 'actions');
        const cancel = make('button', 'secondary', 'İptal');
        const send = make('button', 'primary', 'Maskeli metni gönder');
        cancel.addEventListener('click', () => host.remove());
        actions.append(cancel);
        if (!serviceError) actions.append(send);
        card.append(top, description, preview, notice, actions);
        overlay.appendChild(card);
        shadow.appendChild(overlay);
        document.documentElement.appendChild(host);

        if (serviceError) {
            risk.textContent = '!';
            preview.textContent = data.message || 'Bağlantı kurulamadı.';
            return;
        }

        const matches = [...data.matches].sort((a, b) => a.startIndex - b.startIndex);
        const active = matches.map(() => true);
        function render() {
            preview.replaceChildren();
            let cursor = 0;
            for (let index = 0; index < matches.length; index++) {
                const match = matches[index];
                preview.appendChild(document.createTextNode(data.originalPrompt.slice(cursor, match.startIndex)));
                const token = make('button', `token${active[index] ? '' : ' off'}`, active[index] ? match.mask : match.original);
                token.title = `${match.type} · ${active[index] ? 'Maskeyi kaldır' : 'Tekrar maskele'}`;
                token.addEventListener('click', () => { active[index] = !active[index]; render(); });
                preview.appendChild(token);
                cursor = match.endIndex;
            }
            preview.appendChild(document.createTextNode(data.originalPrompt.slice(cursor)));
            const total = matches.reduce((sum, match) => sum + match.score, 0);
            const exposed = matches.reduce((sum, match, index) => sum + (active[index] ? 0 : match.score), 0);
            const percent = total ? Math.round(exposed / total * 100) : 0;
            risk.className = `risk${percent ? ' exposed' : ''}`;
            risk.replaceChildren(make('small', '', 'AÇIK KALAN PAY'), document.createTextNode(`%${percent}`));
            notice.textContent = percent ? 'Bazı veriler açık bırakıldı. Gönderilecek metni kontrol edin.' : `${matches.length} alan maskelenecek.`;
            send.textContent = percent ? 'Seçilen metni gönder' : 'Maskeli metni gönder';
        }
        send.addEventListener('click', () => {
            let finalPrompt = data.originalPrompt;
            for (let index = matches.length - 1; index >= 0; index--) {
                const match = matches[index];
                if (active[index]) finalPrompt = finalPrompt.slice(0, match.startIndex) + match.mask + finalPrompt.slice(match.endIndex);
            }
            replaceInput(input, finalPrompt);
            host.remove();
            setTimeout(() => submitAfterReview(input, triggerButton), 120);
        });
        render();
    }

    async function inspect(event, input, triggerButton) {
        const prompt = inputText(input);
        if (!prompt.trim()) return;
        event.preventDefault();
        event.stopImmediatePropagation();
        if (processing) return;
        processing = true;
        try {
            const data = await chrome.runtime.sendMessage({ action: 'checkPrompt', prompt });
            if (!data || data.error) showReview(data || {}, input, triggerButton, true);
            else if (data.matches?.length) showReview(data, input, triggerButton);
            else submitAfterReview(input, triggerButton);
        } catch (_error) {
            showReview({}, input, triggerButton, true);
        } finally {
            processing = false;
        }
    }

    document.addEventListener('keydown', event => {
        if (event.key !== 'Enter' || event.shiftKey || event.isComposing) return;
        if (bypassNext) { bypassNext = false; return; }
        const input = inputFor(event.target);
        if (input && (event.target === input || input.contains(event.target))) inspect(event, input, null);
    }, true);

    document.addEventListener('click', event => {
        if (bypassNext) { bypassNext = false; return; }
        const button = event.target.closest?.(SEND_SELECTOR)?.closest('button');
        if (button) {
            const input = inputFor(null);
            if (input) inspect(event, input, button);
        }
    }, true);
})();
