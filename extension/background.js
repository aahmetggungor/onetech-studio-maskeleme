const API = 'http://127.0.0.1:8765';

async function checkPrompt(prompt) {
    try {
        const response = await fetch(`${API}/api/protect`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ prompt }),
            signal: AbortSignal.timeout(8000)
        });
        if (!response.ok) throw new Error(`Yerel servis HTTP ${response.status}`);
        const data = await response.json();
        const matches = Array.isArray(data.matches) ? data.matches : [];
        const score = Math.min(100, matches.reduce((sum, match) => sum + match.score, 0));
        await chrome.storage.local.set({ sonRisk: score, sonEngellenenler: [...new Set(matches.map(m => m.type))] });
        await chrome.action.setBadgeText({ text: score ? `${score}` : '✓' });
        await chrome.action.setBadgeBackgroundColor({ color: score ? '#db6b60' : '#2aa991' });
        return data;
    } catch (error) {
        await chrome.action.setBadgeText({ text: '!' });
        await chrome.action.setBadgeBackgroundColor({ color: '#db6b60' });
        return { error: true, message: 'Yerel OneTech servisine bağlanılamadı. Studio başlatıcısını çalıştırın.' };
    }
}

chrome.runtime.onMessage.addListener((request, _sender, sendResponse) => {
    if (request.action === 'checkPrompt') {
        checkPrompt(request.prompt).then(sendResponse);
        return true;
    }
    if (request.action === 'health') {
        fetch(`${API}/api/health`, { signal: AbortSignal.timeout(1500) })
            .then(response => sendResponse({ ready: response.ok }))
            .catch(() => sendResponse({ ready: false }));
        return true;
    }
});
