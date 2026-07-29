// --- CONFIGURAÇÃO ---
let observadorDeMudancas = null;
let ultimaUrlRegistrada = "";
let enfileirandoEmAndamento = false;   // trava o beforeunload enquanto envia o curso

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

// Containers da árvore do curso: dão o CAMINHO (Curso/Módulo), não viram aula.
// Todo o resto é folha = aula, seja qual for o unitType (module, page, article...).
// Isso honra a intenção documentada: "nenhuma aula do curso é omitida".
const CONTAINERS = new Set(['course', 'set']);

function metaDe(no) {
    // O Skool às vezes entrega metadata como objeto, às vezes como string JSON.
    // Normaliza para objeto; devolve null se não der para aproveitar.
    if (!no) return null;
    const m = no.metadata;
    if (m && typeof m === 'object') return m;
    if (typeof m === 'string' && m) {
        try { return JSON.parse(m); } catch (e) { return null; }
    }
    return null;
}

// O texto da aula ("desc") é uma string que começa com "[v2]" (rich-text do
// Skool). Os recursos ("resources") são um JSON array de {title, link}.
// Ancoramos a busca nesses invariantes MEDIDOS — não no nome/lugar do campo,
// que varia. Assim o texto é capturado mesmo que o Skool o aninhe diferente.
function pareceDesc(v) {
    return typeof v === 'string' && v.startsWith('[v2]');
}

function pareceResources(v) {
    if (typeof v !== 'string') return false;
    const t = v.trim();
    if (!t.startsWith('[')) return false;
    try {
        const arr = JSON.parse(t);
        return Array.isArray(arr) && arr.length > 0 &&
               arr.some(i => i && typeof i === 'object' && (i.link || i.title));
    } catch (e) { return false; }
}

function buscarNaUnit(unit, aceita, profMax = 6) {
    // Busca DENTRO da própria unit, sem descer para OUTRA unit (id diferente),
    // para nunca pegar o texto de uma aula vizinha.
    let achado = '';
    (function anda(no, prof) {
        if (achado || !no || typeof no !== 'object' || prof > profMax) return;
        if (Array.isArray(no)) { for (const x of no) { anda(x, prof + 1); if (achado) return; } return; }
        for (const k of Object.keys(no)) { if (aceita(no[k])) { achado = no[k]; return; } }
        for (const k of Object.keys(no)) {
            const v = no[k];
            if (!v || typeof v !== 'object') continue;
            // não cruzar a fronteira para outra unit do curso
            if (v !== unit && typeof v.id === 'string' && v.unitType && v.id !== unit.id) continue;
            anda(v, prof + 1);
            if (achado) return;
        }
    })(unit, 0);
    return achado;
}

function coletarUnits(raiz) {
    // Travessia genérica: junta todo objeto que seja um "unit" do Skool
    // (id + unitType + metadata), sem depender de como o Skool aninha.
    const porId = {};
    const vistos = new Set();
    (function anda(no) {
        if (!no || typeof no !== 'object') return;
        if (Array.isArray(no)) { no.forEach(anda); return; }
        if (typeof no.id === 'string' && no.unitType && metaDe(no)) {
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
        const m = metaDe(atual) || {};
        if (atual.unitType === 'course') { curso = m.title; break; }
        if (atual.unitType === 'set') modulos.unshift(m.title);
        atual = porId[atual.parentId];
    }
    return { curso, modulos };
}

function slugsDaUrl() {
    // Na rota /[group]/classroom/[course], os slugs vêm direto do caminho ATUAL.
    // Isso reflete a aula/curso na tela AGORA, mesmo após navegação SPA — ao
    // contrário do __NEXT_DATA__, que fica preso ao curso do primeiro load.
    const partes = location.pathname.split('/');
    return { group: partes[1] || '', course: partes[3] || '' };
}

async function obterPagePropsDoCurso() {
    // BUG DA NAVEGAÇÃO SPA: o __NEXT_DATA__ é o SSR do PRIMEIRO carregamento e não
    // se atualiza quando o Skool troca de curso sem recarregar. Ler dele enfileirava
    // o curso ANTIGO (só um F5 corrigia). Aqui buscamos o JSON do curso ATUAL (pela
    // URL) no mesmo endpoint que o Skool usa internamente — o mesmo já usado para o
    // texto por aula, então roda com a sessão do usuário e é comprovadamente autorizado.
    const nd = obterNextData();
    const buildId = nd && nd.buildId;
    const { group, course } = slugsDaUrl();
    if (buildId && group && course) {
        // Inclui o md atual da URL quando houver: deixa o request idêntico ao que o
        // Skool faz ao abrir a aula (o mesmo já comprovado em buscarTextoDaAula).
        // A árvore de aulas não depende do md — ele só marca o módulo selecionado.
        const mdAtual = new URLSearchParams(location.search).get('md');
        let q = `group=${encodeURIComponent(group)}&course=${encodeURIComponent(course)}`;
        if (mdAtual) q += `&md=${encodeURIComponent(mdAtual)}`;
        const url = `${location.origin}/_next/data/${buildId}/${group}/classroom/${course}.json?${q}`;
        try {
            const r = await fetch(url, { credentials: 'include', headers: { 'x-nextjs-data': '1' } });
            if (r.ok) {
                const json = await r.json();
                const pp = json.pageProps || (json.props && json.props.pageProps);
                if (pp && pp.course) return pp;
                console.warn('[Loom] JSON fresco do curso sem pageProps.course; tentando cache local.');
            } else {
                console.warn(`[Loom] _next/data ${r.status} ao buscar curso atual; tentando cache local.`);
            }
        } catch (e) {
            console.warn('[Loom] falha ao buscar curso fresco; tentando cache local:', e);
        }
    }
    // Fallback: só confia no __NEXT_DATA__ se ele for COMPROVADAMENTE do curso ATUAL
    // (o slug `name` bate com o da URL). Se não bater — ou não houver slug na URL — o
    // cache está velho (navegação SPA para outro curso): enfileirá-lo mandaria o curso
    // ERRADO, que é justamente o bug que esta função corrige. Nesse caso, abortamos.
    const ppLocal = nd && nd.props && nd.props.pageProps;
    const nomeLocal = ppLocal && ppLocal.course && ppLocal.course.course && ppLocal.course.course.name;
    if (course && ppLocal && ppLocal.course && nomeLocal === course) {
        return ppLocal;
    }
    console.warn('[Loom] Sem dados frescos do curso e cache desatualizado — recarregue a página (F5).');
    return null;
}

async function coletarAulasDoCurso() {
    const pp = await obterPagePropsDoCurso();
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

    // Diagnóstico: quantos units de cada unitType existem. Se uma aula "não baixa",
    // isto revela na hora se ela era de um tipo que estávamos descartando.
    const porTipo = {};
    for (const u of Object.values(porId)) porTipo[u.unitType] = (porTipo[u.unitType] || 0) + 1;
    console.log('[Loom] unitTypes encontrados:', porTipo);

    const aulas = [];
    for (const unit of Object.values(porId)) {
        // Containers (course/set) só dão o caminho — não viram aula.
        // Todo o resto é folha e ENTRA, seja qual for o unitType: assim uma aula
        // de texto (unitType diferente de 'module') não some em silêncio.
        if (CONTAINERS.has(unit.unitType)) continue;

        const meta = metaDe(unit) || {};
        const videoLink = meta.videoLink || '';
        const ehLoom = /loom\.com\/(embed|share)\//.test(videoLink);
        const ehYoutube = /(youtube\.com|youtu\.be)/.test(videoLink);
        const ehVideo = ehLoom || ehYoutube;   // o servidor roteia Loom vs YouTube

        // Texto/recursos: tenta o campo direto; se vazio, busca dentro da unit
        // por uma string "[v2]" (desc) ou um array de recursos. Ancorado nos
        // invariantes medidos, não no nome do campo.
        let desc = meta.desc || '';
        if (!desc) desc = buscarNaUnit(unit, pareceDesc);
        let resources = meta.resources || '';
        if (!pareceResources(resources)) {
            const r = buscarNaUnit(unit, pareceResources);
            if (r) resources = r;
        }
        const temTexto = !!(desc || (resources && resources !== '[]'));

        // Inclui TODA aula do curso — inclusive as vazias (sem vídeo nem texto).
        // O servidor grava um .md placeholder para elas, para que nenhuma aula
        // suma sem aviso. Só aulas com vídeo de OUTRA plataforma (YouTube etc.)
        // seguem sem o .mp4 — mas o texto/registro ainda vai.

        const { curso, modulos } = caminhoDaAula(unit, porId);
        const pasta = [comunidade, curso, ...modulos]
            .filter(Boolean)
            .map(limparTexto)
            .join('/');

        aulas.push({
            url: ehVideo ? videoLink : '',
            folder: pasta,
            filename: limparTexto(meta.title || 'Aula sem titulo'),
            desc: desc,
            resources: resources,
            _temVideo: ehVideo,
            _temTexto: temTexto,
            _unitType: unit.unitType,
            _id: unit.id,   // = o "md" da aula; usado para buscar o texto individual
        });
    }
    return aulas;
}

// --- 1.6. TEXTO POR AULA (via endpoint de dados do Next.js do Skool) ---
// O __NEXT_DATA__ só traz o `desc` da aula ABERTA. Para pegar o texto das
// demais, buscamos o JSON de cada aula no mesmo endpoint que o Skool usa ao
// trocar de aula: /_next/data/<buildId>/<group>/classroom/<course>.json?md=<id>
// A extensão roda com a sessão do usuário (cookies), então o fetch é autorizado.

function obterContexto() {
    // buildId sai do __NEXT_DATA__ (estável em todo o app, não muda entre cursos).
    // group/course vêm da URL ATUAL — não do nd.query, que fica preso ao primeiro
    // load e apontava para o curso ERRADO após navegação SPA.
    const nd = obterNextData();
    const { group, course } = slugsDaUrl();
    return { buildId: nd && nd.buildId, group, course };
}

function extrairTextoParaMd(pp, md) {
    // No JSON buscado para md=X, a aula X é a "aberta" e carrega o desc completo.
    // Atribui SEMPRE pelo id (id === md) para nunca misturar com aula vizinha.
    if (!pp || !md) return { desc: '', resources: '' };
    const porId = coletarUnits(pp.course || pp);
    const unit = porId[md];
    if (!unit) return { desc: '', resources: '' };
    const meta = metaDe(unit) || {};
    const desc = pareceDesc(meta.desc) ? meta.desc : (buscarNaUnit(unit, pareceDesc) || (meta.desc || ''));
    const resources = pareceResources(meta.resources) ? meta.resources : (buscarNaUnit(unit, pareceResources) || '');
    return { desc, resources };
}

async function buscarTextoDaAula(md, ctx) {
    if (!md || !ctx || !ctx.buildId || !ctx.group || !ctx.course) return { desc: '', resources: '' };
    const q = `md=${encodeURIComponent(md)}&group=${encodeURIComponent(ctx.group)}` +
              `&course=${encodeURIComponent(ctx.course)}`;
    const url = `${location.origin}/_next/data/${ctx.buildId}/${ctx.group}/classroom/${ctx.course}.json?${q}`;
    try {
        const r = await fetch(url, { credentials: 'include', headers: { 'x-nextjs-data': '1' } });
        if (!r.ok) { console.warn(`[Loom] _next/data ${r.status} para md ${md}`); return { desc: '', resources: '' }; }
        const json = await r.json();
        const pp = json.pageProps || (json.props && json.props.pageProps);
        return extrairTextoParaMd(pp, md);
    } catch (e) {
        console.warn(`[Loom] falha ao buscar texto da aula ${md}:`, e);
        return { desc: '', resources: '' };
    }
}

// Executa `fn` sobre `itens` com no máximo `limite` em voo ao mesmo tempo.
// A concorrência limitada é o "respiro": rápida o bastante para fechar o curso
// inteiro em ~1-2s, sem disparar N requests de uma vez contra o Skool/servidor.
async function mapConcorrente(itens, limite, fn) {
    let i = 0;
    const trabalhadores = [];
    for (let w = 0; w < Math.min(limite, itens.length); w++) {
        trabalhadores.push((async () => {
            while (i < itens.length) {
                const idx = i++;
                await fn(itens[idx], idx);
            }
        })());
    }
    await Promise.all(trabalhadores);
}

async function enfileirarCurso(aulas, ctx, aoProgredir) {
    // BUG DO ENFILEIRAMENTO PERDIDO: antes isto era um loop SEQUENCIAL com 400ms de
    // espera por aula. Um curso grande levava dezenas de segundos e, se a página
    // recarregasse ou navegasse no meio, as aulas ainda não enviadas eram PERDIDAS —
    // o loop morria junto com o content script. Agora capturamos os textos e
    // disparamos os POSTs com concorrência limitada, fechando tudo em poucos segundos.
    // Combinado com o guarda `beforeunload`, um reload deixa de perder aulas.
    const n = aulas.length;
    let enviadas = 0, textos = 0, comTexto = 0;

    // Fase 1: captura o texto de cada aula (o desc só vem no JSON da aula aberta).
    // Contra o Skool, mantemos concorrência BAIXA + um respiro por request: o antigo
    // loop espaçava 400ms de propósito ("não floodar"); aqui preservamos essa proteção
    // (senão N fetches em rajada podem levar 429 e perder o texto em silêncio).
    const CONC_TEXTO = 4, RESPIRO_MS = 200;
    await mapConcorrente(aulas, CONC_TEXTO, async (aula) => {
        if (!aula.desc && aula._id && ctx && ctx.buildId) {
            const t = await buscarTextoDaAula(aula._id, ctx);
            if (t.desc) aula.desc = t.desc;
            if (t.resources && !pareceResources(aula.resources)) aula.resources = t.resources;
            await new Promise(r => setTimeout(r, RESPIRO_MS));   // respiro anti-flood
        }
        if (aula.desc || pareceResources(aula.resources)) comTexto++;
        textos++;
        if (aoProgredir) aoProgredir('texto', textos, n);
    });

    // Fase 2: envia os pedidos ao servidor LOCAL. Cada POST é independente e o servidor
    // responde na hora, fazendo o próprio enfileiramento (ThreadPoolExecutor). É
    // localhost, então concorrência maior é segura e não precisa de respiro.
    const CONC_ENVIO = 6;
    await mapConcorrente(aulas, CONC_ENVIO, async (aula) => {
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
        if (aoProgredir) aoProgredir('envio', enviadas, n);
    });

    console.log(`[Loom] textos capturados: ${comTexto}/${n} aulas`);
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

    btn.onclick = async () => {
        if (btn.disabled) return;   // já enfileirando; ignora cliques repetidos

        const aulas = await coletarAulasDoCurso();
        if (!aulas.length) {
            // Pode ser curso realmente vazio OU dados desatualizados (ver console).
            btn.innerText = '❌ Nada encontrado — recarregue (F5)';
            setTimeout(() => { btn.innerText = '📚 Baixar curso inteiro'; }, 4000);
            return;
        }

        const comVideo = aulas.filter(a => a._temVideo).length;
        const soTexto = aulas.length - comVideo;

        // Log informativo — dá para conferir os caminhos no console se quiser,
        // mas NÃO é mais uma trava: o download dispara na mesma ação.
        // A coluna 'texto' mostra se desc/resources foram capturados: uma aula de
        // texto que apareça com texto='—' aponta o problema direto ao campo.
        console.log(`[Loom] === ${aulas.length} aulas ` +
                    `(${comVideo} com vídeo, ${soTexto} sem vídeo) ===`);
        console.table(aulas.map(a => ({
            pasta: a.folder,
            arquivo: a.filename,
            tipo: a._unitType,
            video: a._temVideo ? 'sim' : '—',
            texto: a._temTexto ? 'sim' : '—',
        })));

        // Uma única confirmação antes de disparar downloads em massa.
        const ok = confirm(
            `Baixar o curso inteiro?\n\n` +
            `${aulas.length} aulas — ${comVideo} com vídeo, ${soTexto} só texto.\n` +
            `Isso vai enfileirar ${aulas.length} pedidos no servidor local (localhost:5000).`
        );
        if (!ok) {
            btn.innerText = '📚 Baixar curso inteiro';
            return;
        }

        // Confirmado: dispara os POSTs. Busca o texto de cada aula em paralelo
        // com o enfileiramento (o desc só vem no JSON da aula aberta).
        btn.disabled = true;
        enfileirandoEmAndamento = true;   // ativa o guarda beforeunload
        const ctx = obterContexto();
        let enviadas = 0;
        try {
            enviadas = await enfileirarCurso(aulas, ctx, (fase, i, n) => {
                btn.innerText = fase === 'texto'
                    ? `📝 Lendo textos ${i}/${n}...`
                    : `📡 Enfileirando ${i}/${n}...`;
            });
        } finally {
            enfileirandoEmAndamento = false;   // libera mesmo se algo falhar no meio
        }
        btn.innerText = `⏳ ${enviadas} aulas na fila — veja o terminal`;
        setTimeout(() => {
            btn.disabled = false;
            btn.innerText = '📚 Baixar curso inteiro';
        }, 6000);
    };
}

// --- 2.6. BOTÃO DE VÍDEO VIMEO (posts de comunidade) ---
// O player do Vimeo é um blob (MediaSource) — não dá pra baixar direto. Mas o
// servidor baixa via yt-dlp SE receber a URL do player + o Referer da página.
// Aqui a extensão descobre o id do vídeo e mostra o botão; o Referer = location.href.

function acharVimeoId() {
    // Junta candidatos: src dos iframes + tudo que a página já requisitou
    // (Performance API pega o request do player e o do oembed, mesmo sem iframe visível).
    const fontes = [];
    for (const f of document.querySelectorAll('iframe')) {
        if (f.src) fontes.push(f.src);
    }
    try {
        for (const e of performance.getEntriesByType('resource')) fontes.push(e.name);
    } catch (e) { /* Performance pode não estar disponível */ }

    for (const s of fontes) {
        // player.vimeo.com/video/12345  ou  ...oembed.json?url=...vimeo.com%2F12345
        const m = s.match(/player\.vimeo\.com\/video\/(\d+)/) ||
                  s.match(/vimeo\.com(?:%2F|\/)(\d{6,})/);
        if (m) return m[1];
    }
    return null;
}

function criarBotaoVimeo() {
    if (document.querySelector('.botao-vimeo')) return;   // já existe
    const id = acharVimeoId();
    if (!id) return;

    const btn = document.createElement('button');
    btn.className = 'botao-vimeo';
    btn.innerText = '⬇ Baixar vídeo (Vimeo)';
    document.body.appendChild(btn);

    btn.onclick = async () => {
        if (btn.disabled) return;
        btn.disabled = true;
        btn.innerText = '📡 Enviando...';
        const dados = obterDadosDaPagina();   // mesma lógica de pasta/nome do botão de aula
        try {
            const resp = await fetch(SERVIDOR, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    url: `https://player.vimeo.com/video/${id}`,
                    folder: dados.folder,
                    filename: dados.filename,
                    referer: location.href,   // libera o Vimeo restrito por domínio
                }),
            });
            await resp.json();
            btn.innerText = '⏳ Na fila';
        } catch (e) {
            console.error('[Vimeo] servidor offline?', e);
            btn.innerText = '❌ Servidor offline?';
        }
        setTimeout(() => { btn.disabled = false; btn.innerText = '⬇ Baixar vídeo (Vimeo)'; }, 4000);
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
        // Botão de vídeo Vimeo (posts de comunidade e afins).
        criarBotaoVimeo();
    });
    
    // Começa a vigiar o corpo da página
    observadorDeMudancas.observe(document.body, { childList: true, subtree: true });
}

// Inicia o processo
iniciarObservador();
criarBotaoCurso();
criarBotaoVimeo();

// Guarda contra perder aulas: se o usuário recarregar ou fechar a aba ENQUANTO o
// curso está sendo enfileirado, o navegador mostra o aviso nativo de "sair da
// página?". Isso ataca exatamente o cenário relatado (recarregar no meio do envio).
window.addEventListener('beforeunload', (e) => {
    if (enfileirandoEmAndamento) {
        e.preventDefault();
        e.returnValue = '';   // exigido por alguns navegadores para exibir o aviso
    }
});

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