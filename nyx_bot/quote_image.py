import logging
import os.path
from asyncio import create_subprocess_exec
from asyncio.subprocess import PIPE
from html import escape
from os import remove
from tempfile import mkstemp
from typing import Optional

from wand.drawing import Drawing
from wand.image import Image
from wand.version import MAGICK_VERSION_INFO

import nyx_bot

logger = logging.getLogger(__name__)

TEXTBOX_PADDING_PIX = 16
AVATAR_SIZE = 48
AVATAR_RIGHT_PADDING = 6
BORDER_MARGIN = 8
# MIN_TEXTBOX_WIDTH = 256
MASK_FILE = os.path.join(nyx_bot.__path__[0], "mask.png")


async def make_quote_image(
    sender: Optional[str],
    text: str,
    avatar: Optional[Image],
    formatted: bool,
    tag: Optional[str] = None,
) -> Image:
    draw = Drawing()
    draw_text = ""
    if sender:
        draw_text += (
            f"""<span size="larger" foreground="#1f4788">{escape(sender)}</span>"""
        )
        if tag:
            draw_text += (
                f"""<span size="larger" foreground="#8D94A5"> {escape(tag)}</span>"""
            )
    draw_text += "\n"
    if formatted:
        # If formatted, this message should be already formatted.
        draw_text += text
    else:
        draw_text += escape(text)
    imagefile = await render_text(draw_text)
    image = Image(filename=imagefile)
    image.trim(color="#C0E5F5")
    text_width = image.width
    text_height = image.height
    textbox_height = (TEXTBOX_PADDING_PIX * 2) + text_height
    # Textbox width
    textbox_width = (TEXTBOX_PADDING_PIX * 2) + text_width
    # Final calculated height
    final_height = (BORDER_MARGIN * 2) + textbox_height
    width = (BORDER_MARGIN * 2) + AVATAR_SIZE + AVATAR_RIGHT_PADDING + textbox_width
    height = max(final_height, AVATAR_SIZE + (BORDER_MARGIN * 2))

    # Textbox
    textbox_x = BORDER_MARGIN + AVATAR_SIZE + AVATAR_RIGHT_PADDING
    textbox_y = BORDER_MARGIN

    # Make a mask
    if avatar:
        with avatar.clone() as img, Image(filename=MASK_FILE) as mask:
            img.resize(AVATAR_SIZE, AVATAR_SIZE)
            img.alpha_channel = True
            if MAGICK_VERSION_INFO[0] == 7:
                img.composite_channel("default", mask, "copy_alpha", 0, 0)
            else:
                img.composite_channel("default", mask, "copy_opacity", 0, 0)
            draw.composite(
                "overlay", BORDER_MARGIN, BORDER_MARGIN, AVATAR_SIZE, AVATAR_SIZE, img
            )

    # Make image
    draw.fill_color = "#C0E5F5"
    draw.stroke_width = 0
    draw.rectangle(
        textbox_x, textbox_y, width=textbox_width, height=textbox_height, radius=16
    )

    # Draw text
    text_x = textbox_x + TEXTBOX_PADDING_PIX
    text_y = textbox_y + TEXTBOX_PADDING_PIX
    with image:
        draw.composite("src_over", text_x, text_y, text_width, text_height, image)
    ret = Image(width=int(width), height=int(height))
    with draw:
        draw(ret)
    remove(imagefile)
    return ret


async def render_text(text: str) -> str:
    _, path = mkstemp(".png")
    logger.debug(f"File path: {path}")
    proc = await create_subprocess_exec(
        "pango-view",
        "--background=#C0E5F5",
        "--foreground=black",
        "--font=Sarasa Gothic SC 16",
        "--antialias=gray",
        "--margin=0",
        "--hinting=full",
        "--markup",
        "--width=500",
        "--wrap=word-char",
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
