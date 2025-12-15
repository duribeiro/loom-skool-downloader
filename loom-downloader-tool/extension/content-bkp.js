// Verifica se estamos dentro de um Iframe ou na página do vídeo
function inicializar() {
    console.log("Extensão Loom: Script carregado em", window.location.href);

    // Verifica se a URL atual é de um embed ou share do Loom
    if (window.location.href.includes('loom.com/embed') || window.location.href.includes('loom.com/share')) {
        injetarBotao();
    }
}

function injetarBotao() {
    // Evita duplicatas
    if (document.querySelector('.meu-botao-download')) return;

    const btn = document.createElement('button');
    btn.innerText = '⬇ Baixar';
    btn.className = 'meu-botao-download';
    
    // URL atual (como o script roda DENTRO do iframe, window.location.href é a URL correta do vídeo)
    const urlParaBaixar = window.location.href;

    btn.onclick = function(e) {
        // Impede que o clique pause/despause o vídeo
        e.stopPropagation(); 
        e.preventDefault();

        btn.innerText = '⏳';
        btn.style.backgroundColor = '#e6bf00'; // Amarelo de "aguarde"

        fetch('http://localhost:5000/baixar', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({url: urlParaBaixar})
        })
        .then(response => response.json())
        .then(data => {
            console.log("Resposta do servidor:", data);
            btn.innerText = '✅';
            btn.style.backgroundColor = '#00d084';
            setTimeout(() => btn.innerText = '⬇ Baixar', 4000);
        })
        .catch(err => {
            console.error("Erro ao conectar com servidor Python:", err);
            btn.innerText = '❌ Erro';
            btn.style.backgroundColor = '#ff4444';
        });
    };

    // Adiciona o botão diretamente ao corpo do documento (dentro do iframe)
    document.body.appendChild(btn);
    console.log("Extensão Loom: Botão injetado com sucesso!");
}

// Tenta injetar assim que possível
inicializar();

// Garante que injeta mesmo se o conteúdo carregar dinamicamente
setInterval(inicializar, 2000);