// --- CONFIGURAÇÃO ---
let observer = null;
let ultimoUrl = "";

function limparTexto(texto) {
    if (!texto) return "Desconhecido";
    // Remove caracteres inválidos para pastas/arquivos do Windows
    return texto.replace(/[<>:"/\\|?*]/g, '').trim();
}

function obterDadosDaPagina() {
    let curso = "Download Geral"; 
    let aula = "Aula Sem Titulo";

    // --- 1. DESCOBRIR O NOME DO CURSO (PASTA) ---
    // Baseado no teu print: styled__CourseMenuTopTitleText...
    // O seletor [class*="..."] busca qualquer elemento que CONTENHA esse texto na classe
    const elementoCurso = document.querySelector('[class*="CourseMenuTopTitleText"]');
    
    if (elementoCurso) {
        curso = limparTexto(elementoCurso.innerText);
    } else {
        // Fallback: Tenta pegar o nome da comunidade no topo (header padrão da Skool)
        const headerLink = document.querySelector('a[href^="/communities/"]');
        if (headerLink) curso = limparTexto(headerLink.innerText);
    }

    // --- 2. DESCOBRIR O NOME DA AULA (ARQUIVO) ---
    // Estratégia A: O H1 da página (Geralmente é o título completo e correto acima do vídeo)
    const h1 = document.querySelector('h1');
    
    if (h1) {
        aula = limparTexto(h1.innerText);
    } else {
        // Estratégia B: Baseado no teu print (styled__ModuleTitle...)
        // Isso pega o item da lista lateral. Pode ser útil se não houver H1.
        const elementoAulaSidebar = document.querySelector('[class*="ModuleTitle"]');
        if (elementoAulaSidebar) {
            aula = limparTexto(elementoAulaSidebar.innerText);
        } else {
            // Estratégia C: Título da aba do navegador
            const partesTitulo = document.title.split(' - ');
            if (partesTitulo.length > 0) aula = limparTexto(partesTitulo[0]);
        }
    }

    console.log(`[Extensão] Pasta: "${curso}" | Arquivo: "${aula}"`);

    return {
        folder: curso,
        filename: aula
    };
}

function injetarBotao(iframe) {
    if (iframe.parentNode.querySelector('.meu-botao-download')) return;

    // Garante que o container do iframe tenha posição relativa para o botão fixar nele
    if (getComputedStyle(iframe.parentNode).position === 'static') {
        iframe.parentNode.style.position = 'relative';
    }

    const btn = document.createElement('button');
    btn.innerText = '⬇ Baixar Aula';
    btn.className = 'meu-botao-download'; 
    
    // Força o estilo via JS para garantir que nada na Skool sobrescreva
    Object.assign(btn.style, {
        position: 'absolute',
        zIndex: '9999',
        top: '10px',
        right: '10px',
        cursor: 'pointer',
        backgroundColor: '#00d084',
        color: 'white',
        border: 'none',
        padding: '8px 12px',
        fontWeight: 'bold',
        borderRadius: '4px',
        boxShadow: '0 2px 5px rgba(0,0,0,0.3)'
    });

    btn.onclick = (e) => {
        e.preventDefault();
        e.stopPropagation();

        const dados = obterDadosDaPagina();
        const urlEmbed = iframe.src;

        // Feedback Imediato de Clique
        btn.innerText = '📡 Conectando...';
        btn.style.backgroundColor = '#95a5a6'; // Cinza

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
            // Feedback de Sucesso (Entrou na Fila)
            btn.innerText = '⏳ Na Fila';
            btn.style.backgroundColor = '#3498db'; // Azul
            
            // Volta ao normal depois de 5 segundos para permitir baixar de novo se precisar
            setTimeout(() => {
                btn.innerText = '⬇ Baixar Aula';
                btn.style.backgroundColor = '#00d084'; // Verde Original
            }, 5000);
        })
        .catch(err => {
            btn.innerText = '❌ Erro';
            btn.style.backgroundColor = '#e74c3c';
        });
    };

    // Insere o botão visualmente
    iframe.parentNode.insertBefore(btn, iframe);
}

// O VIGILANTE (MutationObserver)
function iniciarObservador() {
    if (observer) observer.disconnect();

    observer = new MutationObserver((mutations) => {
        const iframes = document.querySelectorAll('iframe');
        iframes.forEach(iframe => {
            // Verifica se é Loom
            if (iframe.src.includes('loom.com/embed') || iframe.src.includes('loom.com/share')) {
                injetarBotao(iframe);
            }
        });
    });

    observer.observe(document.body, { childList: true, subtree: true });
}

// Inicia
iniciarObservador();

// Monitora mudança de URL (SPA)
let lastUrl = location.href; 
new MutationObserver(() => {
  if (location.href !== lastUrl) {
    lastUrl = location.href;
    // Pequeno delay para dar tempo do título da página atualizar
    setTimeout(iniciarObservador, 1500); 
  }
}).observe(document, {subtree: true, childList: true});