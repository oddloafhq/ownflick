"""Build share images and a silent demo from real browser recordings.

Run after scripts/record_demo.mjs. Requires Pillow and ffmpeg.
"""
import argparse
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
INK = '#182437'
BLUE = '#3f5fc4'
PAPER = '#f5f3ee'


def font(size, bold=False):
    suffix = 'Bold' if bold else ''
    return ImageFont.truetype(f'/usr/share/fonts/truetype/freefont/FreeSans{suffix}.ttf', size)


def text(draw, xy, value, size, fill=INK, bold=False):
    draw.multiline_text(xy, value, font=font(size, bold), fill=fill, spacing=10)


def image_card(canvas, source, xy, width, radius=20):
    image = Image.open(source).convert('RGB')
    image = image.resize((width, round(image.height * width / image.width)), Image.Resampling.LANCZOS)
    mask = Image.new('L', image.size)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, image.width, image.height), radius, fill=255)
    canvas.paste(image, xy, mask)


def brand(canvas, xy):
    image_card(canvas, ROOT / 'brand/spooly-avatar-512.png', xy, 58, 14)
    text(ImageDraw.Draw(canvas), (xy[0] + 74, xy[1] + 8), 'OwnFlick', 38, bold=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--recordings', type=Path, default=Path('/tmp/spooly-recording'))
    parser.add_argument('--out', type=Path, default=ROOT / 'docs/promo')
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    cover = Image.new('RGB', (1280, 640), PAPER)
    draw = ImageDraw.Draw(cover)
    brand(cover, (56, 50))
    text(draw, (56, 184), 'Your media.\nWorth another look.', 48, bold=True)
    text(draw, (58, 328), 'A private feed for your\nphotos and videos.', 28)
    text(draw, (58, 460), 'SELF-HOSTED  /  OPEN SOURCE', 17, BLUE, True)
    text(draw, (58, 559), 'github.com/oddloafhq/ownflick', 20)
    image_card(cover, ROOT / 'docs/screenshots/library-desktop.jpg', (565, 95), 660)
    draw.rounded_rectangle((980, 171, 1201, 631), 30, fill=INK)
    image_card(cover, ROOT / 'docs/screenshots/flow-mobile.jpg', (988, 179), 205, 23)
    cover.save(args.out / 'social-preview.jpg', quality=92, optimize=True)

    scenes = [
        ('flow', 'Swipe through\nyour own media.', 'Photos and videos, together.\nPrivate. On your server.'),
        ('library', 'Find a memory.\nFollow a moment.', 'Browse your library\nfrom your phone.'),
        ('home', 'Rediscover what\nyou already love.', 'Start with a folder.\nMake it worth opening again.'),
    ]
    for name, heading, caption in scenes:
        background = Image.new('RGB', (1280, 720), PAPER)
        draw = ImageDraw.Draw(background)
        brand(background, (68, 55))
        text(draw, (68, 226), heading, 56, bold=True)
        text(draw, (70, 402), caption, 30)
        text(draw, (70, 591), 'SELF-HOSTED  /  OPEN SOURCE', 18, BLUE, True)
        text(draw, (70, 646), 'github.com/oddloafhq/ownflick', 23)
        draw.rounded_rectangle((894, 44, 1190, 676), 28, fill=INK)
        background_path = args.recordings / f'{name}-background.png'
        background.save(background_path)
        # Take the final eight seconds, excluding page loads and feed positioning.
        subprocess.run([
            'ffmpeg', '-y', '-loglevel', 'error', '-sseof', '-8', '-i', str(args.recordings / f'{name}.webm'),
            '-loop', '1', '-i', str(background_path), '-filter_complex',
            '[0:v]scale=280:606,setsar=1[phone];[1:v][phone]overlay=902:52:shortest=1,format=yuv420p[out]',
            '-map', '[out]', '-an', '-t', '8', '-r', '30', '-c:v', 'libx264', '-crf', '21',
            str(args.recordings / f'{name}.mp4'),
        ], check=True)
    playlist = args.recordings / 'concat.txt'
    playlist.write_text(''.join(f"file '{name}.mp4'\n" for name, _, _ in scenes))
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0',
                    '-i', str(playlist), '-c', 'copy', '-movflags', '+faststart', str(args.out / 'spooly-demo.mp4')], check=True)
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-ss', '2', '-i', str(args.out / 'spooly-demo.mp4'),
                    '-frames:v', '1', str(args.out / 'demo-poster.jpg')], check=True)


if __name__ == '__main__':
    main()
