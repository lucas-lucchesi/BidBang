"""Génère les textures de l'interface réaliste (bois sombre, or, velours) dans assets/ui_real/.

Usage : python tools/gen_ui_textures.py   (nécessite Pillow)
Les PNG sont des 9-patch (marge 30 px) utilisés par theme/main_theme.tres.
Pour remplacer un style par une vraie texture, déposer un PNG du même nom dans assets/ui_real/.
"""
import random
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

OUT = Path(__file__).resolve().parent.parent / "assets" / "ui_real"
FONT = Path(__file__).resolve().parent.parent / "assets" / "fonts" / "Lato-Bold.ttf"
SIZE, PAD, SS = 96, 8, 4  # taille finale, marge d'ombre, sur-échantillonnage
random.seed(11)


def lerp(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def rgb(c):
    return tuple(int(v * 255) for v in c)


def vgrad(w, h, top, bottom):
    img = Image.new("RGB", (w, h))
    px = img.load()
    for y in range(h):
        c = lerp(top, bottom, y / max(1, h - 1))
        for x in range(w):
            px[x, y] = c
    return img


def rmask(w, h, box, radius, shape="round"):
    m = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(m)
    if shape == "circle":
        d.ellipse(box, fill=255)
    else:
        d.rounded_rectangle(box, radius=radius, fill=255)
    return m


def grain(img, amount=7):
    noise = Image.effect_noise(img.size, 40).convert("L")
    noise = noise.point(lambda v: 128 + (v - 128) * amount // 40)
    return ImageChops.add(img, Image.merge("RGB", (noise,) * 3), scale=1.0, offset=-128)


def button(name, top, bottom, border_top, border_bottom, *, pressed=False, radius=18,
           border=3, alpha=255, glow=None, shape="round", shadow=0.55, glyph=None, gloss=0.18):
    s = SIZE * SS
    pad = PAD * SS
    off = 2 * SS if pressed else 0
    box = (pad, pad + off, s - pad, s - pad + (0 if pressed else 0) - (0 if pressed else 0))
    box = (pad, pad + off, s - pad, s - pad)
    r = radius * SS
    canvas = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    # ombre portée
    sh_mask = rmask(s, s, (box[0], box[1] + (3 if not pressed else 1) * SS, box[2], box[3] + (3 if not pressed else 1) * SS), r, shape)
    sh = Image.new("RGBA", (s, s), (0, 0, 0, int(255 * shadow)))
    sh.putalpha(sh_mask.filter(ImageFilter.GaussianBlur(4 * SS)).point(lambda v: int(v * shadow)))
    canvas.alpha_composite(sh)
    if glow:
        gm = rmask(s, s, box, r, shape).filter(ImageFilter.GaussianBlur(6 * SS))
        g = Image.new("RGBA", (s, s), glow + (0,))
        g.putalpha(gm.point(lambda v: int(v * 0.55)))
        canvas.alpha_composite(g)
    # bordure (dégradé) puis corps (dégradé)
    outer = rmask(s, s, box, r, shape)
    bimg = vgrad(s, s, border_top, border_bottom).convert("RGBA")
    bimg.putalpha(outer)
    canvas.alpha_composite(bimg)
    bw = border * SS
    inner_box = (box[0] + bw, box[1] + bw, box[2] - bw, box[3] - bw)
    inner = rmask(s, s, inner_box, max(2, r - bw), shape)
    body = grain(vgrad(s, s, top, bottom)).convert("RGBA")
    body.putalpha(inner.point(lambda v: int(v * alpha / 255)))
    canvas.alpha_composite(body)
    # reflet doux en haut
    gl = Image.new("RGBA", (s, s), (255, 255, 255, 0))
    gm = Image.new("L", (s, s), 0)
    gd = ImageDraw.Draw(gm)
    gd.rounded_rectangle((inner_box[0] + 2 * SS, inner_box[1] + 2 * SS, inner_box[2] - 2 * SS,
                          inner_box[1] + (inner_box[3] - inner_box[1]) * 0.45), radius=max(2, r - 2 * bw), fill=int(255 * gloss))
    gm = ImageChops.multiply(gm.filter(ImageFilter.GaussianBlur(3 * SS)), inner)
    gl.putalpha(gm)
    canvas.alpha_composite(gl)
    if glyph:
        d = ImageDraw.Draw(canvas)
        c = (s // 2, s // 2 + off // 2)
        col = (245, 236, 214, 255)
        t = 7 * SS
        if glyph == "plus":
            d.rounded_rectangle((c[0] - 20 * SS, c[1] - t // 2, c[0] + 20 * SS, c[1] + t // 2), radius=t // 2, fill=col)
            d.rounded_rectangle((c[0] - t // 2, c[1] - 20 * SS, c[0] + t // 2, c[1] + 20 * SS), radius=t // 2, fill=col)
        elif glyph == "minus":
            d.rounded_rectangle((c[0] - 20 * SS, c[1] - t // 2, c[0] + 20 * SS, c[1] + t // 2), radius=t // 2, fill=col)
        elif glyph == "dollar":
            f = ImageFont.truetype(str(FONT), 52 * SS)
            d.text(c, "$", font=f, fill=col, anchor="mm")
    canvas.resize((SIZE, SIZE), Image.LANCZOS).save(OUT / f"{name}.png")


WOOD = ((0.34, 0.19, 0.13), (0.17, 0.09, 0.07))
GOLDB = ((0.95, 0.78, 0.38), (0.58, 0.40, 0.14))
OUT.mkdir(parents=True, exist_ok=True)
T = lambda c: tuple(int(v * 255) for v in c)

# boutons bois sombre + liseré or
button("btn_normal", T(WOOD[0]), T(WOOD[1]), T(GOLDB[0]), T(GOLDB[1]))
button("btn_hover", T((0.42, 0.24, 0.16)), T((0.22, 0.12, 0.09)), T((1, 0.86, 0.5)), T((0.7, 0.5, 0.2)))
button("btn_pressed", T((0.14, 0.07, 0.06)), T((0.24, 0.13, 0.10)), T((0.6, 0.45, 0.2)), T((0.8, 0.62, 0.3)), pressed=True, gloss=0.05)
button("btn_disabled", T((0.2, 0.15, 0.14)), T((0.14, 0.1, 0.1)), T((0.4, 0.34, 0.28)), T((0.3, 0.25, 0.2)), alpha=200, gloss=0.05, shadow=0.3)
# bouton principal doré
button("primary_normal", T((0.99, 0.84, 0.46)), T((0.80, 0.55, 0.17)), T((1, 0.93, 0.7)), T((0.45, 0.28, 0.08)), gloss=0.32)
button("primary_hover", T((1, 0.9, 0.58)), T((0.88, 0.62, 0.22)), T((1, 0.96, 0.8)), T((0.5, 0.32, 0.1)), gloss=0.38, glow=(255, 200, 90))
button("primary_pressed", T((0.74, 0.5, 0.15)), T((0.92, 0.7, 0.3)), T((0.45, 0.28, 0.08)), T((0.9, 0.75, 0.4)), pressed=True, gloss=0.05)
# bouton rouge velours
button("danger_normal", T((0.58, 0.13, 0.15)), T((0.32, 0.05, 0.08)), T(GOLDB[0]), T(GOLDB[1]))
button("danger_pressed", T((0.25, 0.04, 0.06)), T((0.4, 0.08, 0.1)), T((0.6, 0.45, 0.2)), T((0.8, 0.62, 0.3)), pressed=True, gloss=0.04)
# panneaux : velours sombre, liseré or fin
button("card", T((0.17, 0.08, 0.10)), T((0.09, 0.04, 0.06)), T((0.85, 0.68, 0.32)), T((0.5, 0.36, 0.14)), radius=20, border=2, alpha=238, gloss=0.07, shadow=0.7)
button("hero", T((0.22, 0.11, 0.09)), T((0.11, 0.05, 0.05)), T((1, 0.86, 0.45)), T((0.75, 0.52, 0.18)), radius=20, border=4, alpha=242, gloss=0.1, glow=(240, 180, 70), shadow=0.7)
button("chip_money", T((0.12, 0.36, 0.23)), T((0.05, 0.2, 0.12)), T(GOLDB[0]), T(GOLDB[1]), radius=22, gloss=0.2)
# champs de saisie : creux sombre
button("field", T((0.06, 0.03, 0.03)), T((0.12, 0.07, 0.06)), T((0.55, 0.42, 0.22)), T((0.7, 0.55, 0.3)), radius=16, border=2, gloss=0.0, shadow=0.0)
button("field_focus", T((0.05, 0.03, 0.03)), T((0.11, 0.06, 0.05)), T((1, 0.85, 0.45)), T((1, 0.75, 0.3)), radius=16, border=3, gloss=0.0, shadow=0.0, glow=(255, 200, 90))
# boutons ronds à icône
for g in ("plus", "minus", "dollar"):
    button(f"icon_{g}", T(WOOD[0]), T(WOOD[1]), T(GOLDB[0]), T(GOLDB[1]), shape="circle", glyph=g, gloss=0.2)
    button(f"icon_{g}_hover", T((0.45, 0.26, 0.17)), T((0.24, 0.13, 0.1)), T((1, 0.86, 0.5)), T((0.7, 0.5, 0.2)), shape="circle", glyph=g, gloss=0.25)
    button(f"icon_{g}_pressed", T((0.14, 0.07, 0.06)), T((0.24, 0.13, 0.10)), T((0.6, 0.45, 0.2)), T((0.8, 0.62, 0.3)), shape="circle", pressed=True, glyph=g, gloss=0.05)
print(len(list(OUT.glob("*.png"))), "textures ->", OUT)
