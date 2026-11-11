"""Écrit theme/main_theme.tres (style jeu de société : bleu pétrole, orange, formes épaisses).
Usage : python3 tools/gen_theme.py [dark|light]   (sans argument : les deux ; après tools/gen_ui_textures.py)
Sortie : theme/main_theme.tres (sombre) et theme/light_theme.tres (clair).

Palette : fond #193A49, panneaux #2C5362, principal #E8A044, texte #F3E4C9, validation #72A48A, danger #C4685A.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODE = sys.argv[1] if len(sys.argv) > 1 else ""
if MODE == "":  # sans argument : génère les deux thèmes
    for m in ("dark", "light"):
        subprocess.run([sys.executable, __file__, m], check=True)
    sys.exit(0)
L = MODE == "light"
TEXDIR = "ui_light" if L else "ui_real"
OUTFILE = "light_theme.tres" if L else "main_theme.tres"
# couleurs qui changent selon le thème
ACC = "Color(0.74, 0.42, 0.1, 1)" if L else "Color(0.91, 0.627, 0.267, 1)"   # accents (titres, étiquettes)
LSH = "Color(0, 0, 0, 0)" if L else "Color(0.04, 0.1, 0.13, 0.55)"          # ombre de texte
TSH = "Color(1, 1, 1, 0.6)" if L else "Color(0.04, 0.1, 0.13, 0.85)"
BHOV = "Color(0.06, 0.18, 0.24, 1)" if L else "Color(1, 0.96, 0.88, 1)"
BPR = "Color(0.1, 0.25, 0.32, 1)" if L else "Color(0.85, 0.8, 0.7, 1)"
BDIS = "Color(0.5, 0.57, 0.58, 1)" if L else "Color(0.55, 0.64, 0.66, 1)"
PH = "Color(0.55, 0.6, 0.6, 1)" if L else "Color(0.5, 0.6, 0.62, 1)"
ERR = "Color(0.69, 0.27, 0.2, 1)" if L else "Color(0.96, 0.6, 0.54, 1)"
INFO = "Color(0.2, 0.5, 0.35, 1)" if L else "Color(0.62, 0.87, 0.72, 1)"
BAR_BG = "Color(0.85, 0.79, 0.68, 1)" if L else "Color(0.063, 0.149, 0.184, 1)"
BAR_BORDER = "Color(0.17, 0.29, 0.34, 1)" if L else "Color(0.039, 0.098, 0.122, 1)"
M = 30  # marge 9-patch des textures (voir gen_ui_textures.py)
TEX = ["btn_normal", "btn_hover", "btn_pressed", "btn_disabled", "primary_normal", "primary_hover",
       "primary_pressed", "danger_normal", "danger_pressed", "success_normal", "success_pressed",
       "card", "hero", "row", "chip_money", "field", "field_focus"]

out = ['[gd_resource type="Theme" format=3]\n']
for t in TEX:
    out.append(f'[ext_resource type="Texture2D" path="res://assets/{TEXDIR}/{t}.png" id="t_{t}"]')
out += ['[ext_resource type="FontFile" path="res://assets/fonts/Fredoka.ttf" id="fredoka"]', '']

# Fredoka est une police variable : on déclare les graisses utilisées (tag OpenType "wght" = 2003265652)
for fid, weight in (("font", 400), ("font_bold", 600), ("font_title", 700)):
    out.append(f'[sub_resource type="FontVariation" id="{fid}"]\nbase_font = ExtResource("fredoka")\n'
               f'variation_opentype = {{ 2003265652: {weight}.0 }}\n')


def box(id_, tex, content, extra=""):
    l, t, r, b = content
    return (f'[sub_resource type="StyleBoxTexture" id="{id_}"]\ntexture = ExtResource("t_{tex}")\n'
            f'texture_margin_left = {M}.0\ntexture_margin_top = {M}.0\ntexture_margin_right = {M}.0\ntexture_margin_bottom = {M}.0\n'
            f'content_margin_left = {l}.0\ncontent_margin_top = {t}.0\ncontent_margin_right = {r}.0\ncontent_margin_bottom = {b}.0\n{extra}\n')


# marges de contenu : le bas est plus grand (rebord + ombre), l'appui l'inverse
BTN = (30, 16, 30, 24)
BTN_DN = (30, 20, 30, 20)
PRI = (36, 20, 36, 28)
PRI_DN = (36, 24, 36, 24)
out.append(box("btn_normal", "btn_normal", BTN))
out.append(box("btn_hover", "btn_hover", BTN))
out.append(box("btn_pressed", "btn_pressed", BTN_DN))
out.append(box("btn_disabled", "btn_disabled", BTN))
out.append(box("primary_normal", "primary_normal", PRI))
out.append(box("primary_hover", "primary_hover", PRI))
out.append(box("primary_pressed", "primary_pressed", PRI_DN))
out.append(box("danger_normal", "danger_normal", BTN))
out.append(box("danger_pressed", "danger_pressed", BTN_DN))
out.append(box("success_normal", "success_normal", BTN))
out.append(box("success_pressed", "success_pressed", BTN_DN))
out.append(box("card", "card", (30, 24, 30, 32)))
out.append(box("hero", "hero", (32, 24, 32, 32)))
out.append(box("row", "row", (22, 12, 22, 20)))
out.append(box("chip", "btn_normal", (22, 8, 22, 16)))
out.append(box("chip_money", "chip_money", (24, 8, 24, 16)))
out.append(box("field", "field", (24, 16, 24, 16)))
out.append(box("field_focus", "field_focus", (24, 16, 24, 16)))
out.append(box("small_normal", "btn_normal", (20, 8, 20, 16)))
out.append(box("small_hover", "btn_hover", (20, 8, 20, 16)))
out.append(box("small_pressed", "btn_pressed", (20, 12, 20, 12)))
out.append(box("choice_on", "primary_normal", (20, 8, 20, 16)))
out.append(box("popup", "card", (22, 20, 22, 22)))
out.append(box("popup_hover", "btn_hover", (16, 8, 16, 10)))
out.append('''[sub_resource type="StyleBoxEmpty" id="back_normal"]
content_margin_left = 8.0
content_margin_top = 8.0
content_margin_right = 8.0
content_margin_bottom = 8.0

[sub_resource type="StyleBoxFlat" id="bar_bg"]
bg_color = @BAR_BG@
corner_radius_top_left = 12
corner_radius_top_right = 12
corner_radius_bottom_right = 12
corner_radius_bottom_left = 12
border_width_left = 3
border_width_top = 3
border_width_right = 3
border_width_bottom = 3
border_color = @BAR_BORDER@

[sub_resource type="StyleBoxFlat" id="bar_fill"]
bg_color = Color(0.91, 0.627, 0.267, 1)
corner_radius_top_left = 9
corner_radius_top_right = 9
corner_radius_bottom_right = 9
corner_radius_bottom_left = 9

[resource]'''.replace('@BAR_BG@', BAR_BG).replace('@BAR_BORDER@', BAR_BORDER))
CREAM = "Color(0.098, 0.227, 0.286, 1)" if L else "Color(0.953, 0.894, 0.788, 1)"
MUTED = "Color(0.36, 0.45, 0.48, 1)" if L else "Color(0.69, 0.76, 0.76, 1)"
INK = "Color(0.227, 0.129, 0.043, 1)"  # texte foncé sur bouton orange
res = f'''default_font = SubResource("font")
default_font_size = 28
Label/colors/font_color = {CREAM}
Label/colors/font_shadow_color = {LSH}
Label/constants/shadow_offset_x = 0
Label/constants/shadow_offset_y = 2
Button/colors/font_color = {CREAM}
Button/colors/font_hover_color = {BHOV}
Button/colors/font_pressed_color = {BPR}
Button/colors/font_disabled_color = {BDIS}
Button/colors/font_shadow_color = {LSH}
Button/constants/shadow_offset_y = 2
Button/fonts/font = SubResource("font_bold")
Button/font_sizes/font_size = 28
Button/styles/normal = SubResource("btn_normal")
Button/styles/hover = SubResource("btn_hover")
Button/styles/pressed = SubResource("btn_pressed")
Button/styles/disabled = SubResource("btn_disabled")
Button/styles/focus = SubResource("back_normal")
LineEdit/colors/font_color = {CREAM}
LineEdit/colors/caret_color = {ACC}
LineEdit/colors/selection_color = Color(0.91, 0.627, 0.267, 0.45)
LineEdit/colors/font_placeholder_color = {PH}
LineEdit/constants/caret_width = 3
LineEdit/fonts/font = SubResource("font_bold")
LineEdit/font_sizes/font_size = 30
LineEdit/styles/normal = SubResource("field")
LineEdit/styles/focus = SubResource("field_focus")
OptionButton/styles/normal = SubResource("btn_normal")
OptionButton/styles/hover = SubResource("btn_hover")
OptionButton/styles/pressed = SubResource("btn_pressed")
OptionButton/styles/focus = SubResource("back_normal")
OptionButton/colors/font_color = {CREAM}
OptionButton/fonts/font = SubResource("font_bold")
OptionButton/font_sizes/font_size = 28
PopupMenu/styles/panel = SubResource("popup")
PopupMenu/styles/hover = SubResource("popup_hover")
PopupMenu/colors/font_color = {CREAM}
PopupMenu/colors/font_hover_color = Color(1, 1, 1, 1)
PopupMenu/font_sizes/font_size = 28
PanelContainer/styles/panel = SubResource("card")
HeroPanel/base_type = &"PanelContainer"
HeroPanel/styles/panel = SubResource("hero")
RowPanel/base_type = &"PanelContainer"
RowPanel/styles/panel = SubResource("row")
ChipPanel/base_type = &"PanelContainer"
ChipPanel/styles/panel = SubResource("chip")
MoneyChip/base_type = &"PanelContainer"
MoneyChip/styles/panel = SubResource("chip_money")
ProgressBar/styles/background = SubResource("bar_bg")
ProgressBar/styles/fill = SubResource("bar_fill")
PrimaryButton/base_type = &"Button"
PrimaryButton/colors/font_color = {INK}
PrimaryButton/colors/font_hover_color = {INK}
PrimaryButton/colors/font_pressed_color = {INK}
PrimaryButton/colors/font_disabled_color = Color(0.5, 0.42, 0.32, 1)
PrimaryButton/colors/font_shadow_color = Color(1, 0.9, 0.7, 0.35)
PrimaryButton/constants/shadow_offset_y = 1
PrimaryButton/fonts/font = SubResource("font_title")
PrimaryButton/font_sizes/font_size = 36
PrimaryButton/styles/normal = SubResource("primary_normal")
PrimaryButton/styles/hover = SubResource("primary_hover")
PrimaryButton/styles/pressed = SubResource("primary_pressed")
PrimaryButton/styles/disabled = SubResource("btn_disabled")
DangerButton/base_type = &"Button"
DangerButton/colors/font_color = Color(1, 0.94, 0.9, 1)
DangerButton/fonts/font = SubResource("font_title")
DangerButton/font_sizes/font_size = 30
DangerButton/styles/normal = SubResource("danger_normal")
DangerButton/styles/hover = SubResource("danger_normal")
DangerButton/styles/pressed = SubResource("danger_pressed")
SuccessButton/base_type = &"Button"
SuccessButton/colors/font_color = Color(0.06, 0.16, 0.11, 1)
SuccessButton/colors/font_hover_color = Color(0.06, 0.16, 0.11, 1)
SuccessButton/colors/font_pressed_color = Color(0.06, 0.16, 0.11, 1)
SuccessButton/colors/font_shadow_color = Color(1, 1, 1, 0.25)
SuccessButton/fonts/font = SubResource("font_title")
SuccessButton/font_sizes/font_size = 32
SuccessButton/styles/normal = SubResource("success_normal")
SuccessButton/styles/hover = SubResource("success_normal")
SuccessButton/styles/pressed = SubResource("success_pressed")
SmallButton/base_type = &"Button"
SmallButton/font_sizes/font_size = 26
SmallButton/styles/normal = SubResource("small_normal")
SmallButton/styles/hover = SubResource("small_hover")
SmallButton/styles/pressed = SubResource("small_pressed")
ChoiceButton/base_type = &"Button"
ChoiceButton/font_sizes/font_size = 26
ChoiceButton/colors/font_pressed_color = {INK}
ChoiceButton/colors/font_hover_pressed_color = {INK}
ChoiceButton/colors/font_focus_color = {CREAM}
ChoiceButton/colors/font_shadow_color = {LSH}
ChoiceButton/styles/normal = SubResource("small_normal")
ChoiceButton/styles/hover = SubResource("small_hover")
ChoiceButton/styles/pressed = SubResource("choice_on")
ChoiceButton/styles/hover_pressed = SubResource("choice_on")
ChoiceButton/styles/focus = SubResource("back_normal")
BackButton/base_type = &"Button"
BackButton/colors/font_color = {ACC}
BackButton/colors/font_hover_color = Color(1, 0.78, 0.45, 1)
BackButton/colors/font_pressed_color = Color(1, 0.78, 0.45, 1)
BackButton/styles/normal = SubResource("back_normal")
BackButton/styles/hover = SubResource("back_normal")
BackButton/styles/pressed = SubResource("back_normal")
TitleLabel/base_type = &"Label"
TitleLabel/colors/font_color = {ACC}
TitleLabel/colors/font_shadow_color = {TSH}
TitleLabel/constants/shadow_offset_y = 5
TitleLabel/fonts/font = SubResource("font_title")
TitleLabel/font_sizes/font_size = 84
HeadingLabel/base_type = &"Label"
HeadingLabel/fonts/font = SubResource("font_title")
HeadingLabel/font_sizes/font_size = 38
SectionLabel/base_type = &"Label"
SectionLabel/colors/font_color = {ACC}
SectionLabel/fonts/font = SubResource("font_title")
SectionLabel/font_sizes/font_size = 28
MutedLabel/base_type = &"Label"
MutedLabel/colors/font_color = {MUTED}
MutedLabel/font_sizes/font_size = 24
ErrorLabel/base_type = &"Label"
ErrorLabel/colors/font_color = {ERR}
ErrorLabel/fonts/font = SubResource("font_bold")
InfoLabel/base_type = &"Label"
InfoLabel/colors/font_color = {INFO}
InfoLabel/fonts/font = SubResource("font_bold")
FieldLabel/base_type = &"Label"
FieldLabel/colors/font_color = {ACC}
FieldLabel/fonts/font = SubResource("font_bold")
FieldLabel/font_sizes/font_size = 24
MoneyLabel/base_type = &"Label"
MoneyLabel/colors/font_color = Color(0.06, 0.16, 0.11, 1)
MoneyLabel/colors/font_shadow_color = Color(1, 1, 1, 0.25)
MoneyLabel/fonts/font = SubResource("font_title")
MoneyLabel/font_sizes/font_size = 30
BigMoneyLabel/base_type = &"Label"
BigMoneyLabel/colors/font_color = {ACC}
BigMoneyLabel/fonts/font = SubResource("font_title")
BigMoneyLabel/font_sizes/font_size = 72
'''
(ROOT / "theme" / OUTFILE).write_text("\n".join(out[:1]) + "\n" + "\n".join(out[1:]) + res, encoding="utf-8")
print("theme ok")
