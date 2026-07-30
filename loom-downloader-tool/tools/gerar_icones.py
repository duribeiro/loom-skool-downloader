"""Gera os ícones PNG da extensão (Sifão) a partir do design system.

Mark: tile arredondado com gradiente azul→aqua da marca + glifo branco (seta de
download sobre a bandeja). Fonte do glifo = docs/design-system/README.md.

Uso:
    pip install pillow
    python tools/gerar_icones.py

Saída: extension/icons/icon16.png, icon32.png, icon48.png, icon128.png
"""
import os

from PIL import Image, ImageDraw

# Cores do design system (docs/design-system/README.md)
AZUL = (0x3D, 0x7B, 0xFF)
AQUA = (0x00, 0xE0, 0xC6)
BRANCO = (255, 255, 255, 255)

SS = 8          # supersampling p/ antialias
TAMANHOS = [16, 32, 48, 128]

PASTA_SAIDA = os.path.join(os.path.dirname(__file__), "..", "extension", "icons")


def _mistura(a, b):
    return tuple((x + y) // 2 for x, y in zip(a, b))


def _gradiente(s):
    """Gradiente diagonal azul(topo-esq) → aqua(baixo-dir) via upscale de 2x2."""
    g = Image.new("RGB", (2, 2))
    meio = _mistura(AZUL, AQUA)
    g.putpixel((0, 0), AZUL)
    g.putpixel((1, 0), meio)
    g.putpixel((0, 1), meio)
    g.putpixel((1, 1), AQUA)
    return g.resize((s, s), Image.BILINEAR).convert("RGBA")


def _glifo(draw, s):
    """Seta de download sobre a bandeja, em coordenadas do viewBox 24x24."""
    k = s / 24.0
    w = max(1, round(2.4 * k))

    def P(x, y):
        return (x * k, y * k)

    # Traços principais (cantos/junções arredondados via círculos nos vértices)
    draw.line([P(12, 4), P(12, 13.7)], fill=BRANCO, width=w)
    draw.line([P(7.5, 9.8), P(12, 14.3), P(16.5, 9.8)], fill=BRANCO, width=w, joint="curve")
    draw.line([P(6, 19), P(18, 19)], fill=BRANCO, width=w)

    r = w / 2.0
    for (x, y) in [P(12, 4), P(12, 13.7), P(7.5, 9.8), P(12, 14.3),
                   P(16.5, 9.8), P(6, 19), P(18, 19)]:
        draw.ellipse([x - r, y - r, x + r, y + r], fill=BRANCO)


def gerar(tamanho):
    s = tamanho * SS
    img = _gradiente(s)

    # Máscara de cantos arredondados (22% do lado, igual ao design system).
    mask = Image.new("L", (s, s), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, s - 1, s - 1], radius=int(0.22 * s), fill=255)
    img.putalpha(mask)

    _glifo(ImageDraw.Draw(img), s)

    return img.resize((tamanho, tamanho), Image.LANCZOS)


def main():
    os.makedirs(PASTA_SAIDA, exist_ok=True)
    for t in TAMANHOS:
        caminho = os.path.join(PASTA_SAIDA, f"icon{t}.png")
        gerar(t).save(caminho)
        print(f"✅ {caminho}")


if __name__ == "__main__":
    main()
