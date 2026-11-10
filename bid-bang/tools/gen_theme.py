"""Écrit theme/main_theme.tres (style réaliste : bois sombre, or, velours). Usage : python tools/gen_theme.py"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
M = 30  # marge 9-patch des textures (voir gen_ui_textures.py)
TEX = ["btn_normal", "btn_hover", "btn_pressed", "btn_disabled", "primary_normal", "primary_hover",
       "primary_pressed", "danger_normal", "danger_pressed", "card", "hero", "chip_money", "field", "field_focus"]

out = ['[gd_resource type="Theme" format=3]\n']
for t in TEX:
    out.append(f'[ext_resource type="Texture2D" path="res://assets/ui_real/{t}.png" id="t_{t}"]')
out += ['[ext_resource type="FontFile" path="res://assets/fonts/Lato-Regular.ttf" id="font"]',
        '[ext_resource type="FontFile" path="res://assets/fonts/Lato-Bold.ttf" id="font_bold"]',
        '[ext_resource type="FontFile" path="res://assets/fonts/Cinzel.ttf" id="font_title"]', '']


def box(id_, tex, content, extra=""):
    l, t, r, b = content
    return (f'[sub_resource type="StyleBoxTexture" id="{id_}"]\ntexture = ExtResource("t_{tex}")\n'
            f'texture_margin_left = {M}.0\ntexture_margin_top = {M}.0\ntexture_margin_right = {M}.0\ntexture_margin_bottom = {M}.0\n'
            f'content_margin_left = {l}.0\ncontent_margin_top = {t}.0\ncontent_margin_right = {r}.0\ncontent_margin_bottom = {b}.0\n{extra}\n')


BTN = (34, 20, 34, 24)
PRI = (40, 24, 40, 28)
out.append(box("btn_normal", "btn_normal", BTN))
out.append(box("btn_hover", "btn_hover", BTN))
out.append(box("btn_pressed", "btn_pressed", (34, 24, 34, 20)))
out.append(box("btn_disabled", "btn_disabled", BTN))
out.append(box("primary_normal", "primary_normal", PRI))
out.append(box("primary_hover", "primary_hover", PRI))
out.append(box("primary_pressed", "primary_pressed", (40, 28, 40, 24)))
out.append(box("danger_normal", "danger_normal", BTN))
out.append(box("danger_pressed", "danger_pressed", (34, 24, 34, 20)))
out.append(box("card", "card", (34, 28, 34, 32)))
out.append(box("hero", "hero", (38, 30, 38, 34)))
out.append(box("chip", "btn_normal", (26, 14, 26, 18)))
out.append(box("chip_money", "chip_money", (28, 14, 28, 18)))
out.append(box("field", "field", (26, 18, 26, 20)))
out.append(box("field_focus", "field_focus", (26, 18, 26, 20)))
out.append(box("popup", "card", (22, 20, 22, 22)))
out.append(box("popup_hover", "btn_hover", (16, 8, 16, 10)))
out.append('''[sub_resource type="StyleBoxEmpty" id="back_normal"]
content_margin_left = 8.0
content_margin_top = 8.0
content_margin_right = 8.0
content_margin_bottom = 8.0

[sub_resource type="StyleBoxFlat" id="bar_bg"]
bg_color = Color(0.05, 0.03, 0.03, 0.9)
corner_radius_top_left = 8
corner_radius_top_right = 8
corner_radius_bottom_right = 8
corner_radius_bottom_left = 8
border_width_left = 2
border_width_top = 2
border_width_right = 2
border_width_bottom = 2
border_color = Color(0.55, 0.42, 0.2, 1)

[sub_resource type="StyleBoxFlat" id="bar_fill"]
bg_color = Color(0.95, 0.78, 0.35, 1)
corner_radius_top_left = 6
corner_radius_top_right = 6
corner_radius_bottom_right = 6
corner_radius_bottom_left = 6

[resource]''')
IVORY = "Color(0.96, 0.93, 0.86, 1)"
res = f'''default_font = ExtResource("font")
default_font_size = 28
Label/colors/font_color = {IVORY}
Label/colors/font_shadow_color = Color(0, 0, 0, 0.6)
Label/constants/shadow_offset_x = 0
Label/constants/shadow_offset_y = 2
Button/colors/font_color = {IVORY}
Button/colors/font_hover_color = Color(1, 0.97, 0.88, 1)
Button/colors/font_pressed_color = Color(0.85, 0.8, 0.7, 1)
Button/colors/font_disabled_color = Color(0.55, 0.5, 0.45, 1)
Button/fonts/font = ExtResource("font_bold")
Button/font_sizes/font_size = 28
Button/styles/normal = SubResource("btn_normal")
Button/styles/hover = SubResource("btn_hover")
Button/styles/pressed = SubResource("btn_pressed")
Button/styles/disabled = SubResource("btn_disabled")
Button/styles/focus = SubResource("back_normal")
LineEdit/colors/font_color = {IVORY}
LineEdit/colors/caret_color = Color(1, 0.82, 0.4, 1)
LineEdit/colors/selection_color = Color(0.9, 0.68, 0.25, 0.5)
LineEdit/colors/font_placeholder_color = Color(0.6, 0.54, 0.48, 1)
LineEdit/constants/caret_width = 3
LineEdit/font_sizes/font_size = 28
LineEdit/styles/normal = SubResource("field")
LineEdit/styles/focus = SubResource("field_focus")
OptionButton/styles/normal = SubResource("btn_normal")
OptionButton/styles/hover = SubResource("btn_hover")
OptionButton/styles/pressed = SubResource("btn_pressed")
OptionButton/styles/focus = SubResource("back_normal")
OptionButton/colors/font_color = {IVORY}
OptionButton/fonts/font = ExtResource("font_bold")
OptionButton/font_sizes/font_size = 28
PopupMenu/styles/panel = SubResource("popup")
PopupMenu/styles/hover = SubResource("popup_hover")
PopupMenu/colors/font_color = {IVORY}
PopupMenu/colors/font_hover_color = Color(1, 1, 1, 1)
PopupMenu/font_sizes/font_size = 28
PanelContainer/styles/panel = SubResource("card")
HeroPanel/base_type = &"PanelContainer"
HeroPanel/styles/panel = SubResource("hero")
ChipPanel/base_type = &"PanelContainer"
ChipPanel/styles/panel = SubResource("chip")
MoneyChip/base_type = &"PanelContainer"
MoneyChip/styles/panel = SubResource("chip_money")
ProgressBar/styles/background = SubResource("bar_bg")
ProgressBar/styles/fill = SubResource("bar_fill")
PrimaryButton/base_type = &"Button"
PrimaryButton/colors/font_color = Color(0.22, 0.12, 0.04, 1)
PrimaryButton/colors/font_hover_color = Color(0.18, 0.09, 0.02, 1)
PrimaryButton/colors/font_pressed_color = Color(0.22, 0.12, 0.04, 1)
PrimaryButton/colors/font_disabled_color = Color(0.5, 0.4, 0.3, 1)
PrimaryButton/font_sizes/font_size = 34
PrimaryButton/styles/normal = SubResource("primary_normal")
PrimaryButton/styles/hover = SubResource("primary_hover")
PrimaryButton/styles/pressed = SubResource("primary_pressed")
DangerButton/base_type = &"Button"
DangerButton/colors/font_color = Color(1, 0.92, 0.88, 1)
DangerButton/styles/normal = SubResource("danger_normal")
DangerButton/styles/hover = SubResource("danger_normal")
DangerButton/styles/pressed = SubResource("danger_pressed")
BackButton/base_type = &"Button"
BackButton/colors/font_color = Color(0.9, 0.78, 0.55, 1)
BackButton/styles/normal = SubResource("back_normal")
BackButton/styles/hover = SubResource("back_normal")
BackButton/styles/pressed = SubResource("back_normal")
TitleLabel/base_type = &"Label"
TitleLabel/colors/font_color = Color(0.96, 0.8, 0.4, 1)
TitleLabel/colors/font_shadow_color = Color(0, 0, 0, 0.75)
TitleLabel/constants/shadow_offset_y = 4
TitleLabel/fonts/font = ExtResource("font_title")
TitleLabel/font_sizes/font_size = 80
HeadingLabel/base_type = &"Label"
HeadingLabel/fonts/font = ExtResource("font_bold")
HeadingLabel/font_sizes/font_size = 36
MutedLabel/base_type = &"Label"
MutedLabel/colors/font_color = Color(0.78, 0.72, 0.64, 1)
MutedLabel/font_sizes/font_size = 24
ErrorLabel/base_type = &"Label"
ErrorLabel/colors/font_color = Color(1, 0.52, 0.47, 1)
InfoLabel/base_type = &"Label"
InfoLabel/colors/font_color = Color(0.65, 0.92, 0.6, 1)
FieldLabel/base_type = &"Label"
FieldLabel/colors/font_color = Color(0.95, 0.8, 0.5, 1)
FieldLabel/fonts/font = ExtResource("font_bold")
FieldLabel/font_sizes/font_size = 24
MoneyLabel/base_type = &"Label"
MoneyLabel/colors/font_color = Color(0.7, 0.98, 0.8, 1)
MoneyLabel/fonts/font = ExtResource("font_bold")
MoneyLabel/font_sizes/font_size = 32
BigMoneyLabel/base_type = &"Label"
BigMoneyLabel/colors/font_color = Color(1, 0.83, 0.4, 1)
BigMoneyLabel/fonts/font = ExtResource("font_bold")
BigMoneyLabel/font_sizes/font_size = 64
'''
(ROOT / "theme" / "main_theme.tres").write_text("\n".join(out[:1]) + "\n" + "\n".join(out[1:]) + res, encoding="utf-8")
print("theme ok")
