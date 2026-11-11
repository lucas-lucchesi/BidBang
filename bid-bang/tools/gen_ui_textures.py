"""Génère les textures de l'interface « jeu de société » dans assets/ui_real/.

Style : formes arrondies épaisses, contour sombre, rebord inférieur (effet jeton / bouton en relief),
reflet doux en haut, ombre portée légère. Aucune texture photo-réaliste.

Usage : python3 tools/gen_ui_textures.py [dark|light]   (sans argument : les deux ; nécessite Pillow)
Sortie : assets/ui_real (sombre) et assets/ui_light (clair).
Les PNG sont des 9-patch (marge 30 px) utilisés par theme/main_theme.tres (voir gen_theme.py).

Palette : fond #193A49, panneaux #2C5362, principal #E8A044, texte #F3E4C9, validation #72A48A, danger #C4685A.
"""
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

MODE = sys.argv[1] if len(sys.argv) > 1 else ""
if MODE == "":  # sans argument : génère les deux thèmes
    for m in ("dark", "light"):
        subprocess.run([sys.executable, __file__, m], check=True)
    sys.exit(0)
OUT = Path(__file__).resolve().parent.parent / "assets" / ("ui_real" if MODE == "dark" else "ui_light")
FONT = Path(__file__).resolve().parent.parent / "assets" / "fonts" / "Lato-Bold.ttf"
SIZE, PAD, SS = 96, 8, 4  # taille finale, marge d'ombre, sur-échantillonnage


def hx(s):
    s = s.lstrip("#")
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))


def mix(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def lighter(c, t=0.18):
    return mix(c, (255, 255, 255), t)


def darker(c, t=0.28):
    return mix(c, (0, 0, 0), t)


def vgrad(w, h, top, bottom):
    img = Image.new("RGB", (1, h))
    for y in range(h):
        img.putpixel((0, y), mix(top, bottom, y / max(1, h - 1)))
    return img.resize((w, h))


def rmask(w, h, box, radius, shape="round"):
    m = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(m)
    if shape == "circle":
        d.ellipse(box, fill=255)
    else:
        d.rounded_rectangle(box, radius=radius, fill=255)
    return m


def chunky(name, face, *, lip=None, outline=None, pressed=False, radius=26, alpha=255, shape="round",
           shadow=0.38, glyph=None, glyph_col=None, gloss=0.22, border_col=None, border=0, inset=False):
    """Un jeton : ombre, contour, rebord inférieur (lip), face dégradée, reflet.

    inset=True : creux (champ de saisie) : pas de relief, face sombre, contour fin.
    """
    s = SIZE * SS
    pad = PAD * SS
    r = radius * SS
    lip = lip or darker(face, 0.32)
    outline = outline or darker(face, 0.55)
    lip_h = (0 if inset else (2 if pressed else 6)) * SS
    ol = (3 if not inset else 3) * SS
    box = (pad, pad, s - pad, s - pad)
    canvas = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    # ombre douce
    if shadow > 0:
        off = (2 if pressed else 5) * SS
        sm = rmask(s, s, (box[0], box[1] + off, box[2], box[3] + off), r, shape).filter(ImageFilter.GaussianBlur(4 * SS))
        sh = Image.new("RGBA", (s, s), (6, 22, 30, 0))
        sh.putalpha(sm.point(lambda v: int(v * shadow)))
        canvas.alpha_composite(sh)
    # contour
    o = Image.new("RGBA", (s, s), outline + (255,))
    o.putalpha(rmask(s, s, box, r, shape).point(lambda v: int(v * alpha / 255)))
    canvas.alpha_composite(o)
    # rebord inférieur
    in_box = (box[0] + ol, box[1] + ol, box[2] - ol, box[3] - ol)
    if lip_h:
        lp = Image.new("RGBA", (s, s), lip + (255,))
        lp.putalpha(rmask(s, s, in_box, max(2, r - ol), shape).point(lambda v: int(v * alpha / 255)))
        canvas.alpha_composite(lp)
    # face
    shift = 2 * SS if pressed else 0
    face_box = (in_box[0], in_box[1] + shift, in_box[2], in_box[3] - lip_h + shift)
    fm = rmask(s, s, face_box, max(2, r - ol), shape)
    top = lighter(face, 0.10) if not inset else darker(face, 0.18)
    bot = darker(face, 0.06) if not inset else face
    fimg = vgrad(s, s, top, bot).convert("RGBA")
    fimg.putalpha(fm.point(lambda v: int(v * alpha / 255)))
    canvas.alpha_composite(fimg)
    # liseré de couleur (ex. focus, panneau mis en avant)
    if border and border_col:
        ring = ImageChops.subtract(fm, rmask(s, s, (face_box[0] + border * SS, face_box[1] + border * SS,
                                                    face_box[2] - border * SS, face_box[3] - border * SS),
                                             max(2, r - ol - border * SS), shape))
        rg = Image.new("RGBA", (s, s), border_col + (255,))
        rg.putalpha(ring)
        canvas.alpha_composite(rg)
    # reflet doux en haut de la face
    if gloss and not inset:
        gh = (face_box[3] - face_box[1]) * 0.42
        gm = Image.new("L", (s, s), 0)
        ImageDraw.Draw(gm).rounded_rectangle((face_box[0] + 4 * SS, face_box[1] + 3 * SS, face_box[2] - 4 * SS,
                                              face_box[1] + gh), radius=max(2, r - 2 * ol), fill=int(255 * gloss))
        gm = ImageChops.multiply(gm.filter(ImageFilter.GaussianBlur(3 * SS)), fm)
        gl = Image.new("RGBA", (s, s), (255, 255, 255, 0))
        gl.putalpha(gm)
        canvas.alpha_composite(gl)
    if glyph:
        d = ImageDraw.Draw(canvas)
        c = (s // 2, (face_box[1] + face_box[3]) // 2)
        col = glyph_col or (243, 228, 201)
        t = 8 * SS
        if glyph in ("plus", "minus"):
            d.rounded_rectangle((c[0] - 18 * SS, c[1] - t // 2, c[0] + 18 * SS, c[1] + t // 2), radius=t // 2, fill=col)
        if glyph == "plus":
            d.rounded_rectangle((c[0] - t // 2, c[1] - 18 * SS, c[0] + t // 2, c[1] + 18 * SS), radius=t // 2, fill=col)
        elif glyph == "dollar":
            f = ImageFont.truetype(str(FONT), 52 * SS)
            d.text(c, "$", font=f, fill=col, anchor="mm")
    canvas.resize((SIZE, SIZE), Image.LANCZOS).save(OUT / f"{name}.png")


BG = hx("#193A49")
PANEL = hx("#2C5362")
ORANGE = hx("#E8A044")
CREAM = hx("#F3E4C9")
GREEN = hx("#72A48A")
RED = hx("#C4685A")
DEEP = hx("#10262F")  # contour sombre commun

OUT.mkdir(parents=True, exist_ok=True)

L = MODE == "light"
OL = hx("#2B4A57") if L else DEEP  # contour des éléments neutres
# boutons secondaires
BTN = hx("#BFD3D2") if L else hx("#3E7184")
BLIP = hx("#93AFAE") if L else hx("#2A5262")
chunky("btn_normal", BTN, lip=BLIP, outline=OL)
chunky("btn_hover", lighter(BTN, 0.12), lip=BLIP, outline=OL)
chunky("btn_pressed", darker(BTN, 0.08), lip=BLIP, outline=OL, pressed=True, gloss=0.08)
if L:
    chunky("btn_disabled", hx("#DDD4BF"), lip=hx("#CDC3AB"), outline=hx("#8E9A9A"), alpha=220, gloss=0.05, shadow=0.1)
else:
    chunky("btn_disabled", hx("#2E4F5C"), lip=hx("#26434F"), outline=hx("#17313B"), alpha=210, gloss=0.05, shadow=0.15)
# bouton principal orange
chunky("primary_normal", ORANGE, lip=hx("#B8722A"), outline=hx("#4A2B0E"), gloss=0.32)
chunky("primary_hover", lighter(ORANGE, 0.14), lip=hx("#B8722A"), outline=hx("#4A2B0E"), gloss=0.36)
chunky("primary_pressed", darker(ORANGE, 0.06), lip=hx("#B8722A"), outline=hx("#4A2B0E"), pressed=True, gloss=0.08)
# danger (se coucher) et validation
chunky("danger_normal", RED, lip=hx("#92473D"), outline=hx("#3F1A15"), gloss=0.26)
chunky("danger_pressed", darker(RED, 0.06), lip=hx("#92473D"), outline=hx("#3F1A15"), pressed=True, gloss=0.08)
chunky("success_normal", GREEN, lip=hx("#4F7D66"), outline=hx("#1B3A2C"), gloss=0.26)
chunky("success_pressed", darker(GREEN, 0.06), lip=hx("#4F7D66"), outline=hx("#1B3A2C"), pressed=True, gloss=0.08)
# panneaux : carte posée sur la table
PAN = hx("#FFF8EA") if L else PANEL
PLIP = hx("#DFCFAA") if L else hx("#1F4352")
chunky("card", PAN, lip=PLIP, outline=OL, radius=28, gloss=0.07, shadow=0.25 if L else 0.45)
# panneau mis en avant : liseré orange
chunky("hero", hx("#FFFDF4") if L else hx("#33606F"), lip=hx("#E2D0A6") if L else hx("#21495A"), outline=OL, radius=28,
       gloss=0.10, shadow=0.3 if L else 0.5, border=3, border_col=ORANGE)
# ligne de liste (joueur, objet)
chunky("row", hx("#F1E3C6") if L else hx("#37677A"), lip=hx("#DAC8A0") if L else hx("#2A5262"), outline=OL, radius=22,
       gloss=0.06, shadow=0.15 if L else 0.25)
# pastille d'argent (verte)
chunky("chip_money", GREEN, lip=hx("#4F7D66"), outline=hx("#1B3A2C"), radius=24, gloss=0.25)
# champ de saisie : creux sombre
chunky("field", hx("#FBF5E6") if L else hx("#122C38"), outline=OL, radius=20, inset=True, shadow=0.0, border=0)
chunky("field_focus", hx("#FBF5E6") if L else hx("#122C38"), outline=hx("#4A2B0E"), radius=20, inset=True, shadow=0.0,
       border=3, border_col=ORANGE)
# boutons ronds à icône
for g in ("plus", "minus", "dollar"):
    chunky(f"icon_{g}", ORANGE, lip=hx("#B8722A"), outline=hx("#4A2B0E"), shape="circle", glyph=g,
           glyph_col=hx("#3A210B"), gloss=0.3)
    chunky(f"icon_{g}_hover", lighter(ORANGE, 0.14), lip=hx("#B8722A"), outline=hx("#4A2B0E"), shape="circle",
           glyph=g, glyph_col=hx("#3A210B"), gloss=0.34)
    chunky(f"icon_{g}_pressed", darker(ORANGE, 0.06), lip=hx("#B8722A"), outline=hx("#4A2B0E"), shape="circle",
           pressed=True, glyph=g, glyph_col=hx("#3A210B"), gloss=0.08)
print(len(list(OUT.glob("*.png"))), "textures ->", OUT)
