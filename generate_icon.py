from PIL import Image, ImageDraw
import os

def make_icon():
    size = 256
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # Base block (dirt - brown)
    dirt = (134, 96, 67)
    dirt_dark = (101, 67, 33)
    grass_top = (106, 170, 59)
    grass_mid = (85, 140, 40)
    grass_dark = (60, 110, 25)

    # Draw isometric grass block
    # Front face (dirt)
    front = [(64, 148), (192, 148), (192, 240), (64, 240)]
    d.polygon(front, fill=dirt)
    # Shade lines on front face
    for y in range(148, 240, 8):
        d.line([(64, y), (192, y)], fill=dirt_dark, width=1)

    # Right face (dirt, darker)
    right = [(192, 148), (240, 112), (240, 204), (192, 240)]
    d.polygon(right, fill=(100, 68, 38))
    for y in range(0, 100, 8):
        d.line([(192 + y*0.5, 148 + y*0.46), (240, 112 + y*0.96)], fill=(80, 50, 20), width=1)

    # Top face (grass)
    top = [(64, 80), (192, 80), (240, 112), (112, 112)]
    d.polygon(top, fill=grass_top)
    # Grass texture dots on top
    import random
    random.seed(42)
    for _ in range(60):
        tx = random.randint(70, 225)
        ty = random.randint(82, 108)
        # Keep within parallelogram bounds (rough check)
        d.ellipse([tx, ty, tx+3, ty+3], fill=grass_dark)

    # Top face highlight edges
    d.line([(64, 80), (192, 80)], fill=grass_mid, width=2)
    d.line([(64, 80), (112, 112)], fill=grass_mid, width=2)

    # Grass overhang on front top
    grass_front = [(64, 140), (192, 140), (192, 152), (64, 152)]
    d.polygon(grass_front, fill=grass_top)
    # Grass blades
    for x in range(68, 192, 6):
        blade_h = 8 + (x % 3) * 3
        d.line([(x, 140), (x + 1, 140 - blade_h)], fill=grass_dark, width=2)

    # Grass overhang on right top
    grass_right = [(192, 140), (240, 104), (240, 116), (192, 152)]
    d.polygon(grass_right, fill=grass_mid)

    # Block outlines
    d.line([(64, 80), (192, 80)], fill=(0,0,0,180), width=2)
    d.line([(192, 80), (240, 112)], fill=(0,0,0,180), width=2)
    d.line([(64, 80), (112, 112)], fill=(0,0,0,180), width=2)
    d.line([(112, 112), (240, 112)], fill=(0,0,0,180), width=2)
    d.line([(64, 80), (64, 240)], fill=(0,0,0,180), width=2)
    d.line([(192, 80), (192, 240)], fill=(0,0,0,180), width=2)
    d.line([(240, 112), (240, 204)], fill=(0,0,0,180), width=2)
    d.line([(64, 240), (192, 240)], fill=(0,0,0,180), width=2)
    d.line([(192, 240), (240, 204)], fill=(0,0,0,180), width=2)

    # Save as .ico with multiple sizes
    sizes = [16, 32, 48, 64, 128, 256]
    icons = []
    for s in sizes:
        icons.append(img.resize((s, s), Image.NEAREST))

    out = os.path.join(os.path.dirname(__file__), "icon.ico")
    icons[0].save(out, format="ICO", sizes=[(s, s) for s in sizes],
                  append_images=icons[1:])
    print(f"Icono guardado en: {out}")

if __name__ == "__main__":
    make_icon()
