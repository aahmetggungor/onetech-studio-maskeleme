document.addEventListener('DOMContentLoaded', async () => {
    const status = document.getElementById('status');
    const detail = document.getElementById('detail');
    try {
        const response = await chrome.runtime.sendMessage({ action: 'health' });
        status.textContent = response?.ready ? '● Koruma hazır' : '● Yerel servis kapalı';
        status.className = `status ${response?.ready ? 'ready' : 'offline'}`;
        detail.textContent = response?.ready
            ? 'ChatGPT, Gemini ve Claude istemleri gönderilmeden önce incelenir.'
            : 'Studio başlatıcısını çalıştırın. Servis yokken istem gönderimi durdurulur.';
    } catch (_error) {
        status.textContent = '● Bağlantı kurulamadı';
        status.className = 'status offline';
    }
    document.getElementById('studio').addEventListener('click', () => {
        chrome.tabs.create({ url: 'http://127.0.0.1:8501/' });
    });
});
