"""Génère l'icône et les images de l'installeur à partir du logo StaysaProd.

    .venv\\Scripts\\python tools\\make_assets.py
"""

import os

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "assets")
SOURCE = os.path.join(ASSETS, "logo_staysaprod_original.png")

SYMBOL_BOX = (439, 318, 815, 686)  # le « S » + flèche
WORDMARK_BOX = (202, 732, 1052, 883)  # « StaysaProd » (Staysa est en blanc)
DARK_BG = (11, 18, 32, 255)


def square(img: Image.Image, pad_ratio: float = 0.06) -> Image.Image:
    side = int(max(img.size) * (1 + 2 * pad_ratio))
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(img, ((side - img.width) // 2, (side - img.height) // 2), img)
    return canvas


def fit(img: Image.Image, width: int) -> Image.Image:
    return img.resize((width, round(img.height * width / img.width)), Image.LANCZOS)


def wizard_large(symbol, wordmark, w, h):
    """Panneau gauche de l'installeur : fond sombre, symbole + nom."""
    img = Image.new("RGBA", (w, h), DARK_BG)
    s = fit(symbol, int(w * 0.62))
    t = fit(wordmark, int(w * 0.84))
    top = int(h * 0.30)
    img.alpha_composite(s, ((w - s.width) // 2, top))
    img.alpha_composite(t, ((w - t.width) // 2, top + s.height + int(h * 0.06)))
    return img.convert("RGB")


def wizard_small(symbol, side):
    img = Image.new("RGBA", (side, side), (255, 255, 255, 255))
    s = fit(symbol, int(side * 0.9))
    img.alpha_composite(s, ((side - s.width) // 2, (side - s.height) // 2))
    return img.convert("RGB")


def main():
    logo = Image.open(SOURCE).convert("RGBA")
    symbol = square(logo.crop(SYMBOL_BOX))
    wordmark = logo.crop(WORDMARK_BOX)

    fit(symbol, 512).save(os.path.join(ASSETS, "logo_symbol.png"))
    symbol.resize((256, 256), Image.LANCZOS).save(
        os.path.join(ASSETS, "icon.ico"),
        sizes=[(16, 16), (20, 20), (24, 24), (32, 32), (40, 40), (48, 48),
               (64, 64), (128, 128), (256, 256)])

    # 100 % et 200 % : l'installeur choisit selon la résolution de l'écran
    wizard_large(symbol, wordmark, 164, 314).save(os.path.join(ASSETS, "wizard_large.bmp"))
    wizard_large(symbol, wordmark, 328, 628).save(os.path.join(ASSETS, "wizard_large_200.bmp"))
    wizard_small(symbol, 55).save(os.path.join(ASSETS, "wizard_small.bmp"))
    wizard_small(symbol, 110).save(os.path.join(ASSETS, "wizard_small_200.bmp"))
    print("Images générées dans", ASSETS)


if __name__ == "__main__":
    main()
