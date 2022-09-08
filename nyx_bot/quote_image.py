import logging
import os.path
from asyncio import create_subprocess_exec
from asyncio.subprocess import PIPE
from html import escape
from os import remove
from tempfile import mkstemp

from wand.drawing import Drawing
from wand.image import Image

import nyx_bot

logger = logging.getLogger(__name__)

TEXTBOX_PADDING_PIX = 8
TEXTBOX_INNER_MARGIN = 2
AVATAR_SIZE = 48
AVATAR_RIGHT_PADDING = 6
BORDER_MARGIN = 8
MIN_TEXTBOX_WIDTH = 256
MASK_FILE = os.path.join(nyx_bot.__path__[0], "mask.png")

PANGO_MARKUP_TEMPLATE = """\
<span size="larger" foreground="#1F4788" weight="bold">{}</span>
{}
"""


async def make_quote_image(sender: str, text: str, avatar: Image):
    draw = Drawing()
    imagefile = await render_text(PANGO_MARKUP_TEMPLATE.format(sender, escape(text)))
    image = Image(filename=imagefile)
    text_width = image.width
    text_height = image.height
    textbox_height = (TEXTBOX_PADDING_PIX * 2) + text_height + TEXTBOX_INNER_MARGIN - 8
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
        draw.composite(
            "overlay", BORDER_MARGIN, BORDER_MARGIN, AVATAR_SIZE, AVATAR_SIZE, img
        )

    # Make image
    draw.fill_color = "#97D4EF"
    draw.stroke_width = 0
    draw.rectangle(
        textbox_x, textbox_y, width=textbox_width, height=textbox_height, radius=8
    )

    # Draw text
    text_x = textbox_x + TEXTBOX_PADDING_PIX
    text_y = textbox_y + TEXTBOX_PADDING_PIX - 4
    with image:
        draw.composite("src_over", text_x, text_y, text_width, text_height, image)
    ret = Image(width=int(width), height=int(height))
    draw(ret)
    remove(imagefile)
    return ret


async def render_text(text: str) -> str:
    _, path = mkstemp(".png")
    logger.debug(f"File path: {path}")
    proc = await create_subprocess_exec(
        "pango-view",
        "--background=#97D4EF",
        "--foreground=black",
        "--font=Noto Sans CJK SC 16",
        "--antialias=gray",
        "--margin=0",
        "--hinting=full",
        "--width=600",
        "--wrap=word-char",
        "--markup",
        "-q",
        "-o",
        path,
        f"--text={text}",
        stdin=PIPE,
    )
    stdout, stderr = await proc.communicate(input=text.encode("utf-8"))
    if stdout:
        print(f"[stdout]\n{stdout}")
    if stderr:
        print(f"[stderr]\n{stderr}")
    return path
