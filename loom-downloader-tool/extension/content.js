// content.js - Versão Inteligente para Skool

function limparTexto(texto) {
    return texto.replace(/[<>:"/\\|?*]/g, '').trim();
}

function obterDadosDaPagina() {
    let curso = "Curso Desconhecido";
    let modulo = "Modulo Geral";
    let aula = "Aula";

    // TENTATIVA 1: Lógica específica para SKOOL (Baseada no seu print)
    if (window.location.host.includes('skool.com')) {
        
        // 1. Tentar pegar o Título da Aula (Geralmente um H1 grande)
        const h1 = document.querySelector('h1');
        if (h1) aula = limparTexto(h1.innerText);

        // 2. Tentar pegar o Módulo/Curso do Título da Aba do Navegador
        // O Skool costuma usar: "Nome da Aula - Nome da Comunidade - Skool"
        const tituloPagina = document.title.split('-');
        if (tituloPagina.length >= 2) {
            // Assume que o segundo item é o Curso/Comunidade
            curso = limparTexto(tituloPagina[1]); 
        }

        // 3. Tentar achar o Módulo na barra lateral (Difícil sem classes fixas)
        // Vamos usar um fallback: Se não achar, cria uma pasta "Aulas Baixadas"
        // Dica: Você pode editar isso manualmente no Python se quiser precisão absoluta
    } 

    return {
        folder: `${curso}/${modulo}`, // Cria a estrutura "Curso/Modulo"
        filename: aula
    };
}

function injetarBotaoSkool() {
    // Procura por IFRAMES do Loom na página
    const iframes = document.querySelectorAll('iframe');
    
    iframes.forEach(iframe => {
        // Verifica se é um vídeo do Loom
        if (iframe.src.includes('loom.com/embed') && !iframe.parentNode.querySelector('.btn-baixar-skool')) {
            
            const btn = document.createElement('button');
            btn.innerText = '⬇ Baixar (Organizado)';
            btn.className = 'btn-baixar-skool meu-botao-download'; // Reusa seu CSS
            
            // Ajuste de posição para não ficar em cima do player
            iframe.parentNode.style.position = 'relative';
            
            btn.onclick = (e) => {
                e.preventDefault();
                e.stopPropagation();
                
                const dadosPagina = obterDadosDaPagina();
                const urlVideo = iframe.src;

                btn.innerText = '⏳ Processando...';
                btn.style.backgroundColor = '#e6bf00';

                // Envia para o servidor com os nomes das pastas!
                fetch('http://localhost:5000/baixar', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        url: urlVideo,
                        folder: dadosPagina.folder,     // Ex: RAYA METHOD/Modulo Geral
                        filename: dadosPagina.filename  // Ex: Criando personagem consistente
                    })
                })
                .then(res => res.json())
                .then(data => {
                    btn.innerText = '✅ Baixando!';
                    console.log("Sucesso:", data);
                    setTimeout(() => btn.innerText = '⬇ Baixar (Organizado)', 4000);
                })
                .catch(err => {
                    console.error(err);
                    btn.innerText = '❌ Erro Servidor';
                });
            };

            // Insere o botão LOGO ANTES do iframe na estrutura HTML da Skool
            iframe.parentNode.insertBefore(btn, iframe);
        }
    });
}

// Monitora a página para quando você troca de aula (Single Page Application)
setInterval(injetarBotaoSkool, 2000);