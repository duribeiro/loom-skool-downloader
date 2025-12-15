// --- CONFIGURAÇÃO ---
let observer = null;
let ultimoUrl = "";

function limparTexto(texto) {
    if (!texto) return "";
    // Remove caracteres proibidos para pastas, mas MANTÉM o Unicode (como o símbolo da Backroom)
    return texto.replace(/[<>:"/\\|?*]/g, '').trim();
}

function obterDadosDaPagina() {
    // 1. Pega o Título Bruto
    let titulo = document.title;
    
    // Remove o sufixo " - Skool" se existir
    titulo = titulo.replace(/ - Skool$/i, '');

    let comunidade = "Geral";
    let curso = "Curso Desconhecido";
    let aula = "Aula Sem Titulo";

    // 2. ESTRATÉGIA DO PONTO MÉDIO (·)
    // O log mostrou: "RAYA METHOD... · 〄 BACKROOM"
    // Vamos tentar separar por esse caractere especial
    if (titulo.includes('·')) {
        const partesPonto = titulo.split('·');
        
        // A Comunidade é a parte da direita (após o ponto)
        comunidade = limparTexto(partesPonto[partesPonto.length - 1]);
        
        // O resto (Esquerda) contém "Aula - Curso"
        // Removemos a comunidade da string para processar o resto
        // Juntamos o resto caso haja mais de um ponto (raro)
        let resto = partesPonto.slice(0, -1).join('·').trim();

        // Agora separamos Aula e Curso pelo traço " - "
        // O padrão é "Aula - Curso"
        const partesTraco = resto.split(' - ');
        
        if (partesTraco.length >= 2) {
            // O Curso é a última parte
            curso = limparTexto(partesTraco.pop());
            
            // A Aula é tudo o que sobrou antes (junta de volta caso a aula tenha hífen)
            aula = limparTexto(partesTraco.join(' - '));
        } else {
            // Se não tiver traço, assumimos que é tudo Aula ou tudo Curso
            // Geralmente é o Curso
            curso = limparTexto(resto);
            aula = "Aula Geral"; 
            
            // Tenta salvar pegando H1 se a aula ficou genérica
            const h1 = document.querySelector('h1');
            if (h1) aula = limparTexto(h1.innerText);
        }

    } else {
        // FALLBACK: Se não tiver a bolinha (·), usa a lógica antiga dos traços
        const partes = titulo.split(' - ');
        if (partes.length >= 2) {
            curso = limparTexto(partes.pop()); // O último é o curso
            aula = limparTexto(partes.join(' - ')); // O resto é aula
            
            // Tenta pegar comunidade da URL se não achou no título
            try {
                const path = window.location.pathname.split('/');
                if (path[1]) comunidade = path[1].toUpperCase();
            } catch(e) {}
        }
    }

    // 3. Montagem da Pasta Final
    // Formato: COMUNIDADE / CURSO
    const pastaFinal = `${comunidade}/${curso}`;

    // console.log(`[Extensão] Com: "${comunidade}" | Curso: "${curso}" | Aula: "${aula}"`);

    return {
        folder: pastaFinal,
        filename: aula
    };
}

function injetarBotao(iframe) {
    if (iframe.parentNode.querySelector('.meu-botao-download')) return;

    if (getComputedStyle(iframe.parentNode).position === 'static') {
        iframe.parentNode.style.position = 'relative';
    }

    const btn = document.createElement('button');
    btn.innerText = '⬇ Baixar Aula';
    btn.className = 'meu-botao-download'; 
    
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

        btn.innerText = '📡 ...';
        btn.style.backgroundColor = '#95a5a6'; 

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
            btn.innerText = '⏳ Na Fila';
            btn.style.backgroundColor = '#3498db';
            setTimeout(() => {
                btn.innerText = '⬇ Baixar Aula';
                btn.style.backgroundColor = '#00d084';
            }, 4000);
        })
        .catch(err => {
            console.error(err);
            btn.innerText = '❌ Erro';
            btn.style.backgroundColor = '#e74c3c';
        });
    };

    iframe.parentNode.insertBefore(btn, iframe);
}

function iniciarObservador() {
    if (observer) observer.disconnect();
    observer = new MutationObserver((mutations) => {
        const iframes = document.querySelectorAll('iframe');
        iframes.forEach(iframe => {
            if (iframe.src.includes('loom.com/embed') || iframe.src.includes('loom.com/share')) {
                injetarBotao(iframe);
            }
        });
    });
    observer.observe(document.body, { childList: true, subtree: true });
}

iniciarObservador();

let lastUrl = location.href; 
new MutationObserver(() => {
  if (location.href !== lastUrl) {
    lastUrl = location.href;
    setTimeout(iniciarObservador, 1000); 
  }
}).observe(document, {subtree: true, childList: true});