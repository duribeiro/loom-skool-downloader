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
    return extrairAulas(pp);
}

async function contextoCurso() {
    // Para o popup (central de controle): título e nº de aulas do curso da aba atual.
    const pp = await obterPagePropsDoCurso();
    if (!pp || !pp.course) return { ok: false };
    const meta = (pp.course.course && metaDe(pp.course.course)) || {};
    return { ok: true, title: meta.title || 'Curso', count: extrairAulas(pp).length };
}

function extrairAulas(pp) {
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
        const ehLink = ehLoom || ehYoutube;   // o servidor roteia Loom vs YouTube

        // VÍDEO HOSPEDADO NO PRÓPRIO SKOOL: a aula não tem `videoLink`, só `videoId`.
        // MEDIDO: 32 das 280 aulas de ai-makers são assim, e o curso "Supabase" é
        // 100% desse tipo — todas eram tratadas como "sem vídeo" e só viravam .md.
        // A URL do stream não dá para montar aqui: depende de playbackId+playbackToken,
        // que só vêm no JSON da aula ABERTA. Marcamos e resolvemos na fase 1 do
        // enfileiramento, que já busca esse JSON por aula (custo zero de request).
        const videoIdSkool = (!ehLink && meta.videoId) ? String(meta.videoId) : '';
        const ehVideo = ehLink || !!videoIdSkool;

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
            url: ehLink ? videoLink : '',   // do Skool, a URL só nasce na fase 1
            folder: pasta,
            filename: limparTexto(meta.title || 'Aula sem titulo'),
            desc: desc,
            resources: resources,
            _videoId: videoIdSkool,
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

// Host do HLS do Skool (Mux white-label) — o mesmo que services/skool.py reconhece.
const HOST_STREAM_SKOOL = 'stream.video.skool.com';

function extrairVideoSkool(pp, videoId) {
    // MEDIDO: o JSON da aula ABERTA traz `pageProps.video` com o par
    // playbackId + playbackToken. Sem o token o CDN responde 403.
    //
    // Conferimos `v.id === videoId` de propósito: as buscas por aula rodam
    // concorrentes, e sem essa checagem uma resposta trocada colaria o vídeo de
    // OUTRA aula neste registro — erro que ninguém perceberia até assistir.
    if (!pp || !videoId) return '';
    const v = pp.video;
    if (!v || v.id !== videoId || !v.playbackId || !v.playbackToken) return '';
    return `https://${HOST_STREAM_SKOOL}/${v.playbackId}.m3u8?token=${v.playbackToken}`;
}

// --- VÍDEO QUE MORA NUM POST FIXADO ---
// MEDIDO em 12/08/2026 na ai-makers (280 aulas): 52 aulas NÃO têm vídeo próprio
// (`videoLink` e `videoId` nulos) e guardam o vídeo num POST FIXADO à aula —
// 37 de 85 em "Office Hours com Well Pires" e 12 de 20 em "Founders Talk".
// Para a extensão elas pareciam aulas vazias: viravam um .md placeholder e sumiam
// sem nenhum aviso. Era a maior perda silenciosa do projeto, 18% do acervo.
//
// A pegadinha é o nome do campo: no post ele se chama `videoIds` — PLURAL. Não é
// `videoLink` nem `videoId`, os dois únicos que a leitura da unit consultava.
//
// Onde cada coisa mora (medido, não suposto):
//   - `pageProps.pinnedPosts` pertence à aula ABERTA, não à unit. Varrer a listagem
//     do curso nunca acha: cada requisição só revela os pins de UMA aula.
//   - o JSON da aula traz só o ID do vídeo; playbackId+playbackToken exigem buscar
//     o post pelo slug que vem em `post.name`.

function postsFixadosComVideo(pp) {
    const pins = (pp && pp.pinnedPosts) || [];
    const out = [];
    for (const p of pins) {
        const post = p && p.post;
        const vid = post && post.metadata && post.metadata.videoIds;
        if (vid && post.name) out.push({ slug: post.name, videoId: String(vid), titulo: (post.metadata.title || '') });
    }
    return out;
}

async function resolverVideoDePostFixado(pin, ctx) {
    if (!pin || !ctx || !ctx.buildId || !ctx.group) return '';
    const url = `${location.origin}/_next/data/${ctx.buildId}/${ctx.group}/${pin.slug}.json`;
    try {
        const r = await fetch(url, { credentials: 'include', headers: { 'x-nextjs-data': '1' } });
        if (!r.ok) { console.warn(`[Sifão] post fixado ${pin.slug}: HTTP ${r.status}`); return ''; }
        const pp = (await r.json()).pageProps || {};

        // O objeto do vídeo não fica num caminho fixo do JSON, então varremos.
        // Conferir `id === pin.videoId` é OBRIGATÓRIO: um post pode ter mais de um
        // vídeo, e pegar o primeiro que aparecesse colaria o vídeo errado na aula —
        // erro que ninguém nota até sentar para assistir.
        let achado = null;
        const visto = new Set();
        (function varrer(o) {
            if (!o || typeof o !== 'object' || achado || visto.has(o)) return;
            visto.add(o);
            if (o.id === pin.videoId && o.playbackId && o.playbackToken) { achado = o; return; }
            for (const v of Object.values(o)) varrer(v);
        })(pp);

        if (!achado) { console.warn(`[Sifão] post ${pin.slug} não tem o vídeo ${pin.videoId}`); return ''; }
        return `https://${HOST_STREAM_SKOOL}/${achado.playbackId}.m3u8?token=${achado.playbackToken}`;
    } catch (e) {
        console.warn(`[Sifão] falha ao ler o post fixado ${pin.slug}:`, e);
        return '';
    }
}

async function buscarTextoDaAula(md, ctx, videoId) {
    if (!md || !ctx || !ctx.buildId || !ctx.group || !ctx.course) return { desc: '', resources: '' };
    const q = `md=${encodeURIComponent(md)}&group=${encodeURIComponent(ctx.group)}` +
              `&course=${encodeURIComponent(ctx.course)}`;
    const url = `${location.origin}/_next/data/${ctx.buildId}/${ctx.group}/classroom/${ctx.course}.json?${q}`;
    try {
        const r = await fetch(url, { credentials: 'include', headers: { 'x-nextjs-data': '1' } });
        if (!r.ok) { console.warn(`[Loom] _next/data ${r.status} para md ${md}`); return { desc: '', resources: '' }; }
        const json = await r.json();
        const pp = json.pageProps || (json.props && json.props.pageProps);
        const out = extrairTextoParaMd(pp, md);
        // Mesma resposta, nenhum request a mais: o vídeo do Skool vem daqui.
        out.urlVideo = extrairVideoSkool(pp, videoId);
        // E os posts fixados, que é onde mora o vídeo das aulas "vazias".
        out.postsFixados = out.urlVideo ? [] : postsFixadosComVideo(pp);
        return out;
    } catch (e) {
        console.warn(`[Loom] falha ao buscar texto da aula ${md}:`, e);
        return { desc: '', resources: '' };
    }
}

// --- ARQUIVOS ANEXOS DA AULA ---
// `resources` tem DUAS formas: link ({title, link}) e ARQUIVO ({title, file_id,
// file_name, file_content_type}). O `pareceResources` aceita as duas (ambas têm
// `title`), então o anexo virava só um nome no .md e os bytes nunca eram buscados.
// MEDIDO em ai-makers: 44 aulas com anexo, 38 delas na Biblioteca de Templates —
// curso em que o anexo É o produto e o vídeo só explica o template.

const API_ARQUIVOS_SKOOL = 'https://api2.skool.com/files';

function anexosDeResources(resources) {
    if (!resources) return [];
    let arr;
    try {
        arr = typeof resources === 'string' ? JSON.parse(resources) : resources;
    } catch (e) { return []; }
    if (!Array.isArray(arr)) return [];
    return arr
        .filter(i => i && i.file_id)
        .map(i => ({
            fileId: String(i.file_id),
            nome: String(i.file_name || i.title || i.file_id),
        }));
}

async function resolverUrlAnexo(fileId) {
    // MEDIDO: é POST (GET responde 405) e a resposta é TEXTO PURO com a URL assinada
    // em files.skool.com — que já NÃO precisa de cookie. Por isso o servidor consegue
    // baixar sozinho: a extensão só precisa entregar a URL resolvida.
    const url = `${API_ARQUIVOS_SKOOL}/${encodeURIComponent(fileId)}/download-url?expire=28800`;
    try {
        const r = await fetch(url, { method: 'POST', credentials: 'include' });
        if (!r.ok) { console.warn(`[Sifão] anexo ${fileId}: HTTP ${r.status}`); return ''; }
        const link = (await r.text()).trim();
        return /^https:\/\//.test(link) ? link : '';
    } catch (e) {
        console.warn(`[Sifão] falha ao resolver anexo ${fileId}:`, e);
        return '';
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
        // No modo COMUNIDADE cada aula vem de um curso diferente, então o ctx viaja
        // junto com a aula (`_ctx`). Buscar o texto com o ctx da aba mandaria o
        // `course` errado no request e o texto voltaria vazio, em silêncio.
        // No modo curso único não há `_ctx` e todas compartilham o ctx da aba.
        const ctxAula = aula._ctx || ctx;
        // Busca se falta o texto OU se há vídeo do Skool ainda sem URL resolvida.
        // Sem a segunda condição, uma aula que já tivesse `desc` pularia o fetch e
        // o vídeo dela nunca seria descoberto — some sem aviso.
        const faltaVideo = !!aula._videoId && !aula.url;
        // Aula SEM vídeo nenhum também precisa da busca: o vídeo dela pode estar num
        // post fixado, e isso só aparece no JSON da aula aberta. Sem esta condição as
        // 52 aulas órfãs eram puladas — o `desc` delas é um parágrafo vazio, que é
        // string truthy, então `!aula.desc` dava false e nada era buscado.
        const semVideoNenhum = !aula._temVideo && !aula.url;
        if ((!aula.desc || faltaVideo || semVideoNenhum) && aula._id && ctxAula && ctxAula.buildId) {
            const t = await buscarTextoDaAula(aula._id, ctxAula, aula._videoId);
            if (t.desc) aula.desc = t.desc;
            if (t.resources && !pareceResources(aula.resources)) aula.resources = t.resources;
            if (t.urlVideo && !aula.url) aula.url = t.urlVideo;

            // Último recurso: o vídeo está num post fixado à aula.
            if (!aula.url && t.postsFixados && t.postsFixados.length) {
                if (t.postsFixados.length > 1) {
                    // MEDIDO: 1 aula em 280 tem 2 posts com vídeo. Baixamos o primeiro
                    // (o modelo é um vídeo por aula), mas avisamos alto — perder o
                    // segundo em silêncio seria repetir o bug que este bloco conserta.
                    console.warn(`[Sifão] "${aula.filename}" tem ${t.postsFixados.length} posts com vídeo; ` +
                                 `baixando só o primeiro ("${t.postsFixados[0].titulo}")`);
                }
                const urlPost = await resolverVideoDePostFixado(t.postsFixados[0], ctxAula);
                if (urlPost) {
                    aula.url = urlPost;
                    console.log(`[Sifão] "${aula.filename}": vídeo recuperado do post fixado`);
                }
            }
            await new Promise(r => setTimeout(r, RESPIRO_MS));   // respiro anti-flood
        }
        if (aula.desc || pareceResources(aula.resources)) comTexto++;
        textos++;
        if (aoProgredir) aoProgredir('texto', textos, n);
    });

    // Fase 1.5: resolve os ARQUIVOS anexos. Cada um exige um POST ao Skool, então vai
    // com concorrência baixa e respiro, igual à fase de texto. A URL assinada dura ~8h
    // (expire=28800) — folgado para uma fila que leva horas, mas o servidor avisa alto
    // se ela vencer.
    const comAnexo = [];
    for (const aula of aulas) {
        const lista = anexosDeResources(aula.resources);
        if (lista.length) { aula._anexos = lista; comAnexo.push(aula); }
    }
    if (comAnexo.length) {
        const totalAnexos = comAnexo.reduce((soma, a) => soma + a._anexos.length, 0);
        let feitos = 0;
        console.log(`[Sifão] resolvendo ${totalAnexos} anexo(s) em ${comAnexo.length} aula(s)…`);
        await mapConcorrente(comAnexo, 3, async (aula) => {
            const resolvidos = [];
            for (const anexo of aula._anexos) {
                const url = await resolverUrlAnexo(anexo.fileId);
                if (url) resolvidos.push({ nome: anexo.nome, url });
                feitos++;
                if (aoProgredir) aoProgredir('anexos', feitos, totalAnexos);
                await new Promise(r => setTimeout(r, RESPIRO_MS));
            }
            aula.anexos = resolvidos;
        });
        const perdidos = comAnexo.reduce(
            (s, a) => s + (a._anexos.length - (a.anexos || []).length), 0);
        if (perdidos) {
            console.warn(`[Sifão] ⚠️ ${perdidos} anexo(s) não resolveram e não serão baixados.`);
        }
    }

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
                    anexos: aula.anexos || [],
                }),
            });
        } catch (err) {
            console.error(`[Loom] Falha ao enfileirar "${aula.filename}":`, err);
        }
        enviadas++;
        if (aoProgredir) aoProgredir('envio', enviadas, n);
    });

    console.log(`[Loom] textos capturados: ${comTexto}/${n} aulas`);

    // Vídeo do Skool que não resolveu vira aula só-texto no servidor. Isso é uma
    // PERDA de vídeo — e perda silenciosa é o que este projeto mais evita. Avisa.
    const naoResolvidos = aulas.filter(a => a._videoId && !a.url);
    if (naoResolvidos.length) {
        console.warn(`[Sifão] ⚠️ ${naoResolvidos.length} vídeo(s) do Skool não resolveram ` +
                     `(sem playbackToken) e vão sem .mp4:`,
                     naoResolvidos.map(a => a.filename));
    }
    return enviadas;
}

// --- 1.7. CRAWLER DA COMUNIDADE INTEIRA ---
// Na listagem (/{grupo}/classroom) não há curso na URL, então todo o caminho do
// crawler de curso único não se aplica. Aqui listamos os cursos da comunidade e
// buscamos a árvore de CADA um, reaproveitando extrairAulas() sem alteração.

function ehPaginaComunidade() {
    // A listagem é /{grupo}/classroom SEM slug de curso depois.
    const { group, course } = slugsDaUrl();
    return !!group && !course && /\/classroom\/?$/.test(location.pathname);
}

async function buscarPagePropsDeCurso(slug, buildId, group) {
    // MEDIDO: pedir o curso sem `md` NÃO devolve o curso. O Skool responde 200 com um
    // corpo de redirect — {"pageProps":{"__N_REDIRECT":"...?md=<primeira aula>"}} —
    // porque a rota do curso sempre aponta para uma aula. Só relendo com esse `md` é
    // que vem pageProps.course. (Dentro de um curso isso nunca aparecia: a URL já
    // trazia o md.) Seguimos o salto no máximo 2× para não girar em falso.
    if (!slug || !buildId || !group) return null;
    const base = `${location.origin}/_next/data/${buildId}/${group}/classroom/${slug}.json`;
    let q = `group=${encodeURIComponent(group)}&course=${encodeURIComponent(slug)}`;

    for (let salto = 0; salto < 3; salto++) {
        try {
            const r = await fetch(`${base}?${q}`, {
                credentials: 'include', headers: { 'x-nextjs-data': '1' },
            });
            if (!r.ok) { console.warn(`[Sifão] curso ${slug}: HTTP ${r.status}`); return null; }
            const json = await r.json();
            const pp = json.pageProps || (json.props && json.props.pageProps);

            if (pp && pp.__N_REDIRECT) {
                const md = new URL(pp.__N_REDIRECT, location.origin).searchParams.get('md');
                if (!md) { console.warn(`[Sifão] curso ${slug}: redirect sem md`); return null; }
                q = `group=${encodeURIComponent(group)}&course=${encodeURIComponent(slug)}` +
                    `&md=${encodeURIComponent(md)}`;
                continue;
            }
            if (pp && pp.course) return pp;
            console.warn(`[Sifão] curso ${slug}: resposta sem pageProps.course`);
            return null;
        } catch (e) {
            console.warn(`[Sifão] falha ao buscar curso ${slug}:`, e);
            return null;
        }
    }
    console.warn(`[Sifão] curso ${slug}: redirects demais`);
    return null;
}

async function listarCursosDaComunidade() {
    // Busca a listagem FRESCA pelo mesmo motivo do curso único (content.js:204): o
    // __NEXT_DATA__ é o SSR do primeiro load e, após navegação SPA, listaria os cursos
    // da comunidade ANTERIOR.
    const nd = obterNextData();
    const buildId = nd && nd.buildId;
    const { group } = slugsDaUrl();
    if (!buildId || !group) return null;

    let pp = null;
    const url = `${location.origin}/_next/data/${buildId}/${group}/classroom.json` +
                `?group=${encodeURIComponent(group)}`;
    try {
        const r = await fetch(url, { credentials: 'include', headers: { 'x-nextjs-data': '1' } });
        if (r.ok) {
            const json = await r.json();
            pp = json.pageProps || (json.props && json.props.pageProps);
        } else {
            console.warn(`[Sifão] listagem HTTP ${r.status}; tentando cache local.`);
        }
    } catch (e) {
        console.warn('[Sifão] falha ao listar cursos; tentando cache local:', e);
    }

    // Fallback: só aceita o cache local se ele for COMPROVADAMENTE desta comunidade.
    if (!pp || !pp.allCourses) {
        const local = nd.props && nd.props.pageProps;
        const grupoLocal = nd.query && nd.query.group;
        pp = (local && local.allCourses && grupoLocal === group) ? local : null;
    }
    if (!pp || !pp.allCourses) {
        console.warn('[Sifão] não achei a lista de cursos — recarregue a página (F5).');
        return null;
    }

    const cg = pp.currentGroup || {};
    const comunidade = (cg.metadata && cg.metadata.displayName) || cg.name || 'Skool';

    // MEDIDO: cursos sem acesso vêm com hasAccess != 1 e, no JSON deles, NENHUMA aula
    // tem videoLink — o Skool remove os vídeos no servidor. Baixá-los renderia zero
    // arquivos e só gastaria requests, então saem da fila e são relatados no fim.
    const liberados = [], bloqueados = [];
    for (const c of pp.allCourses) {
        const m = c.metadata || {};
        const item = { slug: c.name, titulo: m.title || c.name, aulas: m.numModules || 0 };
        if (m.hasAccess === 1) liberados.push(item); else bloqueados.push(item.titulo);
    }
    return { buildId, group, comunidade, cursos: liberados, bloqueados };
}

async function contextoComunidade() {
    // Para o popup. `numModules` é a contagem real de aulas (medido: soma dos
    // acessíveis = 280, idêntico à varredura das árvores), então o total sai na hora,
    // sem precisar varrer os cursos antes de o usuário confirmar.
    if (!ehPaginaComunidade()) return { ok: false };
    const info = await listarCursosDaComunidade();
    if (!info || !info.cursos.length) return { ok: false };
    return {
        ok: true,
        comunidade: info.comunidade,
        cursos: info.cursos.length,
        bloqueados: info.bloqueados.length,
        aulas: info.cursos.reduce((a, c) => a + c.aulas, 0),
    };
}

async function enfileirarComunidadeDaAba(aoProgredir) {
    if (enfileirandoEmAndamento) return { ok: false, motivo: 'ocupado' };

    // O guarda cobre a varredura TAMBÉM: ela leva alguns segundos e um F5 no meio
    // perderia o trabalho todo (mesma razão do guarda no curso único).
    enfileirandoEmAndamento = true;
    try {
        const info = await listarCursosDaComunidade();
        if (!info || !info.cursos.length) return { ok: false, motivo: 'vazio' };

        // Fase 0: árvore de cada curso. Concorrência 3 + respiro: medido em 7,8s para
        // 11 cursos, sem rate-limit. Subir isso é arriscar 429 e perder curso calado.
        const CONC_CURSO = 3, RESPIRO_MS = 150;
        const todas = [], falharam = [];
        let lidos = 0;

        await mapConcorrente(info.cursos, CONC_CURSO, async (c) => {
            const pp = await buscarPagePropsDeCurso(c.slug, info.buildId, info.group);
            if (!pp) {
                falharam.push(c.titulo);
            } else {
                const aulas = extrairAulas(pp);
                // Cada aula carrega o ctx do SEU curso: a fase de texto do
                // enfileirarCurso busca por aula, e o curso varia entre elas.
                for (const a of aulas) {
                    a._ctx = { buildId: info.buildId, group: info.group, course: c.slug };
                }
                todas.push(...aulas);
            }
            lidos++;
            if (aoProgredir) aoProgredir('cursos', lidos, info.cursos.length);
            await new Promise(r => setTimeout(r, RESPIRO_MS));
        });

        if (!todas.length) return { ok: false, motivo: 'vazio' };

        const comVideo = todas.filter(a => a._temVideo).length;
        console.log(`[Sifão] === comunidade ${info.comunidade}: ${info.cursos.length} cursos, ` +
                    `${todas.length} aulas (${comVideo} com vídeo) ===`);

        // ctx da aba = null: cada aula já traz o seu.
        const enviadas = await enfileirarCurso(todas, null, aoProgredir);
        return {
            ok: true, enviadas,
            cursos: info.cursos.length,
            bloqueados: info.bloqueados,
            falharam,
        };
    } finally {
        enfileirandoEmAndamento = false;
    }
}

// --- 2. COMPONENTE DE DOWNLOAD (pill unificado) ---

// Fábrica do pill: mesmo visual em Loom e Vimeo (o youtube.js tem a sua, idêntica).
// O ícone vem do ui.css (.sf-pill__ico); o texto fica num span para trocar o
// rótulo/estado sem perder o ícone. `fixo` = canto da tela; senão overlay no vídeo.
function criarPill(rotulo, fixo) {
    const btn = document.createElement('button');
    btn.className = 'sf-pill ' + (fixo ? 'sf-pill--fixed' : 'sf-pill--overlay');
    const ico = document.createElement('span');
    ico.className = 'sf-pill__ico';
    const lab = document.createElement('span');
    lab.className = 'sf-pill__label';
    lab.textContent = rotulo;
    btn.append(ico, lab);
    btn._lab = lab;   // atalho p/ atualizar o texto de estado
    return btn;
}

// Caminho REAL da aula ABERTA (Comunidade/Curso/Módulo), o MESMO que o "curso
// inteiro" usa. Sem isto, o botão individual montava a pasta pelo document.title —
// que não traz o módulo — e a aula caía fora da subpasta (ex.: solta em AGENTES
// NEURAIS em vez de AGENTES NEURAIS/Nivelamento), sem deduplicar a cópia já baixada.
// Devolve null quando não dá pra resolver (ex.: loom.com fora do Skool) — aí o
// chamador cai no obterDadosDaPagina() antigo.
async function dadosDaAulaAtual() {
    const md = new URLSearchParams(location.search).get('md');
    if (!md) return null;
    const pp = await obterPagePropsDoCurso();
    if (!pp || !pp.course) return null;
    const porId = coletarUnits(pp.course);
    const unit = porId[md];
    if (!unit) return null;
    const cg = pp.currentGroup || {};
    const comunidade = (cg.metadata && cg.metadata.displayName) || cg.name || 'Skool';
    const meta = metaDe(unit) || {};
    const { curso, modulos } = caminhoDaAula(unit, porId);
    const pasta = [comunidade, curso, ...modulos].filter(Boolean).map(limparTexto).join('/');
    return { folder: pasta, filename: limparTexto(meta.title || 'Aula sem titulo') };
}

function criarBotaoDownload(iframe) {
    // Evita criar dois pills no mesmo vídeo
    if (iframe.parentNode.querySelector('.sf-pill')) return;

    // Garante que o container do vídeo tenha posição relativa (o overlay é absolute).
    if (getComputedStyle(iframe.parentNode).position === 'static') {
        iframe.parentNode.style.position = 'relative';
    }

    const btn = criarPill('Baixar aula', false);

    btn.onclick = async (e) => {
        e.preventDefault();
        e.stopPropagation();
        if (btn.disabled) return;

        const urlEmbed = iframe.src;
        btn.disabled = true;
        btn._lab.textContent = 'Enviando…';

        // Caminho completo da aula (com o módulo). Fallback: título da página.
        const dados = (await dadosDaAulaAtual()) || obterDadosDaPagina();

        fetch(SERVIDOR, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url: urlEmbed, folder: dados.folder, filename: dados.filename }),
        })
        .then(r => r.json())
        .then(() => { btn._lab.textContent = 'Na fila'; })
        .catch(err => {
            console.error('[Loom] servidor offline?', err);
            btn.classList.add('sf-pill--err');
            btn._lab.textContent = 'Servidor offline?';
        })
        .finally(() => {
            setTimeout(() => {
                btn.disabled = false;
                btn.classList.remove('sf-pill--err');
                btn._lab.textContent = 'Baixar aula';
            }, 4000);
        });
    };

    // Insere o pill logo antes do iframe do vídeo
    iframe.parentNode.insertBefore(btn, iframe);
}

// --- 2.5. PONTE COM O POPUP (central de controle) ---
// O botão de "curso inteiro" saiu da página (design Sifão) e virou uma ação do
// popup. Aqui só expomos, por mensagem, o CONTEXTO do curso e o disparo do
// enfileiramento — que roda no content script e PERSISTE mesmo se o popup fechar.

async function enfileirarCursoDaAba(aoProgredir) {
    if (enfileirandoEmAndamento) return { ok: false, motivo: 'ocupado' };
    const aulas = await coletarAulasDoCurso();
    if (!aulas.length) return { ok: false, motivo: 'vazio' };   // vazio ou cache velho (F5)

    enfileirandoEmAndamento = true;   // ativa o guarda beforeunload
    const ctx = obterContexto();
    try {
        const comVideo = aulas.filter(a => a._temVideo).length;
        console.log(`[Loom] === ${aulas.length} aulas ` +
                    `(${comVideo} com vídeo, ${aulas.length - comVideo} sem vídeo) ===`);
        const enviadas = await enfileirarCurso(aulas, ctx, aoProgredir);
        return { ok: true, enviadas };
    } finally {
        enfileirandoEmAndamento = false;   // libera mesmo se algo falhar no meio
    }
}

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
    if (!msg || !msg.tipo) return;
    if (msg.tipo === 'sifao:contextoCurso') {
        contextoCurso().then(sendResponse).catch(() => sendResponse({ ok: false }));
        return true;   // resposta assíncrona
    }
    if (msg.tipo === 'sifao:baixarCurso') {
        // Progresso vai pro popup (se ainda aberto); o enfileiramento roda aqui.
        enfileirarCursoDaAba((fase, i, n) => {
            try { chrome.runtime.sendMessage({ tipo: 'sifao:progresso', fase, i, n }); } catch (e) {}
        }).then(sendResponse).catch(() => sendResponse({ ok: false, motivo: 'erro' }));
        return true;
    }
    if (msg.tipo === 'sifao:contextoComunidade') {
        contextoComunidade().then(sendResponse).catch(() => sendResponse({ ok: false }));
        return true;
    }
    if (msg.tipo === 'sifao:baixarComunidade') {
        enfileirarComunidadeDaAba((fase, i, n) => {
            try { chrome.runtime.sendMessage({ tipo: 'sifao:progresso', fase, i, n }); } catch (e) {}
        }).then(sendResponse).catch(() => sendResponse({ ok: false, motivo: 'erro' }));
        return true;
    }
});

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

function acharVimeoIframe() {
    for (const f of document.querySelectorAll('iframe')) {
        if (f.src && /player\.vimeo\.com/.test(f.src)) return f;
    }
    return null;
}

function ancorarPillNoIframe(btn, iframe) {
    btn.classList.remove('sf-pill--fixed');
    btn.classList.add('sf-pill--overlay');
    if (getComputedStyle(iframe.parentNode).position === 'static') iframe.parentNode.style.position = 'relative';
    iframe.parentNode.insertBefore(btn, iframe);
}

function criarBotaoVimeo() {
    const id = acharVimeoId();
    if (!id) return;
    const iframe = acharVimeoIframe();

    // Se o botão já existe e nasceu no canto (o iframe do Vimeo carregou DEPOIS, pois
    // o id foi detectado pela Performance API antes do iframe entrar no DOM),
    // reancora sobre o vídeo assim que o iframe aparecer.
    const existente = document.getElementById('sf-vimeo');
    if (existente) {
        if (iframe && existente.classList.contains('sf-pill--fixed')) ancorarPillNoIframe(existente, iframe);
        return;
    }

    const btn = criarPill('Baixar vídeo', !iframe);   // overlay se já há iframe; senão canto
    btn.id = 'sf-vimeo';

    btn.onclick = async () => {
        if (btn.disabled) return;
        btn.disabled = true;
        btn._lab.textContent = 'Enviando…';
        const dados = (await dadosDaAulaAtual()) || obterDadosDaPagina();   // caminho completo (com módulo)
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
            btn._lab.textContent = 'Na fila';
        } catch (e) {
            console.error('[Vimeo] servidor offline?', e);
            btn.classList.add('sf-pill--err');
            btn._lab.textContent = 'Servidor offline?';
        }
        setTimeout(() => {
            btn.disabled = false;
            btn.classList.remove('sf-pill--err');
            btn._lab.textContent = 'Baixar vídeo';
        }, 4000);
    };

    if (iframe) ancorarPillNoIframe(btn, iframe);
    else document.body.appendChild(btn);
}

// --- 2.7. LOOM NATIVO (página do próprio loom.com/share|embed) ---
// No Skool o Loom vem num iframe; direto no loom.com o vídeo é o player NATIVO da
// página (sem iframe), então o botão de iframe não aparecia. Aqui detectamos a
// página do Loom e ancoramos o pill sobre o <video>, mandando a URL de embed.

function ehPaginaLoom() {
    return /(^|\.)loom\.com$/.test(location.hostname) &&
           /^\/(share|embed)\/[0-9a-f]{20,}/.test(location.pathname);
}

function idDaPaginaLoom() {
    const m = location.pathname.match(/^\/(?:share|embed)\/([0-9a-f]{20,})/);
    return m ? m[1] : null;
}

function criarBotaoLoomNativo() {
    if (!ehPaginaLoom()) return;
    if (document.getElementById('sf-loom')) return;
    const id = idDaPaginaLoom();
    if (!id) return;
    const video = document.querySelector('video#LoomShakaVideoPlayer, video');
    if (!video) return;

    // O <video> e o wrapper imediato ficam 0×0 (o Loom desenha o quadro num canvas).
    // Sobe até o primeiro ancestral COM tamanho: é o container visível do player.
    let alvo = video.parentElement;
    while (alvo && (alvo.offsetWidth === 0 || alvo.offsetHeight === 0)) alvo = alvo.parentElement;
    if (!alvo) return;   // ainda sem layout; o observador tenta de novo

    if (getComputedStyle(alvo).position === 'static') alvo.style.position = 'relative';

    const btn = criarPill('Baixar vídeo', false);   // overlay sobre o vídeo
    btn.id = 'sf-loom';

    btn.onclick = async () => {
        if (btn.disabled) return;
        btn.disabled = true;
        btn._lab.textContent = 'Enviando…';
        const titulo = limparTexto(
            document.title.replace(/\s*[|-]\s*Loom\s*$/i, '').trim() || 'Video Loom');
        try {
            const resp = await fetch(SERVIDOR, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    url: `https://www.loom.com/embed/${id}`,   // mesmo caminho do embed no Skool
                    folder: 'Loom',
                    filename: titulo,
                }),
            });
            await resp.json();
            btn._lab.textContent = 'Na fila';
        } catch (e) {
            console.error('[Loom] servidor offline?', e);
            btn.classList.add('sf-pill--err');
            btn._lab.textContent = 'Servidor offline?';
        }
        setTimeout(() => {
            btn.disabled = false;
            btn.classList.remove('sf-pill--err');
            btn._lab.textContent = 'Baixar vídeo';
        }, 4000);
    };

    alvo.appendChild(btn);
}

// --- 2.8. BOTÃO DE VÍDEO HOSPEDADO NO SKOOL ---
// Aula com `videoId` não tem iframe (o player é Mux via MediaSource), então nenhum
// dos botões anteriores nascia nela — dava para baixar só pelo curso inteiro.
// Aqui detectamos a aula aberta e ancoramos o pill sobre o player.

let _skoolVideoTentado = '';   // md já processado, para o observador não refazer fetch

function acharPlayerSkool() {
    // MEDIDO: antes do play não existe <video> NEM <img> — a thumbnail do Mux entra
    // como `background-image` de uma div. Procurar por `img[src*=...]` (a primeira
    // tentativa) nunca casava, e o pill caía no fallback do canto da tela.
    for (const el of document.querySelectorAll('div,span,section')) {
        if (el.offsetWidth < 240 || el.offsetHeight < 120) continue;
        const bg = getComputedStyle(el).backgroundImage;
        if (bg && bg !== 'none' && bg.includes('image.video.skool.com')) return el;
    }

    // Depois do play o <video> existe: sobe até o primeiro ancestral com tamanho.
    const video = document.querySelector('video');
    if (video) {
        let p = video.parentElement;
        while (p && (p.offsetWidth === 0 || p.offsetHeight === 0)) p = p.parentElement;
        if (p) return p;
    }

    // Último recurso: a caixa 16:9 do player (medida em 657x369 = 1.78).
    let melhor = null;
    for (const el of document.querySelectorAll('div')) {
        const w = el.offsetWidth, h = el.offsetHeight;
        if (w < 300 || h < 160) continue;
        const razao = w / h;
        if (razao > 1.72 && razao < 1.83) {
            if (!melhor || w < melhor.offsetWidth) melhor = el;   // o mais interno
        }
    }
    return melhor;
}

async function criarBotaoVideoSkool() {
    const md = new URLSearchParams(location.search).get('md');
    if (!md || !/\/classroom\//.test(location.pathname)) return;
    if (_skoolVideoTentado === md) return;        // já resolvido/descartado nesta aula
    if (document.getElementById('sf-skool')) return;

    _skoolVideoTentado = md;                      // marca ANTES do await: o observador
                                                  // dispara muitas vezes por segundo e
                                                  // sem isto viraria enxurrada de fetch.
    const pp = await obterPagePropsDoCurso();
    if (!pp || !pp.course) return;
    const unit = coletarUnits(pp.course)[md];
    if (!unit) return;
    const meta = metaDe(unit) || {};
    if (meta.videoLink) return;                   // Loom/YouTube já têm o seu botão

    // A aula pode não ter vídeo PRÓPRIO e guardar o vídeo num POST FIXADO. Antes a
    // condição era `!meta.videoId` e essas aulas ficavam sem pill nenhum — o
    // enfileiramento em massa as recuperava, mas quem abrisse a aula para baixar só
    // ela não tinha botão. São 52 aulas na ai-makers, quase todas de Office Hours.
    //
    // `obterPagePropsDoCurso` já manda o `md` atual no request, e `pinnedPosts`
    // pertence à aula ABERTA — então isto sai de graça, sem requisição a mais.
    const pins = meta.videoId ? [] : postsFixadosComVideo(pp);
    if (!meta.videoId && !pins.length) return;    // sem vídeo em lugar nenhum

    if (document.getElementById('sf-skool')) return;
    const alvo = acharPlayerSkool();
    const btn = criarPill('Baixar vídeo', !alvo);   // sem player achado, vai pro canto
    btn.id = 'sf-skool';

    btn.onclick = async () => {
        if (btn.disabled) return;
        btn.disabled = true;
        btn._lab.textContent = 'Resolvendo…';

        // O par playbackId+token só existe no JSON da aula aberta, e expira (~24h),
        // então resolvemos no clique — nunca guardamos um token velho.
        const ctx = obterContexto();
        const t = await buscarTextoDaAula(md, ctx, String(meta.videoId || ''));
        const dados = (await dadosDaAulaAtual()) || obterDadosDaPagina();

        // Sem vídeo próprio, o vídeo vem do post fixado. Resolvemos aqui, no clique,
        // pelo mesmo motivo do vídeo do Skool: o token expira (~24h) e guardá-lo
        // adiantado só produziria um 403 na hora do download.
        if (!t.urlVideo && pins.length) {
            t.urlVideo = await resolverVideoDePostFixado(pins[0], ctx);
        }

        if (!t.urlVideo) {
            console.warn('[Sifão] não consegui resolver o vídeo do Skool para', md);
            btn.classList.add('sf-pill--err');
            btn._lab.textContent = 'Falhou — recarregue (F5)';
            setTimeout(() => {
                btn.disabled = false;
                btn.classList.remove('sf-pill--err');
                btn._lab.textContent = 'Baixar vídeo';
            }, 5000);
            return;
        }

        btn._lab.textContent = 'Enviando…';
        try {
            const r = await fetch(SERVIDOR, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    url: t.urlVideo,
                    folder: dados.folder,
                    filename: dados.filename,
                    desc: t.desc || '',
                    resources: t.resources || '',
                }),
            });
            await r.json();
            btn._lab.textContent = 'Na fila';
        } catch (e) {
            console.error('[Sifão] servidor offline?', e);
            btn.classList.add('sf-pill--err');
            btn._lab.textContent = 'Servidor offline?';
        }
        setTimeout(() => {
            btn.disabled = false;
            btn.classList.remove('sf-pill--err');
            btn._lab.textContent = 'Baixar vídeo';
        }, 4000);
    };

    if (alvo) {
        // Overlay DENTRO do container do player (mesmo padrão do Loom nativo).
        // ancorarPillNoIframe não serve aqui: ela insere como IRMÃO do elemento,
        // o que colocaria o pill ao lado do player em vez de sobre ele.
        if (getComputedStyle(alvo).position === 'static') alvo.style.position = 'relative';
        alvo.appendChild(btn);
    } else {
        document.body.appendChild(btn);
    }
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
        // Botão de vídeo Vimeo (posts de comunidade e afins).
        criarBotaoVimeo();
        // Botão do Loom nativo (página do próprio loom.com/share|embed).
        criarBotaoLoomNativo();
        // Botão de vídeo hospedado no Skool (aula com videoId, sem iframe).
        // É assíncrono e se auto-limita por `md`, então não floda o observador.
        criarBotaoVideoSkool();
    });
    
    // Começa a vigiar o corpo da página
    observadorDeMudancas.observe(document.body, { childList: true, subtree: true });
}

// Inicia o processo
iniciarObservador();
criarBotaoVimeo();
criarBotaoLoomNativo();
criarBotaoVideoSkool();

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