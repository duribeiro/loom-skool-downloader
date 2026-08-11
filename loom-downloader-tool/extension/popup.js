// Sifão — popup central de controle.
// Status do servidor + "Baixar curso inteiro" (contextual à aba do Skool) +
// colar link do YouTube. A ação de curso é executada pelo content script da aba
// (persiste mesmo se o popup fechar); aqui só disparamos e mostramos progresso.

const SERVIDOR = 'http://localhost:5000/baixar';
const $ = (id) => document.getElementById(id);

// O servidor roteia YouTube, Loom e Vimeo. Como o campo agora se chama "link do
// vídeo" (e não mais "link do YouTube"), aceitar só YouTube seria mentir para o
// usuário. Cada origem tem sua pasta — YouTube ainda se subdivide por canal no servidor.
const ORIGENS = [
    { nome: 'YouTube', teste: /(youtube\.com|youtu\.be)/i, pasta: 'YouTube' },
    { nome: 'Loom',    teste: /loom\.com\/(embed|share)\//i, pasta: 'Loom' },
    { nome: 'Vimeo',   teste: /vimeo\.com/i, pasta: 'Vimeo' },
];

function origemDoLink(url) {
    return ORIGENS.find((o) => o.teste.test(url)) || null;
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

// --- Comunidade da aba (listagem /{grupo}/classroom) ------------------------
// Confirmação em DOIS passos: o primeiro clique só revela o tamanho do estrago
// (podem ser centenas de aulas); o segundo é que dispara. O total sai na hora
// porque vem de `numModules`, sem varrer os cursos antes.
let abaComuId = null;
let comuInfo = null;
let comuArmado = false;

async function detectarComunidade() {
    const tab = await tabAtiva();
    if (!tab || !tab.url || !/skool\.com\//.test(tab.url)) return;
    const info = await enviarPraAba(tab.id, { tipo: 'sifao:contextoComunidade' });
    if (info && info.ok) {
        abaComuId = tab.id;
        comuInfo = info;
        $('comuNome').textContent = info.comunidade;
        const blo = info.bloqueados
            ? ` · ${info.bloqueados} sem acesso (serão pulados)` : '';
        $('comuResumo').textContent =
            `${info.cursos} curso${info.cursos === 1 ? '' : 's'} · ~${info.aulas} aulas${blo}`;
        $('ctxComunidade').classList.remove('hidden');
    }
}

function desarmarComunidade() {
    comuArmado = false;
    $('btnComuTxt').textContent = 'Baixar todos os cursos';
    $('btnComuCancel').classList.add('hidden');
}

$('btnComuCancel').addEventListener('click', () => {
    desarmarComunidade();
    $('hint').textContent = '';
});

$('btnComu').addEventListener('click', async () => {
    if (abaComuId == null || !comuInfo) return;

    // 1º clique: arma e mostra o que vai acontecer. Nada é enviado ainda.
    if (!comuArmado) {
        comuArmado = true;
        $('btnComuTxt').textContent = `Confirmar — ${comuInfo.aulas} aulas`;
        $('btnComuCancel').classList.remove('hidden');
        $('hint').textContent =
            `⚠️ Vai enfileirar ~${comuInfo.aulas} aulas de ${comuInfo.cursos} cursos. ` +
            `Leva alguns minutos e a aba precisa ficar aberta.`;
        return;
    }

    // 2º clique: dispara de verdade.
    const btn = $('btnComu');
    btn.disabled = true;
    $('btnComuCancel').classList.add('hidden');
    $('btnComuTxt').textContent = 'Lendo cursos…';

    const resp = await enviarPraAba(abaComuId, { tipo: 'sifao:baixarComunidade' });
    if (resp && resp.ok) {
        $('btnComuTxt').textContent = 'Comunidade enviada';
        let msg = `✅ ${resp.enviadas} aulas de ${resp.cursos} cursos na fila — acompanhe no terminal.`;
        if (resp.bloqueados && resp.bloqueados.length) {
            msg += `\n\n🔒 Pulados por falta de acesso (${resp.bloqueados.length}): ` +
                   resp.bloqueados.join(', ') + '.';
        }
        if (resp.falharam && resp.falharam.length) {
            msg += `\n\n⚠️ Não consegui ler (${resp.falharam.length}): ` +
                   resp.falharam.join(', ') + '.';
        }
        $('hint').textContent = msg;
    } else {
        const motivo = resp && resp.motivo;
        btn.disabled = false;
        desarmarComunidade();
        $('hint').textContent =
            motivo === 'vazio' ? '⚠️ Nenhum curso acessível encontrado — recarregue a página (F5).'
          : motivo === 'ocupado' ? '⏳ Já há um envio em andamento nessa aba.'
          : '❌ Não consegui enfileirar. O servidor está online?';
    }
});

// Progresso vindo do content script (enquanto o popup estiver aberto).
chrome.runtime.onMessage.addListener((msg) => {
    if (msg && msg.tipo === 'sifao:progresso') {
        const texto = msg.fase === 'cursos' ? `Lendo cursos ${msg.i}/${msg.n}…`
                    : msg.fase === 'texto'  ? `Lendo textos ${msg.i}/${msg.n}…`
                    :                         `Enfileirando ${msg.i}/${msg.n}…`;
        // O progresso vai para o botão que está de fato rodando.
        const alvo = $('btnComu').disabled ? 'btnComuTxt' : 'btnCursoTxt';
        $(alvo).textContent = texto;
    }
});

// --- YouTube (link colado) --------------------------------------------------
async function baixarYoutube() {
    const url = $('url').value.trim();
    if (!url) { $('hint').textContent = 'Cole um link primeiro.'; return; }

    const origem = origemDoLink(url);
    if (!origem) {
        $('hint').textContent = '⚠️ Não reconheci o link. Aceito YouTube, Loom e Vimeo.';
        return;
    }

    $('btnYt').disabled = true;
    $('hint').textContent = `Enviando para ${origem.nome}…`;
    try {
        await fetch(SERVIDOR, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url, folder: origem.pasta, filename: '' }),
        });
        $('hint').textContent = origem.nome === 'YouTube'
            ? '✅ Na fila! Organizado por canal em output/YouTube/.'
            : `✅ Na fila! Vai para output/${origem.pasta}/.`;
        $('url').value = '';
    } catch (e) {
        $('hint').textContent = '❌ Servidor offline? Suba o servidor local (localhost:5000).';
    }
    $('btnYt').disabled = false;
}

// Colar link é o caso raro; fica recolhido até ser pedido. Abrir já foca o campo,
// porque quem clica aqui veio com um link na mão.
$('btnAbrirColar').addEventListener('click', () => {
    $('blocoColar').classList.remove('hidden');
    $('btnAbrirColar').classList.add('hidden');
    $('url').focus();
});

$('btnYt').addEventListener('click', baixarYoutube);
$('url').addEventListener('keydown', (e) => { if (e.key === 'Enter') baixarYoutube(); });

atualizarStatus();
detectarCurso();
detectarComunidade();
