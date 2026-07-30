// Sifão — popup central de controle.
// Status do servidor + "Baixar curso inteiro" (contextual à aba do Skool) +
// colar link do YouTube. A ação de curso é executada pelo content script da aba
// (persiste mesmo se o popup fechar); aqui só disparamos e mostramos progresso.

const SERVIDOR = 'http://localhost:5000/baixar';
const $ = (id) => document.getElementById(id);

function ehYoutube(url) {
    return /(youtube\.com|youtu\.be)/i.test(url);
}

function tabAtiva() {
    return new Promise((res) =>
        chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => res(tabs[0] || null)));
}

function enviarPraAba(tabId, msg) {
    // Resolve null se não houver content script ouvindo (aba não-Skool, etc.).
    return new Promise((res) => {
        try {
            chrome.tabs.sendMessage(tabId, msg, (resp) => {
                if (chrome.runtime.lastError) { res(null); return; }
                res(resp);
            });
        } catch (e) { res(null); }
    });
}

// --- Status do servidor -----------------------------------------------------
async function pingServidor() {
    // no-cors: resolve se a conexão vingou (mesmo 404), rejeita se recusada.
    try {
        const ctrl = new AbortController();
        const t = setTimeout(() => ctrl.abort(), 1500);
        await fetch('http://localhost:5000/', { mode: 'no-cors', signal: ctrl.signal });
        clearTimeout(t);
        return true;
    } catch (e) { return false; }
}

async function atualizarStatus() {
    const on = await pingServidor();
    $('dot').className = 'dot ' + (on ? 'on' : 'off');
    $('statusTxt').textContent = on ? 'servidor online' : 'servidor offline';
}

// --- Curso da aba (contextual) ---------------------------------------------
let abaCursoId = null;

async function detectarCurso() {
    const tab = await tabAtiva();
    if (!tab || !tab.url || !/skool\.com\//.test(tab.url)) return;
    const info = await enviarPraAba(tab.id, { tipo: 'sifao:contextoCurso' });
    if (info && info.ok) {
        abaCursoId = tab.id;
        $('cursoNome').textContent = `${info.title} · ${info.count} aula${info.count === 1 ? '' : 's'}`;
        $('ctxCurso').classList.remove('hidden');
    }
}

$('btnCurso').addEventListener('click', async () => {
    if (abaCursoId == null) return;
    const btn = $('btnCurso');
    const txt = $('btnCursoTxt');
    btn.disabled = true;
    txt.textContent = 'Enfileirando…';

    const resp = await enviarPraAba(abaCursoId, { tipo: 'sifao:baixarCurso' });
    if (resp && resp.ok) {
        txt.textContent = 'Curso enviado';
        $('hint').textContent = `✅ ${resp.enviadas} aulas na fila — acompanhe no terminal.`;
    } else {
        const motivo = resp && resp.motivo;
        txt.textContent = 'Baixar curso inteiro';
        btn.disabled = false;
        $('hint').textContent =
            motivo === 'vazio' ? '⚠️ Nada encontrado — recarregue a página do curso (F5) e tente de novo.'
          : motivo === 'ocupado' ? '⏳ Já há um curso sendo enfileirado nessa aba.'
          : '❌ Não consegui enfileirar. O servidor está online?';
    }
});

// Progresso vindo do content script (enquanto o popup estiver aberto).
chrome.runtime.onMessage.addListener((msg) => {
    if (msg && msg.tipo === 'sifao:progresso') {
        $('btnCursoTxt').textContent = msg.fase === 'texto'
            ? `Lendo textos ${msg.i}/${msg.n}…`
            : `Enfileirando ${msg.i}/${msg.n}…`;
    }
});

// --- YouTube (link colado) --------------------------------------------------
async function baixarYoutube() {
    const url = $('url').value.trim();
    if (!url) { $('hint').textContent = 'Cole um link primeiro.'; return; }
    if (!ehYoutube(url)) { $('hint').textContent = '⚠️ Isso não parece um link do YouTube.'; return; }

    $('btnYt').disabled = true;
    $('hint').textContent = 'Enviando…';
    try {
        await fetch(SERVIDOR, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url, folder: 'YouTube', filename: '' }),
        });
        $('hint').textContent = '✅ Na fila! Organizado por canal em output/YouTube/.';
        $('url').value = '';
    } catch (e) {
        $('hint').textContent = '❌ Servidor offline? Suba o servidor local (localhost:5000).';
    }
    $('btnYt').disabled = false;
}

$('btnYt').addEventListener('click', baixarYoutube);
$('url').addEventListener('keydown', (e) => { if (e.key === 'Enter') baixarYoutube(); });

atualizarStatus();
detectarCurso();
