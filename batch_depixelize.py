# batch_stylized_vectorize_mt_alpha_green.py
import os
import numpy as np
from PIL import Image
import xbrz
from autotrace import Bitmap
from autotrace import VectorFormat
from concurrent.futures import ThreadPoolExecutor
import xml.etree.ElementTree as ET
from wand.image import Image as WandImage

UPSCALE = 4
MAX_WORKERS = 4
OUTDIR = "depixelOutputs"
PNG_SIZE = (256, 256)

GREENSCREEN_RGB = (0, 255, 0)

def preprocess_image(im):
    """Upscale and mark alpha=0 pixels as green screen"""
    im = im.convert("RGBA")
    arr = np.array(im)
    # replace fully transparent pixels with GREENSCREEN_RGB
    mask = arr[..., 3] == 0
    arr[mask, :3] = GREENSCREEN_RGB
    arr[mask, 3] = 255  # make them opaque for autotrace
    im2 = Image.fromarray(arr, mode="RGBA")
    up = xbrz.scale_pillow(im2, UPSCALE)
    return up  # RGBA

def remove_greenscreen_from_svg(svg_path):
    tree = ET.parse(svg_path)
    root = tree.getroot()
    ns = {'svg': 'http://www.w3.org/2000/svg'}

    def is_greenscreen(color):
        color = color.lower()
        return color in ('#00ff00', 'rgb(0,255,0)', 'green')

    # remove rects with green fill
    for rect in root.findall('.//svg:rect', ns):
        fill = rect.attrib.get('fill', '').lower()
        if is_greenscreen(fill):
            root.remove(rect)

    # remove paths with green fill in style
    for path in root.findall('.//svg:path', ns):
        style = path.attrib.get('style', '').lower()
        if 'fill:#00ff00' in style or 'fill:rgb(0,255,0)' in style:
            root.remove(path)

    tree.write(svg_path, encoding='utf-8', xml_declaration=True)

def svg_to_png(svg_path, png_path):
    with WandImage(filename=svg_path, background='transparent') as img:
        img.format = 'png'
        img.resize(*PNG_SIZE)
        img.save(filename=png_path)

def process_file(in_path):
    fname = os.path.basename(in_path)
    print(f"processing {fname} …")

    im = Image.open(in_path)
    stylized = preprocess_image(im)
    arr = np.asarray(stylized)
    bmp = Bitmap(arr[...,:3])  # RGB only for tracing
    vec = bmp.trace()

    out_svg_path = os.path.join(OUTDIR, os.path.splitext(fname)[0] + ".svg")
    vec.save(out_svg_path)

    remove_greenscreen_from_svg(out_svg_path)

    out_png_dir = os.path.join(OUTDIR, "png")
    os.makedirs(out_png_dir, exist_ok=True)
    out_png_path = os.path.join(out_png_dir, os.path.splitext(fname)[0] + ".png")
    svg_to_png(out_svg_path, out_png_path)

    print(f"done {fname}")

def main():
    cwd = os.getcwd()
    outdir_path = os.path.join(cwd, OUTDIR)
    os.makedirs(outdir_path, exist_ok=True)

    png_files = [os.path.join(cwd, f) for f in os.listdir(cwd) if f.lower().endswith(".png")]

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(process_file, f) for f in png_files]
        for future in futures:
            future.result()

if __name__ == "__main__":
    main()
