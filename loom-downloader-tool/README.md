<div align="center">

<img src="extension/icons/icon128.png" width="96" alt="Sifão" />

# Sifão — Baixador de aulas

**Baixe, organize e converta aulas do Skool/Loom, vídeos do YouTube e Vimeo — direto do player, com um clique.**

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python)
![Flask](https://img.shields.io/badge/Flask-Backend-green?style=for-the-badge&logo=flask)
![FFmpeg](https://img.shields.io/badge/FFmpeg-Converter-orange?style=for-the-badge&logo=ffmpeg)
![yt-dlp](https://img.shields.io/badge/yt--dlp-YouTube%20%2F%20Vimeo-red?style=for-the-badge)
![Chrome](https://img.shields.io/badge/Chrome-Extension-yellow?style=for-the-badge&logo=googlechrome)

[Funcionalidades](#-funcionalidades) • [Instalação](#-instalação) • [Como usar](#-como-usar) • [Organização](#-organização-dos-arquivos) • [Design](#-identidade-visual)

<img src="docs/screenshots/hero.png" width="760" alt="Sifão — uma linguagem visual só" />

</div>

---

## 📖 Sobre o projeto

Baixador de aulas hospedadas em comunidades do **Skool** (via **Loom** e **Vimeo**) e de vídeos do **YouTube**, para assistir offline. A arquitetura é **híbrida**:

1. Uma **extensão do Chrome** injeta um botão de download no player — o mesmo componente em qualquer vídeo.
2. Um **servidor Python local** recebe o pedido, baixa (HLS em paralelo ou via `yt-dlp`), converte para `.mp4` com FFmpeg e organiza tudo em pastas.

> **Uso pessoal/educacional:** backup de cursos que você adquiriu. Respeite os termos das plataformas e os direitos dos autores.

---

## ✨ Funcionalidades

- **🎯 Um pill para tudo** — o mesmo botão sobre o vídeo no **Loom**, **YouTube** e **Vimeo** (estilo Internet Download Manager). Só o rótulo muda.
- **📚 Curso inteiro pelo popup** — na classroom do Skool, o popup detecta o curso da aba e enfileira **todas as aulas** de uma vez (vídeo + texto), respeitando a estrutura de módulos.
- **🎥 4 fontes** — Skool/Loom (HLS), YouTube e Vimeo (`yt-dlp`), incluindo **Vimeo privado** do Skool (via `Referer`) e **Loom direto** (`loom.com/share`).
- **📁 YouTube por canal** — vídeos do YouTube caem em `output/YouTube/<Canal>/`, a mesma lógica de pastas do Skool.
- **🧠 Caminho correto + dedup** — cada aula grava no caminho completo (Comunidade/Curso/Módulo) e o que já existe é **pulado**.
- **⚡ Download paralelo** — fragmentos HLS baixados com múltiplas threads; enfileiramento de curso resiliente a recarregar a página.
- **🖥️ Dashboard no terminal** — progresso em tempo real (biblioteca `rich`).
- **🟢 Status do servidor** — o popup mostra se o servidor local está online.

---

## 🖼️ Visão geral

**O mesmo pill sobre qualquer player:**

<img src="docs/screenshots/pills.png" width="760" alt="Pill unificado sobre Loom, YouTube e Vimeo" />

**Dashboard no terminal (progresso em tempo real):**

<img src="assets/image.png" width="760" alt="Dashboard no terminal" />

> Veja o mockup interativo (claro/escuro) do sistema visual em [`docs/design-system/mockup.html`](docs/design-system/mockup.html).

---

## 🛠 Pré-requisitos

1. **Python 3.10+** — [python.org](https://www.python.org/)
2. **FFmpeg** no PATH — obrigatório para converter/fundir vídeo.
   - *Windows:* [tutorial](https://phoenixnap.com/kb/ffmpeg-windows) (adicione ao PATH)
   - *macOS:* `brew install ffmpeg`
   - *Linux:* `sudo apt install ffmpeg`
3. **Google Chrome** (ou Edge/Brave — Chromium).

> "O servidor não sobe" é quase sempre FFmpeg fora do PATH: `verificar_ffmpeg()` faz `sys.exit(1)` se não encontrar.

---

## 🚀 Instalação

### 1. Servidor (backend)

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

O script verifica Python e FFmpeg, cria o `venv` e instala tudo. É **idempotente** (pode rodar várias vezes) e nunca apaga um `venv` existente. Se faltar um pré-requisito, ele para com a instrução exata do que instalar.

> **Windows:** o `.\` é obrigatório. Se der erro de política de execução (arquivo veio de `.zip`), rode `Unblock-File .\setup.ps1` antes.

### 2. Extensão (frontend) — manual

O Chrome não permite automatizar este passo:

1. Abra `chrome://extensions`
2. Ative o **"Modo do desenvolvedor"** (canto superior direito)
3. Clique em **"Carregar sem compactação"**
4. Selecione a pasta **`extension`** deste projeto

> O caminho completo é impresso pelo `setup.ps1` no final — é só copiar.

---

## 🕹 Como usar

**1. Inicie o servidor** — no terminal, **de dentro de `loom-downloader-tool/`**:

```powershell
# Windows
.\venv\Scripts\python.exe server\app.py
```
```bash
# Linux / macOS
./venv/bin/python server/app.py
```

Sobe em `localhost:5000` com o dashboard no terminal.

> **A pasta importa:** `PASTA_TEMP_RAIZ` é relativo ao diretório atual — rode de dentro de `loom-downloader-tool/`.

**2. Baixe** — de acordo com o que você quer:

| Quero baixar… | O que fazer |
|---|---|
| **Uma aula do Skool/Loom** | Abra a aula → clique no pill **⬇ Baixar aula** sobre o vídeo |
| **Um curso inteiro do Skool** | Na classroom → clique no ícone da extensão → **📚 Baixar curso inteiro** |
| **Um vídeo do YouTube** | Abra o vídeo → pill **⬇ Baixar vídeo** sobre o player |
| **Um YouTube por link** | Clique no ícone da extensão → cole o link → **Baixar** |
| **Um Vimeo (post do Skool)** | Abra o post → pill **⬇ Baixar vídeo** sobre o vídeo |
| **Um Loom direto** | Abra `loom.com/share/...` → pill sobre o player |

Acompanhe o progresso no **dashboard do terminal**.

---

## 📂 Organização dos arquivos

Mesma lógica em todas as fontes: `output/<Origem>/<Agrupador>/<Aula>.mp4`.

```text
output/
├── BACKROOM.EXE/                     ← comunidade Skool
│   └── AGENTES NEURAIS/              ← curso
│       └── Nivelamento/             ← módulo
│           └── Vamos começar.mp4    ← aula
└── YouTube/
    └── Hashtag Treinamentos/        ← nome do canal (via yt-dlp)
        └── Aula 1 - Criando agentes de IA.mp4
```

---

## 🎨 Identidade visual

A extensão segue um design system próprio — **Sifão** — documentado em [`docs/design-system/`](docs/design-system/README.md):

<img src="docs/screenshots/palette.png" width="680" alt="Paleta Sifão" />

- **Um acento** (azul-elétrico `#3D7BFF`) e um mark em gradiente, em toda a extensão.
- **Cores semânticas** (online/erro) separadas da marca.
- **Um só componente** de download (pill) sobre qualquer player.
- Ícone próprio gerado por [`tools/gerar_icones.py`](tools/gerar_icones.py) a partir do design system.

---

## 🧪 Testes

```powershell
.\venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\venv\Scripts\python.exe -m pytest          # rápido, sem internet
.\venv\Scripts\python.exe -m pytest -m rede  # bate no Loom de verdade
```

São **dois tipos de teste** com propósitos diferentes:

| | O que protege | Quando roda |
|---|---|---|
| **Suíte padrão** | Contra **nós** quebrarmos o código | Sempre. Fixtures congeladas, sem internet |
| **`-m rede`** | Contra o **Loom** mudar a página | Sob demanda. Precisa de internet |

Uma fixture congelada fica verde para sempre mesmo se o Loom mudar o formato da página — projeto quebrado, suíte passando. **Se um teste `-m rede` falhar, não é bug — é manutenção:** o Loom mudou algo. Baixe o HTML novo e atualize a extração junto com a fixture em `tests/fixtures/loom_embed.html`.

---

## 🧩 Como funciona (resumo)

1. **Extensão** → `POST localhost:5000/baixar` com `{url, folder, filename[, desc, resources, referer]}`.
2. **Servidor** responde `200` na hora e joga o download num `ThreadPoolExecutor` (até 3 simultâneos).
3. **Roteamento por URL:** YouTube/Vimeo → `yt-dlp`; Loom/embed → extrai o `.m3u8` e baixa o HLS.
4. **Loom (HLS):** escolhe a maior qualidade, baixa vídeo + áudio em paralelo, funde com FFmpeg (`-c copy`).
5. **Organização:** grava em `output/…` seguindo a estrutura de comunidade/curso/módulo (ou `YouTube/<Canal>`).

---

## ⚠️ Limitações conhecidas

- **Falhas silenciosas de segmento:** um fragmento HLS que falha vira um "buraco" no vídeo sem aviso (sem retry).
- **Limiar de 1 MB:** um `.mp4` truncado acima de 1 MB é considerado "completo" e não é rebaixado.
- **Sem cancelamento:** depois de enfileirado, um download só para matando o processo (`Ctrl+C`).

---

## 🤝 Contribuição

1. Faça um fork
2. Crie uma branch (`git checkout -b feature/minha-feature`)
3. Commit (`git commit -m 'feat: minha feature'`)
4. Push (`git push origin feature/minha-feature`)
5. Abra um Pull Request

---

<div align="center">

Feito com 💜 e Python por [Eduardo Ribeiro](https://github.com/duribeiro)

</div>
