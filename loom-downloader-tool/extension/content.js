// --- CONFIGURAÇÃO ---
let observadorDeMudancas = null;
let ultimaUrlRegistrada = "";

// --- 1. FUNÇÕES AUXILIARES ---

function limparTexto(texto) {
    if (!texto) return "";
    // Remove caracteres especiais, mas mantém acentos e emojis
    // Removemos: < > : " / \ | ? * (Proibidos em pastas do Windows)
    return texto.replace(/[<>:"/\\|?*]/g, '').trim();
}

function obterDadosDaPagina() {
    /**
     * Analisa o título da página para descobrir:
     * 1. Nome da Comunidade
     * 2. Nome do Curso
     * 3. Nome da Aula
     */
    
    // Pega o título da aba do navegador
    let tituloBruto = document.title;
    
    // Remove sulfixos irrelevantes gerados pelo Skool
    tituloBruto = tituloBruto.replace(/ - Skool$/i, '');

    // Valores padrão caso a lógica falhe
    let comunidade = "Geral";
    let curso = "Curso Desconhecido";
    let aula = "Aula Sem Titulo";

    // --- ESTRATÉGIA DO PONTO MÉDIO (·) ---
    // O Skool costuma formatar assim: "Nome da Aula - Nome do Curso · NOME DA COMUNIDADE"
    // O caractere chave aqui é o ponto médio "·"
    if (tituloBruto.includes('·')) {
        const partesPonto = tituloBruto.split('·');
        
        // A parte da DIREITA do ponto é sempre a Comunidade
        comunidade = limparTexto(partesPonto[partesPonto.length - 1]);
        
        // A parte da ESQUERDA contém "Aula - Curso"
        // Juntamos o resto (caso haja mais de um ponto raro) para processar
        let restoEsquerda = partesPonto.slice(0, -1).join('·').trim();

        // Agora separamos Aula e Curso pelo traço " - "
        const partesTraco = restoEsquerda.split(' - ');
        
        if (partesTraco.length >= 2) {
            // O padrão é que o ÚLTIMO elemento seja o Curso
            curso = limparTexto(partesTraco.pop());
            
            // Tudo o que sobra antes é o nome da Aula
            aula = limparTexto(partesTraco.join(' - '));
        } else {
            // Se não tiver traço, assumimos que o texto todo é o Curso
            curso = limparTexto(restoEsquerda);
            aula = "Aula Geral"; 
            
            // Tenta salvar pegando o H1 da página se a aula ficou genérica
            const h1 = document.querySelector('h1');
            if (h1) aula = limparTexto(h1.innerText);
        }

    } else {
        // --- FALLBACK (PLANO B) ---
        // Se não tiver o ponto (·), usamos a lógica antiga baseada apenas nos traços
        const partes = tituloBruto.split(' - ');
        if (partes.length >= 2) {
            curso = limparTexto(partes.pop()); // Último = Curso
            aula = limparTexto(partes.join(' - ')); // Resto = Aula
            
            // Tenta pegar a comunidade da URL (ex: skool.com/COMUNIDADE/...)
            try {
                const caminhoUrl = window.location.pathname.split('/');
                if (caminhoUrl[1]) comunidade = caminhoUrl[1].toUpperCase();
            } catch(e) {}
        }
    }

    // Monta a pasta final no formato: COMUNIDADE / CURSO
    const pastaFinal = `${comunidade}/${curso}`;

    return {
        folder: pastaFinal,
        filename: aula
    };
}

// --- 1.5. CRAWLER DO CURSO INTEIRO ---
// Lê o __NEXT_DATA__ do Skool (JSON de SSR do Next.js, presente no DOM) e monta
// a lista de TODAS as aulas do curso de uma vez. Não precisa navegar aula a aula.

const SERVIDOR = 'http://localhost:5000/baixar';

function obterNextData() {
    // __NEXT_DATA__ é uma tag <script> no DOM — o content script alcança.
    const tag = document.getElementById('__NEXT_DATA__');
    if (!tag) return null;
    try {
        return JSON.parse(tag.textContent);
    } catch (e) {
        console.error('[Loom] __NEXT_DATA__ não é JSON válido:', e);
        return null;
    }
}

function coletarUnits(raiz) {
    // Travessia genérica: junta todo objeto que seja um "unit" do Skool
    // (id + unitType + metadata), sem depender de como o Skool aninha.
    const porId = {};
    const vistos = new Set();
    (function anda(no) {
        if (!no || typeof no !== 'object') return;
        if (Array.isArray(no)) { no.forEach(anda); return; }
        if (typeof no.id === 'string' && no.unitType && no.metadata && typeof no.metadata === 'object') {
            if (!vistos.has(no.id)) { vistos.add(no.id); porId[no.id] = no; }
        }
        for (const k of Object.keys(no)) anda(no[k]);
    })(raiz);
    return porId;
}

function caminhoDaAula(unit, porId) {
    // Sobe pela cadeia parentId: os 'set' viram Módulos; o 'course' vira Curso.
    const modulos = [];
    let curso = null;
    let atual = porId[unit.parentId];
    let guarda = 0;
    while (atual && guarda++ < 20) {
        if (atual.unitType === 'course') { curso = atual.metadata.title; break; }
        if (atual.unitType === 'set') modulos.unshift(atual.metadata.title);
        atual = porId[atual.parentId];
    }
    return { curso, modulos };
}

function coletarAulasDoCurso() {
    const nd = obterNextData();
    const pp = nd && nd.props && nd.props.pageProps;
    if (!pp || !pp.course) {
        console.warn('[Loom] Não achei os dados do curso nesta página.');
        return [];
    }

    // Nome "bonito" da comunidade (ex: BACKROOM.EXE), não o slug (backroomexe-3259).
    // O displayName é o mesmo que o botão de aula individual usa (via document.title),
    // então os dois botões gravam na MESMA pasta de comunidade.
    const cg = pp.currentGroup || {};
    const comunidade = (cg.metadata && cg.metadata.displayName) || cg.name || 'Skool';
    const porId = coletarUnits(pp.course);

    const aulas = [];
    for (const unit of Object.values(porId)) {
        if (unit.unitType !== 'module') continue;  // só aulas são folhas

        const meta = unit.metadata || {};
        const videoLink = meta.videoLink || '';
        const ehLoom = /loom\.com\/(embed|share)\//.test(videoLink);
        const temTexto = (meta.desc && meta.desc.length > 4) ||
                         (meta.resources && meta.resources.length > 2);

        // Pula aulas sem nada aproveitável (nem Loom, nem texto).
        if (!ehLoom && !temTexto) continue;

        const { curso, modulos } = caminhoDaAula(unit, porId);
        const pasta = [comunidade, curso, ...modulos]
            .filter(Boolean)
            .map(limparTexto)
            .join('/');

        aulas.push({
            url: ehLoom ? videoLink : '',
            folder: pasta,
            filename: limparTexto(meta.title || 'Aula sem titulo'),
            desc: meta.desc || '',
            resources: meta.resources || '',
            _temVideo: ehLoom,
        });
    }
    return aulas;
}

async function enfileirarCurso(aulas, aoProgredir) {
    // Rate limit entre POSTs: não floodar o servidor nem o CDN.
    let enviadas = 0;
    for (const aula of aulas) {
        try {
            await fetch(SERVIDOR, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    url: aula.url,
                    folder: aula.folder,
                    filename: aula.filename,
                    desc: aula.desc,
                    resources: aula.resources,
                }),
            });
        } catch (err) {
            console.error(`[Loom] Falha ao enfileirar "${aula.filename}":`, err);
        }
        enviadas++;
        if (aoProgredir) aoProgredir(enviadas, aulas.length);
        await new Promise(r => setTimeout(r, 400));  // respiro entre pedidos
    }
    return enviadas;
}

// --- 2. INJEÇÃO DO BOTÃO ---

function criarBotaoDownload(iframe) {
    // Evita criar dois botões no mesmo vídeo
    if (iframe.parentNode.querySelector('.meu-botao-download')) return;

    // Garante que o container do vídeo tenha posição relativa
    // (Isso é necessário para o botão "absolute" ficar preso ao vídeo, não à página)
    if (getComputedStyle(iframe.parentNode).position === 'static') {
        iframe.parentNode.style.position = 'relative';
    }

    const btn = document.createElement('button');
    btn.innerText = '⬇ Baixar Aula';
    btn.className = 'meu-botao-download'; // Estilizado no style.css
    
    // Adiciona o evento de clique
    btn.onclick = (e) => {
        e.preventDefault();
        e.stopPropagation();

        const dados = obterDadosDaPagina(); 
        const urlEmbed = iframe.src;

        // Feedback Visual: "Processando..."
        btn.innerText = '📡 ...';
        btn.style.backgroundColor = '#95a5a6'; // Cinza

        // Envia para o nosso servidor Python
        fetch('http://localhost:5000/baixar', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                url: urlEmbed,
                folder: dados.folder,
                filename: dados.filename
            })
        })
        .then(r => r.json())
        .then(d => {
            // Feedback Visual: "Sucesso"
            btn.innerText = '⏳ Na Fila';
            btn.style.backgroundColor = '#3498db'; // Azul
            
            // Volta ao normal depois de 4 segundos
            setTimeout(() => {
                btn.innerText = '⬇ Baixar Aula';
                btn.style.backgroundColor = ''; // Remove cor inline para voltar ao CSS original
            }, 4000);
        })
        .catch(err => {
            console.error("Erro ao conectar com servidor:", err);
            btn.innerText = '❌ Erro (Servidor Offline?)';
            btn.style.backgroundColor = '#e74c3c'; // Vermelho
        });
    };

    // Insere o botão logo antes do iframe do vídeo
    iframe.parentNode.insertBefore(btn, iframe);
}

// --- 2.5. BOTÃO "BAIXAR CURSO INTEIRO" ---

function criarBotaoCurso() {
    if (document.querySelector('.botao-curso-inteiro')) return;   // já existe
    // Só faz sentido numa página de classroom com dados de curso.
    if (!document.getElementById('__NEXT_DATA__')) return;
    if (!/\/classroom\//.test(location.pathname)) return;

    const btn = document.createElement('button');
    btn.className = 'botao-curso-inteiro';
    btn.innerText = '📚 Baixar curso inteiro';
    document.body.appendChild(btn);

    let aulasPendentes = null;   // preenchido no dry-run (1º clique)

    btn.onclick = async () => {
        // --- ETAPA 1: dry-run. Coleta e mostra, sem baixar nada. ---
        if (!aulasPendentes) {
            const aulas = coletarAulasDoCurso();
            if (!aulas.length) {
                btn.innerText = '❌ Nenhuma aula encontrada';
                setTimeout(() => { btn.innerText = '📚 Baixar curso inteiro'; }, 3000);
                return;
            }
            aulasPendentes = aulas;

            const comVideo = aulas.filter(a => a._temVideo).length;
            const soTexto = aulas.length - comVideo;

            console.log(`[Loom] === PRÉVIA: ${aulas.length} aulas ` +
                        `(${comVideo} com vídeo, ${soTexto} só texto) ===`);
            console.table(aulas.map(a => ({
                pasta: a.folder, arquivo: a.filename, video: a._temVideo ? 'sim' : '—',
            })));
            console.log('[Loom] Confira acima. Clique de novo para ENFILEIRAR.');

            btn.innerText = `✅ Enfileirar ${aulas.length} aulas? (confira o console)`;
            btn.classList.add('confirmar');
            return;
        }

        // --- ETAPA 2: confirma. Dispara os POSTs. ---
        const total = aulasPendentes.length;
        btn.disabled = true;
        btn.classList.remove('confirmar');
        const enviadas = await enfileirarCurso(aulasPendentes, (i, n) => {
            btn.innerText = `📡 Enfileirando ${i}/${n}...`;
        });
        btn.innerText = `⏳ ${enviadas} aulas na fila — veja o terminal`;
        aulasPendentes = null;
        setTimeout(() => {
            btn.disabled = false;
            btn.innerText = '📚 Baixar curso inteiro';
        }, 6000);
    };
}

// --- 3. OBSERVADORES (O VIGIA) ---

function iniciarObservador() {
    // Se já existir um vigia, demite-o antes de contratar o novo (evita duplicidade)
    if (observadorDeMudancas) observadorDeMudancas.disconnect();
    
    // Cria um novo vigia que fica olhando o HTML da página
    observadorDeMudancas = new MutationObserver((mutations) => {
        // Procura por iframes do Loom
        const iframes = document.querySelectorAll('iframe');
        iframes.forEach(iframe => {
            if (iframe.src.includes('loom.com/embed') || iframe.src.includes('loom.com/share')) {
                criarBotaoDownload(iframe);
            }
        });
        // Botão de curso inteiro (aparece em qualquer aula do classroom).
        criarBotaoCurso();
    });
    
    // Começa a vigiar o corpo da página
    observadorDeMudancas.observe(document.body, { childList: true, subtree: true });
}

// Inicia o processo
iniciarObservador();
criarBotaoCurso();

// Detecção de Navegação em SPA (Single Page Application)
// Sites modernos não recarregam a página ao mudar de aula, então vigiamos a URL.
let urlAtual = location.href; 
new MutationObserver(() => {
  if (location.href !== urlAtual) {
    urlAtual = location.href;
    // Espera 1 segundo para o novo conteúdo carregar e reinicia o vigia
    setTimeout(iniciarObservador, 1000); 
  }
}).observe(document, {subtree: true, childList: true});