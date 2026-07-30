# Sifão — Design System

Identidade visual unificada da extensão. **Uma extensão, uma linguagem visual só:**
o mesmo *pill* sobre qualquer vídeo (Loom, YouTube, Vimeo) e toda a inteligência de
curso e status no popup. Referência de produto: **Internet Download Manager**.

> **Nome "Sifão"** (puxa a mídia pra você) é o nome de trabalho — trocável.
> Referência visual navegável: [`mockup.html`](./mockup.html) (abra no navegador; tem
> tema claro e escuro).

---

## Princípios

1. **Um acento, um gradiente, um mark em tudo.** Nada de cor por plataforma.
2. **Estado ≠ marca.** Cores semânticas (online/erro) são separadas do acento.
3. **Ação na página é o pill; lote e configuração moram no popup.** A página do
   Skool/YouTube volta a ser dela mesma — sem botões flutuando "tipo anúncio".
4. **Honesto com fontes.** Sem webfont via CDN (o CSP/ambiente bloqueia e cai em
   fallback silencioso). Usamos stack de sistema + uma mono utilitária.

---

## Cores

Paleta própria e neutra entre plataformas: **azul-elétrico** com um **aqua** de apoio
usado só no gradiente do mark. Fugimos de propósito do verde-Skool, do vermelho-YouTube
e do clichê roxo→azul.

| Token | Hex | Uso |
|---|---|---|
| `--accent` | `#3D7BFF` | Cor principal: pills, botões, foco, links de ação |
| `--accent-2` | `#00E0C6` | Segundo tom do gradiente **apenas no mark/ícone** |
| `--ok` | `#25C26E` | Servidor online, download concluído |
| `--bad` | `#FF5A5A` | Servidor offline, erro |
| `--warn` | `#FFB020` | Aviso (uso pontual) |

### Neutros — tema claro

| Token | Hex |
|---|---|
| `--bg` | `#F6F7FB` |
| `--surface` | `#FFFFFF` |
| `--surface-2` | `#EEF1F8` |
| `--line` | `#DDE2EE` |
| `--ink` (texto) | `#141826` |
| `--muted` | `#5C647C` |
| `--faint` | `#8A93AD` |

### Neutros — tema escuro

| Token | Hex |
|---|---|
| `--bg` | `#0E1220` |
| `--surface` | `#171B2E` |
| `--surface-2` | `#1E2338` |
| `--line` | `#2A3149` |
| `--ink` (texto) | `#E7EAF3` |
| `--muted` | `#9AA3BE` |
| `--faint` | `#6C769A` |

Os neutros são **azulados de propósito** (enviesados para o acento), nunca cinza puro.

---

## Tipografia

Sem webfont — hierarquia por peso, tamanho e tracking.

| Papel | Stack | Onde |
|---|---|---|
| **Sans** (display + corpo) | `"Segoe UI", system-ui, -apple-system, Roboto, Helvetica, Arial, sans-serif` | Títulos, botões, texto |
| **Mono** (utilitária) | `"Cascadia Code", "Consolas", ui-monospace, "SF Mono", Menlo, monospace` | Caminhos de arquivo, rótulos, status, dados |

- **Wordmark:** sans 800, `letter-spacing: -.02em`.
- **Eyebrows / rótulos:** mono, `text-transform: uppercase`, `letter-spacing: .12em–.16em`.
- **Caminhos de arquivo** (ex: `output/YouTube/Canal/Aula.mp4`) sempre em mono — reforça
  a cara de "download manager".

---

## Forma

| Token | Valor |
|---|---|
| `--radius` | `14px` (cards, popup, players) |
| `--radius-sm` | `10px` (botões, inputs) |
| Pill | `border-radius: 999px` |
| Tile do ícone | `border-radius: 22%` |
| `--shadow` (claro) | `0 10px 30px rgba(20,30,60,.10), 0 2px 8px rgba(20,30,60,.06)` |
| `--shadow` (escuro) | `0 14px 40px rgba(0,0,0,.45), 0 2px 10px rgba(0,0,0,.35)` |

---

## Componentes

### 1. Pill (na página)

O **mesmo** componente sobre qualquer player. Só o rótulo muda:

- Skool/Loom → **Baixar aula**
- YouTube → **Baixar vídeo**
- Skool/Vimeo → **Baixar vídeo**

Especificação:

- Ancorado ao canto superior direito do vídeo (`position: absolute; top:12px; right:12px`).
- `border-radius: 999px`, fundo `linear-gradient(180deg,#4a83ff,#2f6bff)`, texto branco
  650, borda `1px rgba(255,255,255,.14)`, sombra `0 6px 16px rgba(10,20,50,.35)`.
- Ícone do mark (⬇ seta sobre bandeja) 15px à esquerda do rótulo, `gap: 8px`.
- `:hover` → `filter: brightness(1.07)`.

### 2. Popup — central de controle (~320px)

Ordem de cima para baixo:

1. **Cabeçalho:** mark + "Sifão" + indicador de status (`● servidor online/offline`,
   ping em `localhost:5000`).
2. **Curso detectado na aba** (contextual — só quando a aba ativa é uma classroom do
   Skool): nome + nº de aulas + botão **Baixar curso inteiro**.
3. **Link do YouTube:** input + botão **Baixar vídeo colado**.
4. **Na fila / recentes:** lista com nome (mono), barra de progresso e estado.

Fora do Skool, o bloco de curso some. Página do site fica **limpa** — o botão flutuante
de "curso inteiro" deixa de existir.

### 3. Ícone da toolbar

Tile arredondado no gradiente da marca + glifo branco (seta de download sobre a
bandeja). Simples de propósito: legível a **16px**, bonito a **128px**. Gerar PNGs em
16 / 32 / 48 / 128 para `manifest.json` (`icons` + `action.default_icon`).

**Fonte do glifo (SVG):**

```svg
<svg viewBox="0 0 24 24" fill="none">
  <path d="M12 4v9.5"          stroke="#fff" stroke-width="2.4" stroke-linecap="round"/>
  <path d="M7.5 9.8 12 14.3l4.5-4.5" stroke="#fff" stroke-width="2.4"
        stroke-linecap="round" stroke-linejoin="round"/>
  <path d="M6 19h12"           stroke="#fff" stroke-width="2.4" stroke-linecap="round"/>
</svg>
```

Tile: `linear-gradient(135deg, #3D7BFF, #00E0C6)`, cantos `22%`, glifo ocupando ~62% do tile.

---

## Organização de arquivos baixados

Mesma lógica em todas as origens: `output/<Origem>/<Agrupador>/<Aula>.mp4`.

| Origem | Padrão | Exemplo |
|---|---|---|
| Skool | `output/<Comunidade>/<Curso>/<Módulo>/<Aula>.mp4` | `output/BACKROOM.EXE/GANG.EXE/Money Skills/1.1 — Dissecação de Skills.mp4` |
| **YouTube** | `output/YouTube/<Canal>/<Título>.mp4` | `output/YouTube/Hashtag Treinamentos/Aula 1 - Criando agentes de IA.mp4` |

O nome do canal do YouTube vem do próprio `yt-dlp` (metadado `channel`), resolvido no
servidor — vale para qualquer entrada (pill, popup ou link colado).

---

## Antes → depois

| Antes (bagunça) | Depois (Sifão) |
|---|---|
| Verde `#00d084` numa tela, roxo `#6c5ce7` na outra | Um acento, um gradiente, um mark |
| 4 posições (sobre o vídeo, 2× canto inferior, flutuante) | Pill no canto do vídeo; lote e status no popup |
| 3 textos p/ "baixar vídeo", sem ícone de marca | Ícone de toolbar próprio (16→128) |
| Botão de curso flutuando "tipo anúncio" | Página limpa, cara de produto |

---

## Tokens como CSS custom properties

Base para o `ui.css` da extensão (tema por `prefers-color-scheme` + override por
`:root[data-theme=...]`):

```css
:root{
  --accent:#3D7BFF; --accent-2:#00E0C6;
  --ok:#25C26E; --bad:#FF5A5A; --warn:#FFB020;
  --bg:#F6F7FB; --surface:#FFFFFF; --surface-2:#EEF1F8;
  --line:#DDE2EE; --ink:#141826; --muted:#5C647C; --faint:#8A93AD;
  --radius:14px; --radius-sm:10px;
  --mono:"Cascadia Code","Consolas",ui-monospace,"SF Mono",Menlo,monospace;
  --sans:"Segoe UI",system-ui,-apple-system,Roboto,Helvetica,Arial,sans-serif;
}
@media (prefers-color-scheme:dark){
  :root{
    --bg:#0E1220; --surface:#171B2E; --surface-2:#1E2338;
    --line:#2A3149; --ink:#E7EAF3; --muted:#9AA3BE; --faint:#6C769A;
  }
}
```
