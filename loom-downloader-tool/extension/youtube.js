// Botão de download direto na página do YouTube (youtube.com/watch).
// Clica -> manda a URL do vídeo pro servidor local, que baixa via yt-dlp.
// O YouTube é uma SPA: a URL muda sem recarregar, então vigiamos as mudanças.

const SERVIDOR = 'http://localhost:5000/baixar';
const ID_BOTAO = 'loom-yt-download-btn';

function ehPaginaDeVideo() {
    return location.pathname === '/watch' &&
           new URLSearchParams(location.search).has('v');
}

function urlLimpaDoVideo() {
    // Só o essencial: descarta &t=, &list=, etc.
    const v = new URLSearchParams(location.search).get('v');
    return `https://www.youtube.com/watch?v=${v}`;
}

function tituloDoVideo() {
    // document.title = "TÍTULO - YouTube". O servidor limpa caracteres proibidos.
    return document.title.replace(/\s*-\s*YouTube\s*$/i, '').trim();
}

function estilizar(btn) {
    Object.assign(btn.style, {
        position: 'fixed',
        bottom: '90px',
        right: '20px',
        zIndex: '99999',
        padding: '12px 18px',
        borderRadius: '10px',
        border: 'none',
        background: '#6c5ce7',
        color: '#fff',
        font: '600 14px system-ui, sans-serif',
        cursor: 'pointer',
        boxShadow: '0 6px 14px rgba(0,0,0,0.35)',
    });
}

function criarBotao() {
    if (!ehPaginaDeVideo()) { removerBotao(); return; }
    if (document.getElementById(ID_BOTAO)) return;

    const btn = document.createElement('button');
    btn.id = ID_BOTAO;
    btn.textContent = '⬇ Baixar vídeo';
    estilizar(btn);

    btn.onclick = async () => {
        if (btn.disabled) return;
        btn.disabled = true;
        btn.textContent = '📡 Enviando...';
        try {
            const resp = await fetch(SERVIDOR, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    url: urlLimpaDoVideo(),
                    folder: 'YouTube',
                    filename: tituloDoVideo(),
                }),
            });
            await resp.json();
            btn.textContent = '⏳ Na fila';
        } catch (e) {
            console.error('[YouTube DL] servidor offline?', e);
            btn.textContent = '❌ Servidor offline?';
        }
        setTimeout(() => { btn.disabled = false; btn.textContent = '⬇ Baixar vídeo'; }, 4000);
    };

    document.body.appendChild(btn);
}

function removerBotao() {
    const btn = document.getElementById(ID_BOTAO);
    if (btn) btn.remove();
}

// Injeta agora e a cada mudança de URL (navegação SPA do YouTube).
criarBotao();
let urlAtual = location.href;
new MutationObserver(() => {
    if (location.href !== urlAtual) {
        urlAtual = location.href;
        setTimeout(criarBotao, 500);
    }
}).observe(document, { subtree: true, childList: true });
