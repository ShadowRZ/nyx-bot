from wand.drawing import Drawing
from wand.image import Image
from wand.color import Color
import os.path
import nyx_bot

TEXTBOX_PADDING_PIX = 8
TEXTBOX_INNER_MARGIN = 4
AVATAR_SIZE = 48
AVATAR_RIGHT_PADDING = 6
BORDER_MARGIN = 8
MIN_TEXTBOX_WIDTH = 256

FONT_FILE = os.path.join(nyx_bot.__path__[0], "DroidSansFallback.ttf")
MASK_FILE = os.path.join(nyx_bot.__path__[0], "mask.png")

def make_quote_image(sender: str, text: str, avatar: Image):
    draw = Drawing()
    draw.font = FONT_FILE
    draw.font_size = 15
    with Image(width=2000, height=2000) as i:
        bbox = draw.get_font_metrics(i, text, True)
        sender_bbox = draw.get_font_metrics(i, sender, False)
    text_width = max(bbox.text_width, sender_bbox.text_width)
    textbox_height = (TEXTBOX_PADDING_PIX * 2) + bbox.text_height + sender_bbox.text_height + TEXTBOX_INNER_MARGIN
    # Original textbox width
    textbox_width_orig = (TEXTBOX_PADDING_PIX * 2) + text_width
    # Final textbox width
    textbox_width = max(textbox_width_orig, MIN_TEXTBOX_WIDTH)
    # Final calculated height
    final_height = (BORDER_MARGIN * 2) + textbox_height
    width = (BORDER_MARGIN * 2) + AVATAR_SIZE + AVATAR_RIGHT_PADDING + textbox_width
    height = max(final_height, AVATAR_SIZE + (BORDER_MARGIN * 2))

    # Textbox
    textbox_x = BORDER_MARGIN + AVATAR_SIZE + AVATAR_RIGHT_PADDING
    textbox_y = BORDER_MARGIN

    # Make a mask
    with avatar.clone() as img, Image(filename=MASK_FILE) as mask:
        img.resize(AVATAR_SIZE, AVATAR_SIZE)
        img.alpha_channel = True
        img.composite_channel("default", mask, "copy_alpha", 0, 0)
        draw.composite("overlay", BORDER_MARGIN, BORDER_MARGIN, AVATAR_SIZE, AVATAR_SIZE, img)

    # Make image
    draw.fill_color = "#111111"
    draw.stroke_width = 0
    draw.rectangle(textbox_x, textbox_y, width=textbox_width, height=textbox_height, radius=8)

    # Draw text
    draw.fill_color = "#FFFFFF"
    name_x = textbox_x + TEXTBOX_PADDING_PIX
    name_y = textbox_y + TEXTBOX_PADDING_PIX + 14
    draw.text(int(name_x), int(name_y), sender)
    text_x = name_x
    text_y = name_y + TEXTBOX_INNER_MARGIN + sender_bbox.text_height
    draw.text(int(text_x), int(text_y), text)
    ret = Image(width=int(width), height=int(height))
    draw(ret)
    return ret
