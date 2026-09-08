import json
import math
import os
import pathlib
import re
import subprocess
import sys
import textwrap
import urllib.parse

import requests
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H = 720, 1280
OUT = pathlib.Path("output")
SCENES_DIR = OUT / "scenes"
OUT.mkdir(exist_ok=True)
SCENES_DIR.mkdir(exist_ok=True)

FONT_REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

def font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()

TITLE_FONT = font(FONT_BOLD, 34)
CAPTION_FONT = font(FONT_BOLD, 54)
BODY_FONT = font(FONT_REG, 31)
SMALL_FONT = font(FONT_REG, 22)

def run(cmd):
    print("+", " ".join(str(x) for x in cmd))
    subprocess.run(cmd, check=True)

def safe_text(s):
    return re.sub(r"\s+", " ", str(s or "")).strip()

def wrap(draw, text, fnt, max_width):
    words = safe_text(text).split()
    lines, current = [], []
    for word in words:
        test = " ".join(current + [word])
        box = draw.textbbox((0,0), test, font=fnt)
        if box[2] - box[0] <= max_width or not current:
            current.append(word)
        else:
            lines.append(" ".join(current))
            current = [word]
    if current:
        lines.append(" ".join(current))
    return lines

def draw_centered(draw, lines, y, fnt, fill, spacing=10, max_lines=None):
    if max_lines:
        lines = lines[:max_lines]
    heights = []
    for line in lines:
        b = draw.textbbox((0,0), line, font=fnt)
        heights.append(b[3]-b[1])
    total = sum(heights) + spacing * max(0, len(lines)-1)
    yy = y - total/2
    for line, hh in zip(lines, heights):
        b = draw.textbbox((0,0), line, font=fnt)
        ww = b[2]-b[0]
        draw.text(((W-ww)/2, yy), line, font=fnt, fill=fill)
        yy += hh + spacing

def gradient_bg():
    im = Image.new("RGB", (W,H))
    p = im.load()
    for y in range(H):
        t = y/(H-1)
        r = int(9 + 12*t)
        g = int(14 + 10*t)
        b = int(28 + 18*t)
        for x in range(W):
            p[x,y] = (r,g,b)
    return im

def fit_crop(img, target=(W,H)):
    img = img.convert("RGB")
    tw, th = target
    ratio = max(tw/img.width, th/img.height)
    nw, nh = int(img.width*ratio), int(img.height*ratio)
    img = img.resize((nw,nh), Image.LANCZOS)
    left = (nw-tw)//2
    top = (nh-th)//2
    return img.crop((left,top,left+tw,top+th))

def fetch_nasa(query):
    if not query:
        return None, ""
    try:
        r = requests.get(
            "https://images-api.nasa.gov/search",
            params={"q": query, "media_type": "image"},
            timeout=20
        )
        r.raise_for_status()
        items = r.json().get("collection", {}).get("items", [])
        for item in items[:8]:
            links = item.get("links") or []
            href = next((x.get("href") for x in links if x.get("render") == "image"), None)
            if not href:
                continue
            ir = requests.get(href, timeout=20)
            if ir.ok and ir.content:
                tmp = OUT / "_nasa.jpg"
                tmp.write_bytes(ir.content)
                img = Image.open(tmp)
                title = ((item.get("data") or [{}])[0]).get("title", "NASA image")
                return img, f"NASA: {title}"
    except Exception as e:
        print("NASA image lookup failed:", e)
    return None, ""

def fetch_pubchem(compound):
    if not compound:
        return None, ""
    try:
        encoded = urllib.parse.quote(compound, safe="")
        url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{encoded}/PNG"
        r = requests.get(url, params={"image_size":"large"}, timeout=20)
        if r.ok and r.content:
            tmp = OUT / "_pubchem.png"
            tmp.write_bytes(r.content)
            return Image.open(tmp).convert("RGBA"), f"PubChem: {compound}"
    except Exception as e:
        print("PubChem lookup failed:", e)
    return None, ""

def spectrum_panel(canvas, draw, y0=350, y1=610):
    x0, x1 = 70, W-70
    colors = [
        (110,50,180),(70,90,220),(40,150,230),(45,200,150),
        (220,215,60),(245,145,40),(220,55,45)
    ]
    seg = (x1-x0)/len(colors)
    for i,c in enumerate(colors):
        xa = int(x0+i*seg)
        xb = int(x0+(i+1)*seg)+1
        draw.rectangle([xa,y0,xb,y1], fill=c)
    # subtle absorption-style lines
    for frac in [0.14,0.29,0.47,0.68,0.83]:
        x = int(x0 + frac*(x1-x0))
        draw.rectangle([x-3,y0,x+3,y1], fill=(15,15,20))
    draw.rounded_rectangle([x0-8,y0-8,x1+8,y1+8], radius=18, outline=(235,235,240), width=3)

def generic_diagram(draw, instruction):
    boxes = [
        (90,350,630,500),
        (90,565,630,715),
        (90,780,630,930)
    ]
    snippets = re.split(r"[.;→]+", safe_text(instruction))
    snippets = [x.strip() for x in snippets if x.strip()]
    while len(snippets) < 3:
        snippets.append(["LIGHT","SPECTRUM","MEASUREMENT"][len(snippets)])
    for i, box in enumerate(boxes):
        draw.rounded_rectangle(box, radius=28, fill=(28,37,68), outline=(120,155,230), width=3)
        lines = wrap(draw, snippets[i], BODY_FONT, box[2]-box[0]-45)
        yy = (box[1]+box[3])//2
        draw_centered(draw, lines, yy, BODY_FONT, (245,247,250), max_lines=3)
        if i < 2:
            x = W//2
            y1 = box[3]+15
            y2 = boxes[i+1][1]-15
            draw.line([x,y1,x,y2], fill=(220,225,235), width=5)
            draw.polygon([(x,y2),(x-12,y2-20),(x+12,y2-20)], fill=(220,225,235))

def add_header_footer(canvas, title, caption, source_note=""):
    draw = ImageDraw.Draw(canvas)
    # Header
    header_lines = wrap(draw, title, TITLE_FONT, W-80)
    yy = 72
    for line in header_lines[:2]:
        b = draw.textbbox((0,0), line, font=TITLE_FONT)
        draw.text(((W-(b[2]-b[0]))/2, yy), line, font=TITLE_FONT, fill=(238,241,250))
        yy += 43

    # Caption safe-area card
    cap = safe_text(caption).upper()
    if cap:
        lines = wrap(draw, cap, CAPTION_FONT, W-100)
        box_top = 1010
        draw.rounded_rectangle([38, box_top, W-38, 1200], radius=30, fill=(8,10,18))
        draw_centered(draw, lines, 1105, CAPTION_FONT, (255,255,255), spacing=8, max_lines=3)

    if source_note:
        note = safe_text(source_note)[:90]
        draw.text((28,1240), note, font=SMALL_FONT, fill=(175,185,205))
    return canvas

def render_scene(scene, title, idx):
    visual_type = safe_text(scene.get("visual_type")).lower()
    instruction = safe_text(scene.get("visual_instruction"))
    query = safe_text(scene.get("asset_query"))
    caption = safe_text(scene.get("caption"))
    source_note = ""

    canvas = gradient_bg()
    draw = ImageDraw.Draw(canvas)

    if visual_type == "astronomy_image":
        img, source_note = fetch_nasa(query or instruction)
        if img is not None:
            bg = fit_crop(img)
            bg = bg.filter(ImageFilter.GaussianBlur(radius=0.4))
            overlay = Image.new("RGBA",(W,H),(4,7,15,80))
            canvas = Image.alpha_composite(bg.convert("RGBA"), overlay).convert("RGB")
            draw = ImageDraw.Draw(canvas)
        else:
            # stylized stars
            for i in range(90):
                x = (i*83 + 37) % W
                y = (i*137 + 61) % 970
                r = 1 + (i % 4)
                draw.ellipse([x-r,y-r,x+r,y+r], fill=(220,225,245))
    elif visual_type == "molecule":
        mol, source_note = fetch_pubchem(query or instruction)
        if mol is not None:
            # White card for structure
            card = Image.new("RGB",(590,620),(248,248,248))
            mol.thumbnail((540,560), Image.LANCZOS)
            if mol.mode == "RGBA":
                card.paste(mol, ((590-mol.width)//2,(620-mol.height)//2), mol)
            else:
                card.paste(mol, ((590-mol.width)//2,(620-mol.height)//2))
            canvas.paste(card,(65,300))
            draw = ImageDraw.Draw(canvas)
        else:
            generic_diagram(draw, instruction)
    elif visual_type == "spectrum":
        spectrum_panel(canvas, draw)
        lines = wrap(draw, instruction, BODY_FONT, W-100)
        draw_centered(draw, lines, 760, BODY_FONT, (235,240,248), max_lines=4)
    elif visual_type in {"diagram","chart","icon_animation","text_animation","other",""}:
        generic_diagram(draw, instruction)
    else:
        generic_diagram(draw, instruction)

    return add_header_footer(canvas, title, caption, source_note)

def ffprobe_duration(path):
    p = subprocess.run(
        ["ffprobe","-v","error","-show_entries","format=duration","-of","default=noprint_wrappers=1:nokey=1",str(path)],
        check=True, capture_output=True, text=True
    )
    return float(p.stdout.strip())

def atempo_chain(factor):
    # atempo accepts 0.5 to 2.0 per filter
    vals = []
    f = factor
    while f > 2.0:
        vals.append(2.0); f /= 2.0
    while f < 0.5:
        vals.append(0.5); f /= 0.5
    vals.append(f)
    return ",".join(f"atempo={v:.6f}" for v in vals)

def main():
    payload_path = pathlib.Path(sys.argv[1] if len(sys.argv)>1 else "payload.json")
    payload = json.loads(payload_path.read_text(encoding="utf-8"))

    title = safe_text(payload.get("title") or "Science Short")
    narration = safe_text(payload.get("narration"))
    scenes = payload.get("scenes") or []
    target = float(payload.get("target_duration_seconds") or 45)

    if not scenes:
        raise RuntimeError("Payload contains no scenes.")
    if not narration:
        narration = "This science Short was generated automatically from a verified storyboard."

    # Normalize scene timing if needed.
    durations = []
    for i, s in enumerate(scenes):
        start = float(s.get("start_sec") or 0)
        end = float(s.get("end_sec") or 0)
        dur = max(1.5, end-start)
        durations.append(dur)

        frame = render_scene(s, title, i+1)
        frame.save(SCENES_DIR / f"scene_{i+1:02d}.jpg", quality=92)

    # Build concat list.
    concat = OUT / "concat.txt"
    lines = []
    for i, dur in enumerate(durations):
        p = (SCENES_DIR / f"scene_{i+1:02d}.jpg").resolve()
        lines.append(f"file '{p}'")
        lines.append(f"duration {dur:.3f}")
    # ffmpeg concat demuxer needs last image repeated.
    last = (SCENES_DIR / f"scene_{len(scenes):02d}.jpg").resolve()
    lines.append(f"file '{last}'")
    concat.write_text("\n".join(lines), encoding="utf-8")

    silent = OUT / "silent.mp4"
    run([
        "ffmpeg","-y","-f","concat","-safe","0","-i",str(concat),
        "-vf",f"scale={W}:{H},format=yuv420p",
        "-r","24","-c:v","libx264","-preset","veryfast","-crf","22",
        str(silent)
    ])

    # Generate a completely free prototype narration with espeak-ng.
    narration_txt = OUT / "narration.txt"
    narration_txt.write_text(narration, encoding="utf-8")
    wav = OUT / "narration_raw.wav"
    run([
        "espeak-ng","-v","en-us","-s","165","-w",str(wav),
        "-f",str(narration_txt)
    ])

    video_dur = ffprobe_duration(silent)
    audio_dur = ffprobe_duration(wav)
    factor = audio_dur / max(video_dur, 0.1)
    afilter = atempo_chain(factor)

    final = OUT / "science_short.mp4"
    run([
        "ffmpeg","-y",
        "-i",str(silent),"-i",str(wav),
        "-filter:a",afilter,
        "-c:v","copy","-c:a","aac","-b:a","160k",
        "-shortest",str(final)
    ])

    metadata = {
        "job_id": payload.get("job_id"),
        "title": title,
        "verified_sources": payload.get("verified_sources") or [],
        "target_duration_seconds": target,
        "rendered_duration_seconds": ffprobe_duration(final),
        "scene_count": len(scenes),
        "voice_engine": "espeak-ng prototype",
        "video_file": "science_short.mp4"
    }
    (OUT / "render_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    (OUT / "source_manifest.json").write_text(
        json.dumps({
            "verified_sources": payload.get("verified_sources") or [],
            "scenes": scenes
        }, indent=2),
        encoding="utf-8"
    )
    print(json.dumps(metadata, indent=2))

if __name__ == "__main__":
    main()
