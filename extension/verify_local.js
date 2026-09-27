// Yerel servis çalışırken: node extension/verify_local.js
const assert = require('node:assert/strict');

let listener;
let badge;
global.chrome = {
    runtime: { onMessage: { addListener(callback) { listener = callback; } } },
    storage: { local: { async set() {} } },
    action: {
        async setBadgeText({ text }) { badge = text; },
        async setBadgeBackgroundColor() {}
    }
};
require('./background.js');

function message(action, prompt) {
    return new Promise(resolve => {
        const asyncResponse = listener({ action, prompt }, {}, resolve);
        assert.equal(asyncResponse, true);
    });
}

(async () => {
    const health = await message('health');
    assert.equal(health.ready, true, 'Önce prompt_api.py servisini başlatın.');
    const result = await message('checkPrompt', 'E-posta: ayse.ornek@example.com');
    assert.equal(result.matches.length, 1);
    assert.equal(result.matches[0].type, 'E-posta');
    assert.equal(badge, '30');
    const realFetch = global.fetch;
    global.fetch = async () => { throw new Error('offline'); };
    const failure = await message('checkPrompt', 'ayse.ornek@example.com');
    global.fetch = realFetch;
    assert.equal(failure.error, true);
    assert.equal(badge, '!');
    console.log('OK: OneTech background → yerel API → eşleşme, rozet ve bağlantı hatası');
})().catch(error => { console.error(error); process.exitCode = 1; });
