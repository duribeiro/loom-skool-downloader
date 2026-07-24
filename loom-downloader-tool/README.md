<div align="center">

# 🚀 Loom Downloader - Skool Edition

**Uma ferramenta poderosa para baixar, organizar e converter aulas do Loom diretamente da plataforma Skool.**

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python)
![Flask](https://img.shields.io/badge/Flask-Backend-green?style=for-the-badge&logo=flask)
![FFmpeg](https://img.shields.io/badge/FFmpeg-Converter-orange?style=for-the-badge&logo=ffmpeg)
![Chrome Extension](https://img.shields.io/badge/Chrome-Extension-yellow?style=for-the-badge&logo=google-chrome)

[Funcionalidades](#-funcionalidades) • [Pré-requisitos](#-pré-requisitos) • [Instalação](#-instalação) • [Como Usar](#-como-usar)

</div>

---

## 📖 Sobre o Projeto

Este projeto nasceu da necessidade de baixar aulas hospedadas no Loom dentro de comunidades do Skool para visualização offline. Diferente de baixadores comuns, este sistema é **híbrido**:

1.  Uma **Extensão do Chrome** injeta um botão de download diretamente no player de vídeo.
2.  Um **Servidor Python** local recebe o pedido, baixa os fragmentos `.ts` em alta velocidade, converte para `.mp4` e organiza tudo automaticamente.

> **Nota:** Este projeto é para fins educacionais e de uso pessoal (backup de cursos adquiridos).

---

## ✨ Funcionalidades

* **⚡ Download Multi-thread:** Baixa múltiplos fragmentos do vídeo simultaneamente para máxima velocidade.
* **🧠 Inteligente:** Detecta automaticamente o nome da Comunidade, do Curso e da Aula para criar as pastas.
* **🛡️ Proteção contra Duplicatas:** Verifica se o arquivo já existe antes de iniciar, poupando tempo e banda.
* **🎬 Conversão Automática:** Une e converte os segmentos `.ts` para um arquivo `.mp4` limpo usando FFmpeg.
* **🖥️ Dashboard Visual:** Interface rica no terminal para acompanhar o progresso em tempo real (via biblioteca `rich`).
* **📂 Organização Automática:**
    ```text
    output/
    └── Nome da Comunidade/
        └── Nome do Curso/
            └── Aula 01 - Título.mp4
    ```

---

## 🛠 Pré-requisitos

Antes de começar, precisas ter instalado na tua máquina:

1.  **Python 3.10+**: [Baixar aqui](https://www.python.org/)
2.  **FFmpeg**: Essencial para a conversão de vídeo.
    * *Windows:* [Tutorial de Instalação](https://phoenixnap.com/kb/ffmpeg-windows) (Não esqueça de adicionar ao PATH).
    * *Mac:* `brew install ffmpeg`
    * *Linux:* `sudo apt install ffmpeg`
3.  **Google Chrome** (ou navegador baseado em Chromium, como Edge/Brave).

---

## 🚀 Instalação

### Passo 1: Servidor (Backend) — um comando

**Windows (PowerShell):**
```powershell
git clone https://github.com/duribeiro/loom-downloader-tool.git
cd loom-downloader-tool
.\setup.ps1
```

**Linux / macOS:**
```bash
git clone https://github.com/duribeiro/loom-downloader-tool.git
cd loom-downloader-tool
./setup.sh
```

O script verifica Python e FFmpeg, cria o ambiente virtual e instala tudo.
Ele é **idempotente**: pode rodar quantas vezes quiser, e nunca apaga um `venv`
que já exista.

Se algum pré-requisito estiver faltando, ele para com a instrução exata do que
instalar — em vez de falhar mais adiante com um erro obscuro.

> **Windows:** o `.\` na frente é obrigatório; o PowerShell não executa nada do
> diretório atual sem ele. Se der erro de política de execução (acontece quando o
> arquivo veio de um `.zip` baixado, que o Windows marca), rode
> `Unblock-File .\setup.ps1` antes.

### Passo 2: Extensão (Frontend) — manual

Este passo o Chrome não permite automatizar:

1.  Abra `chrome://extensions`.
2.  Ative o **"Modo do desenvolvedor"** (canto superior direito).
3.  Clique em **"Carregar sem compactação"** (Load unpacked).
4.  Selecione a pasta `extension` dentro deste projeto.

> O caminho completo da pasta é impresso pelo `setup.ps1` no final — é só copiar.

---

## 🕹 Como Usar

1.  **Inicie o Servidor:**
    No terminal, **de dentro de `loom-downloader-tool/`**, rode:

    ```powershell
    # Windows
    .\venv\Scripts\python.exe server\app.py
    ```
    ```bash
    # Linux / macOS
    ./venv/bin/python server/app.py
    ```
    *Você verá o Dashboard iniciar e o servidor subir na porta 5000.*

    > **A pasta importa.** `PASTA_TEMP_RAIZ` é relativo ao diretório atual — rodar
    > de outro lugar espalha os arquivos temporários no lugar errado.

2.  **Vá para o Skool:**
    Acesse a aula que deseja baixar no seu navegador.

3.  **Baixe:**
    Um botão verde **"⬇ Baixar Aula"** aparecerá no canto superior direito do vídeo.
    * Clique nele. O botão mudará para "⏳ Na Fila".
    * Olhe para o seu terminal para ver o download acontecer!

---

## 📸 Screenshots

*![Dashboard no terminal](assets/image.png)*

---

## 🤝 Contribuição

Contribuições são bem-vindas! Se tens uma ideia para melhorar o código:

1.  Faça um Fork do projeto.
2.  Crie uma Branch para sua Feature (`git checkout -b feature/Incrível`).
3.  Faça o Commit (`git commit -m 'Add some Incrível'`).
4.  Faça o Push (`git push origin feature/Incrível`).
5.  Abra um Pull Request.

---

<div align="center">

Feito com 💜 e Python por [Eduardo Ribeiro](https://github.com/duribeiro)

</div>