// Popup "colar link": manda uma URL de YouTube pro servidor local.
// O título fica vazio de propósito — o servidor resolve pelo yt-dlp.

const SERVIDOR = 'http://localhost:5000/baixar';
const $ = (id) => document.getElementById(id);

function ehYoutube(url) {
    return /(youtube\.com|youtu\.be)/i.test(url);
}

async function baixar() {
    const url = $('url').value.trim();
    const folder = $('folder').value.trim() || 'YouTube';
    const status = $('status');

    if (!url) { status.textContent = 'Cole um link primeiro.'; return; }
    if (!ehYoutube(url)) {
        status.textContent = '⚠️ Isso não parece um link do YouTube.';
        return;
    }

    $('baixar').disabled = true;
    status.textContent = 'Enviando...';
    try {
        const resp = await fetch(SERVIDOR, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url, folder, filename: '' }),
        });
        await resp.json();
        status.textContent = '✅ Na fila! Acompanhe no terminal do servidor.';
        $('url').value = '';
    } catch (e) {
        status.textContent = '❌ Servidor offline? Suba o servidor local (localhost:5000).';
    }
    $('baixar').disabled = false;
}

$('baixar').addEventListener('click', baixar);
$('url').addEventListener('keydown', (e) => { if (e.key === 'Enter') baixar(); });
