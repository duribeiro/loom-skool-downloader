// Botão de download (pill Sifão) na página do YouTube (youtube.com/watch).
// Mesmo visual do pill do Skool/Loom/Vimeo — os estilos vêm do ui.css compartilhado.
// O YouTube é uma SPA: a URL muda sem recarregar, então vigiamos as mudanças.

const SERVIDOR = 'http://localhost:5000/baixar';
const ID_BOTAO = 'sf-youtube';

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
    // A pasta do canal é resolvida no servidor (yt-dlp) → output/YouTube/<Canal>/.
    return document.title.replace(/\s*-\s*YouTube\s*$/i, '').trim();
}

// Fábrica do pill — idêntica à do content.js; visual vem do ui.css (.sf-pill).
function criarPill(rotulo, fixo) {
    const btn = document.createElement('button');
    btn.className = 'sf-pill ' + (fixo ? 'sf-pill--fixed' : 'sf-pill--overlay');
    const ico = document.createElement('span');
    ico.className = 'sf-pill__ico';
    const lab = document.createElement('span');
    lab.className = 'sf-pill__label';
    lab.textContent = rotulo;
    btn.append(ico, lab);
    btn._lab = lab;
    return btn;
}

function criarBotao() {
    if (!ehPaginaDeVideo()) { removerBotao(); return; }
    if (document.getElementById(ID_BOTAO)) return;

    // Ancora SOBRE o player, como no Loom. Se o player ainda não renderizou, NÃO cria
    // agora — o observador tenta de novo quando ele aparecer (evita cair no canto).
    const player = document.querySelector('#movie_player, .html5-video-player');
    if (!player) return;

    const btn = criarPill('Baixar vídeo', false);   // overlay no canto do vídeo
    btn.id = ID_BOTAO;

    btn.onclick = async () => {
        if (btn.disabled) return;
        btn.disabled = true;
        btn._lab.textContent = 'Enviando…';
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
            btn._lab.textContent = 'Na fila';
        } catch (e) {
            console.error('[YouTube DL] servidor offline?', e);
            btn.classList.add('sf-pill--err');
            btn._lab.textContent = 'Servidor offline?';
        }
        setTimeout(() => {
            btn.disabled = false;
            btn.classList.remove('sf-pill--err');
            btn._lab.textContent = 'Baixar vídeo';
        }, 4000);
    };

    if (getComputedStyle(player).position === 'static') player.style.position = 'relative';
    player.appendChild(btn);
}

function removerBotao() {
    const btn = document.getElementById(ID_BOTAO);
    if (btn) btn.remove();
}

// Injeta agora e vigia a página. O YouTube troca de vídeo sem recarregar (SPA) e
// ainda re-renderiza o player durante o uso — então, além de recriar na mudança de
// URL, recolocamos o pill se ele sumir enquanto estivermos numa página de vídeo.
criarBotao();
let urlAtual = location.href;
new MutationObserver(() => {
    if (location.href !== urlAtual) {
        urlAtual = location.href;
        setTimeout(criarBotao, 500);
        return;
    }
    if (ehPaginaDeVideo() && !document.getElementById(ID_BOTAO)) criarBotao();
}).observe(document, { subtree: true, childList: true });
