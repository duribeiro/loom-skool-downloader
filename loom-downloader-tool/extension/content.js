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
    });
    
    // Começa a vigiar o corpo da página
    observadorDeMudancas.observe(document.body, { childList: true, subtree: true });
}

// Inicia o processo
iniciarObservador();

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