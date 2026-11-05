#!/usr/bin/env python3

import argparse
from array import array
import math
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import turtle as t
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageStat, ImageTk

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
except ImportError:
    DND_FILES = None
    TkinterDnD = None


PROCESSING_PRESETS = {
    "balanced": {
        "label": "General",
        "detail": 80,
        "variation_threshold": 22,
        "background_threshold": 64,
        "suppress_grid": False,
    },
    "photo": {
        "label": "Photograph",
        "detail": 120,
        "variation_threshold": 18,
        "background_threshold": 64,
        "suppress_grid": False,
    },
    "illustration": {
        "label": "Illustration / cartoon",
        "detail": 100,
        "variation_threshold": 22,
        "background_threshold": 64,
        "suppress_grid": False,
    },
    "pixel-art": {
        "label": "Pixel art / sprite",
        "detail": 80,
        "variation_threshold": 24,
        "background_threshold": 64,
        "suppress_grid": False,
    },
    "grid-drawing": {
        "label": "Grid-paper drawing",
        "detail": 100,
        "variation_threshold": 22,
        "background_threshold": 96,
        "suppress_grid": True,
    },
    "line-art": {
        "label": "Line art / logo",
        "detail": 110,
        "variation_threshold": 18,
        "background_threshold": 64,
        "suppress_grid": False,
    },
}
PRESET_LABELS = {
    settings["label"]: preset for preset, settings in PROCESSING_PRESETS.items()
}


def parse_args():
    parser = argparse.ArgumentParser(
        description="Convert an image into large pixel-art using Turtle graphics."
    )
    parser.add_argument(
        "image",
        nargs="?",
        help="Path to the source image file. If omitted, open the image uploader.",
    )
    parser.add_argument(
        "--pixel-size",
        type=int,
        default=None,
        help="Render each source pixel as this many turtle units. Defaults to the largest size that fits the window.",
    )
    parser.add_argument(
        "--scale",
        type=float,
        default=None,
        help="Scale factor applied to the image before rendering. Example: 0.5 halves the pixel count, 2 doubles it.",
    )
    parser.add_argument(
        "--detail",
        type=int,
        default=None,
        help="Maximum detail along the image's longest side (defaults to the preset).",
    )
    parser.add_argument(
        "--preset",
        choices=tuple(PROCESSING_PRESETS),
        default="balanced",
        help="Processing preset for the source image style.",
    )
    parser.add_argument(
        "--colors",
        type=int,
        default=None,
        help="Override the automatically selected palette size (2-256 colors).",
    )
    parser.add_argument(
        "--margin",
        type=int,
        default=0,
        help="Margin in pixels around the image inside the window.",
    )
    parser.add_argument(
        "--background",
        default="black",
        help="Background color for the turtle window.",
    )
    parser.add_argument(
        "--title",
        default="Pixel Art Generator",
        help="Window title.",
    )
    parser.add_argument(
        "--fast",
        action="store_true",
        help="Disable animation for faster drawing.",
    )
    return parser.parse_args()


def load_image(path):
    with Image.open(path) as source:
        return source.convert("RGBA")


def compute_render_size(image_width, image_height, margin, screen_width, screen_height):
    usable_width = max(1, screen_width - margin * 2)
    usable_height = max(1, screen_height - margin * 2)
    pixel_size = min(usable_width / image_width, usable_height / image_height)
    return max(1, math.floor(pixel_size))


def rgb_to_hex(rgb):
    red, green, blue = rgb
    return f"#{red:02x}{green:02x}{blue:02x}"


def representative_region_color(region, edge_strength=0):
    pixel_data = region.convert("RGBA").tobytes()
    totals = {}
    channel_totals = [0, 0, 0]
    visible_count = 0
    alpha_total = 0

    for offset in range(0, len(pixel_data), 4):
        red, green, blue, alpha = pixel_data[offset : offset + 4]
        if alpha == 0:
            continue

        visible_count += 1
        channel_totals[0] += red
        channel_totals[1] += green
        channel_totals[2] += blue
        alpha_total += alpha
        color_bin = (red >> 3, green >> 3, blue >> 3)
        color_totals = totals.setdefault(color_bin, [0, 0, 0, 0, 0])
        color_totals[0] += 1
        color_totals[1] += red
        color_totals[2] += green
        color_totals[3] += blue
        color_totals[4] += alpha

    if visible_count == 0:
        return (0, 0, 0, 0)

    dominant_bin = max(totals, key=lambda color_bin: totals[color_bin][0])
    color_totals = totals[dominant_bin]
    dominant_count = color_totals[0]
    dominant_fraction = dominant_count / visible_count
    mode_weight = (
        1.0
        if edge_strength >= 12 and dominant_fraction < 0.9
        else min(
            0.9,
            0.35 + 0.5 * (1 - dominant_fraction) + min(0.15, edge_strength / 255),
        )
    )
    mean_color = [value / visible_count for value in channel_totals]
    mode_color = [value / dominant_count for value in color_totals[1:4]]
    mixed_rgb = tuple(
        round(mean * (1 - mode_weight) + mode * mode_weight)
        for mean, mode in zip(mean_color, mode_color)
    )
    average_alpha = round(alpha_total / region.width / region.height)
    return (*mixed_rgb, average_alpha)


def adaptive_blocks(
    image,
    max_detail,
    variation_threshold=22,
    suppress_grid=False,
):
    if max_detail < 1:
        raise ValueError("Detail must be at least 1.")

    if max(image.size) > 512:
        image = image.copy()
        image.thumbnail((512, 512), Image.Resampling.LANCZOS)

    if suppress_grid:
        image = image.filter(ImageFilter.MedianFilter(size=3))

    base_size = max(image.size) / max_detail
    max_block_size = base_size * 1.75
    edge_map = image.convert("L").filter(ImageFilter.FIND_EDGES)
    gray_pixels = image.convert("L").tobytes()
    blocks = []

    def find_edge_cut(start, end, cross_start, cross_end, vertical):
        gap = max(1, int(base_size * 0.35))
        if end - start <= gap * 2 + 1:
            return None
        sample_step = max(1, (cross_end - cross_start) // 128)
        best_score = 0
        best_position = None
        for position in range(start + gap, end - gap + 1):
            total = 0
            samples = 0
            for cross in range(cross_start, cross_end, sample_step):
                if vertical:
                    first = gray_pixels[cross * image.width + position - 1]
                    second = gray_pixels[cross * image.width + position]
                else:
                    first = gray_pixels[(position - 1) * image.width + cross]
                    second = gray_pixels[position * image.width + cross]
                total += abs(second - first)
                samples += 1
            score = total / samples
            if score > best_score:
                best_score = score
                best_position = position
        return best_position if best_score >= 12 else None

    def split_region(left, top, right, bottom):
        region = image.crop((left, top, right, bottom))
        edge_strength = ImageStat.Stat(
            edge_map.crop((left, top, right, bottom))
        ).mean[0]
        representative_color = representative_region_color(region, edge_strength)
        standard_deviation = ImageStat.Stat(region.convert("RGB")).stddev
        variation = math.sqrt(sum(value * value for value in standard_deviation) / 3)

        split_x = right - left > base_size
        split_y = bottom - top > base_size
        exceeds_block_limit = (
            right - left > max_block_size or bottom - top > max_block_size
        )
        significant_edge = edge_strength >= 12
        needs_detail = variation > variation_threshold or significant_edge
        if not exceeds_block_limit and (not needs_detail or not (split_x or split_y)):
            blocks.append((left, top, right, bottom, representative_color))
            return

        cut_x = (
            find_edge_cut(left, right, top, bottom, True) if split_x else None
        )
        cut_y = (
            find_edge_cut(top, bottom, left, right, False) if split_y else None
        )
        x_parts = (
            (left, cut_x or (left + right) // 2, right)
            if split_x
            else (left, right)
        )
        y_parts = (
            (top, cut_y or (top + bottom) // 2, bottom)
            if split_y
            else (top, bottom)
        )
        for y_index in range(len(y_parts) - 1):
            for x_index in range(len(x_parts) - 1):
                split_region(
                    x_parts[x_index],
                    y_parts[y_index],
                    x_parts[x_index + 1],
                    y_parts[y_index + 1],
                )

    split_region(0, 0, image.width, image.height)
    return image, blocks


def make_palette(image, color_count):
    return image.convert("RGB").quantize(
        colors=color_count,
        method=Image.Quantize.MEDIANCUT,
    )


def quantize_image(image, color_count, palette_source=None):
    image = image.convert("RGBA")
    alpha = image.getchannel("A")
    source = image if palette_source is None else palette_source
    palette = make_palette(source, color_count)
    quantized = image.convert("RGB").quantize(
        palette=palette,
        dither=Image.Dither.NONE,
    )
    result = quantized.convert("RGB").convert("RGBA")
    result.putalpha(alpha)
    return result


def palette_error(original, quantized):
    difference = ImageChops.difference(
        original.convert("RGB"), quantized.convert("RGB")
    )
    channel_rms = ImageStat.Stat(difference).rms
    return math.sqrt(sum(error * error for error in channel_rms) / 3)


def choose_palette_size(image, palette_source=None, target_error=8):
    candidate_sizes = (2, 4, 6, 8, 12, 16, 24, 32, 48, 64)
    evaluation_image = image if palette_source is None else palette_source
    for color_count in candidate_sizes:
        quantized = quantize_image(
            evaluation_image, color_count, palette_source
        )
        if palette_error(evaluation_image, quantized) <= target_error:
            return color_count
    return candidate_sizes[-1]


def apply_automatic_palette(image, color_count=None, palette_source=None):
    if color_count is None:
        color_count = choose_palette_size(image, palette_source)
    if not 2 <= color_count <= 256:
        raise ValueError("Color count must be between 2 and 256.")
    return quantize_image(image, color_count, palette_source)


def snap_near_black(image, threshold=24):
    pixels = image.load()
    for y in range(image.height):
        for x in range(image.width):
            red, green, blue, alpha = pixels[x, y]
            brightness = 0.2126 * red + 0.7152 * green + 0.0722 * blue
            if alpha and brightness <= threshold:
                pixels[x, y] = (0, 0, 0, alpha)
    return image


def estimate_border_color(image):
    border_pixels = []
    for x in range(image.width):
        border_pixels.append(image.getpixel((x, 0)))
        if image.height > 1:
            border_pixels.append(image.getpixel((x, image.height - 1)))
    for y in range(1, image.height - 1):
        border_pixels.append(image.getpixel((0, y)))
        if image.width > 1:
            border_pixels.append(image.getpixel((image.width - 1, y)))

    bins = {}
    for red, green, blue, alpha in border_pixels:
        if alpha == 0:
            continue
        key = (red >> 3, green >> 3, blue >> 3)
        totals = bins.setdefault(key, [0, 0, 0, 0])
        totals[0] += 1
        totals[1] += red
        totals[2] += green
        totals[3] += blue

    if not bins:
        return None
    count, red, green, blue = max(bins.values(), key=lambda values: values[0])
    return (round(red / count), round(green / count), round(blue / count))


def snap_image_to_background(image, background_color, threshold=64):
    if background_color is None:
        return image

    image = image.copy()
    pixels = image.load()
    for y in range(image.height):
        for x in range(image.width):
            red, green, blue, alpha = pixels[x, y]
            if alpha and color_distance((red, green, blue), background_color) <= threshold:
                pixels[x, y] = (*background_color, alpha)
    return image


def color_distance(first, second):
    return math.sqrt(sum((first[index] - second[index]) ** 2 for index in range(3)))


def snap_to_background(blocks, background_color, threshold=36):
    if background_color is None:
        return blocks

    adjusted = []
    for left, top, right, bottom, color in blocks:
        if color[3] and color_distance(color, background_color) <= threshold:
            color = (*background_color, color[3])
        adjusted.append((left, top, right, bottom, color))
    return adjusted


def remove_isolated_color_specks(blocks, image_size, max_detail):
    width, height = image_size
    base_size = max(image_size) / max_detail
    max_area = max(2, base_size * base_size * 0.2)
    block_map = array("i", [-1]) * (width * height)
    for index, (left, top, right, bottom, _) in enumerate(blocks):
        row = array("i", [index]) * (right - left)
        for y in range(top, bottom):
            start = y * width + left
            block_map[start : start + right - left] = row

    adjusted = list(blocks)
    for index, (left, top, right, bottom, color) in enumerate(blocks):
        area = (right - left) * (bottom - top)
        luminance = 0.2126 * color[0] + 0.7152 * color[1] + 0.0722 * color[2]
        if area > max_area or luminance < 32:
            continue

        boundary_colors = {}

        def count_neighbor(neighbor_index):
            if neighbor_index < 0 or neighbor_index == index:
                return
            neighbor_color = blocks[neighbor_index][4]
            if neighbor_color[3] == 0:
                return
            boundary_colors[neighbor_color[:3]] = (
                boundary_colors.get(neighbor_color[:3], 0) + 1
            )

        if left > 0:
            for y in range(top, bottom):
                count_neighbor(block_map[y * width + left - 1])
        if right < width:
            for y in range(top, bottom):
                count_neighbor(block_map[y * width + right])
        if top > 0:
            for x in range(left, right):
                count_neighbor(block_map[(top - 1) * width + x])
        if bottom < height:
            for x in range(left, right):
                count_neighbor(block_map[bottom * width + x])

        if not boundary_colors:
            continue
        replacement, shared_edge = max(
            boundary_colors.items(), key=lambda item: item[1]
        )
        total_edge = sum(boundary_colors.values())
        if shared_edge / total_edge < 0.75:
            continue
        if color_distance(color, replacement) > 45:
            continue
        adjusted[index] = (left, top, right, bottom, (*replacement, color[3]))

    return adjusted


def draw_block(pen, width, height, color):
    color_code = rgb_to_hex(color)
    pen.color(color_code, color_code)
    pen.pensize(1)
    pen.begin_fill()
    pen.forward(width + 1)
    pen.left(90)
    pen.forward(height + 1)
    pen.left(90)
    pen.forward(width + 1)
    pen.left(90)
    pen.forward(height + 1)
    pen.left(90)
    pen.end_fill()


def process_pixel_art(
    image,
    detail,
    colors,
    preset,
    suppress_grid=None,
):
    if preset not in PROCESSING_PRESETS:
        raise ValueError(f"Unknown processing preset: {preset}")
    preset_settings = PROCESSING_PRESETS[preset]
    if detail is None:
        detail = preset_settings["detail"]
    if suppress_grid is None:
        suppress_grid = preset_settings["suppress_grid"]
    if image.mode != "RGBA":
        image = image.convert("RGBA")

    background_color = estimate_border_color(image)
    background_threshold = preset_settings["background_threshold"]
    if suppress_grid:
        background_threshold = max(background_threshold, 96)
    image = snap_image_to_background(
        image,
        background_color,
        threshold=background_threshold,
    )
    image, blocks = adaptive_blocks(
        image,
        detail,
        variation_threshold=preset_settings["variation_threshold"],
        suppress_grid=suppress_grid,
    )

    sample_limit = 4096
    sample_pixels = []
    total_area = image.width * image.height
    for left, top, right, bottom, color in blocks:
        weight = max(
            1,
            round((right - left) * (bottom - top) * sample_limit / total_area),
        )
        sample_pixels.extend([color[:3]] * weight)

    palette_source = Image.new("RGB", (len(sample_pixels), 1))
    palette_source.putdata(sample_pixels)
    block_colors = Image.new("RGBA", (len(blocks), 1))
    block_colors.putdata([block[4] for block in blocks])
    block_colors = apply_automatic_palette(block_colors, colors, palette_source)
    block_colors = snap_near_black(block_colors, threshold=20)
    blocks = [
        (*block[:4], block_colors.getpixel((index, 0)))
        for index, block in enumerate(blocks)
    ]
    blocks = snap_to_background(blocks, background_color)
    blocks = remove_isolated_color_specks(blocks, image.size, detail)

    output = Image.new("RGBA", image.size, (0, 0, 0, 0))
    output_draw = ImageDraw.Draw(output)
    for left, top, right, bottom, color in blocks:
        if color[3]:
            output_draw.rectangle(
                (left, top, right - 1, bottom - 1),
                fill=color,
            )
    return image, blocks, output


def render_pixel_art(
    image,
    pixel_size=None,
    scale=None,
    margin=40,
    background="black",
    title="Pixel Art Generator",
    fast=False,
    root=None,
    detail=None,
    colors=None,
    preset="balanced",
    suppress_grid=None,
    render_parent=None,
    processed_result=None,
):
    if preset not in PROCESSING_PRESETS:
        raise ValueError(f"Unknown processing preset: {preset}")
    if scale is not None:
        if scale <= 0:
            raise ValueError("Scale must be greater than zero.")
        new_width = max(1, int(image.width * scale))
        new_height = max(1, int(image.height * scale))
        image = image.resize((new_width, new_height), Image.Resampling.NEAREST)

    if processed_result is None:
        image, blocks, _ = process_pixel_art(
            image,
            detail,
            colors,
            preset,
            suppress_grid,
        )
    else:
        image, blocks, _ = processed_result

    if root is None:
        screen = t.Screen()
        canvas = screen.getcanvas()
    else:
        root.title(title)
        root.state("zoomed")
        root.update()
        canvas = tk.Canvas(
            render_parent if render_parent is not None else root,
            width=max(1, (render_parent or root).winfo_width()),
            height=max(1, (render_parent or root).winfo_height()),
            highlightthickness=0,
        )
        canvas.pack(fill="both", expand=True)
        root.update()
        screen = t.TurtleScreen(canvas)

    screen.bgcolor(background)
    if root is None:
        screen.title(title)
        screen.setup(width=0.95, height=0.95)
    else:
        canvas_width = canvas.winfo_width()
        canvas_height = canvas.winfo_height()
        screen.setworldcoordinates(
            -canvas_width / 2,
            -canvas_height / 2,
            canvas_width / 2,
            canvas_height / 2,
        )
    screen.tracer(0, 0)

    width = image.width
    height = image.height
    if pixel_size is None:
        if root is None:
            screen_width = screen.window_width()
            screen_height = screen.window_height()
        else:
            screen_width = canvas.winfo_width()
            screen_height = canvas.winfo_height()
        fitted_pixel_size = compute_render_size(
            width, height, margin, screen_width, screen_height
        )
        pixel_size = fitted_pixel_size
    else:
        fitted_pixel_size = compute_render_size(
            width,
            height,
            margin,
            canvas.winfo_width() if root is not None else screen.window_width(),
            canvas.winfo_height() if root is not None else screen.window_height(),
        )
        pixel_size = min(max(1, pixel_size), fitted_pixel_size)

    art_width = width * pixel_size
    art_height = height * pixel_size
    start_x = -art_width / 2
    start_y = art_height / 2

    pen = t.Turtle() if root is None else t.RawTurtle(screen)
    pen.hideturtle()
    pen.speed(0)
    pen.shape("turtle")
    if not fast:
        pen.showturtle()
    pen.penup()

    update_interval = max(1, len(blocks) // 250)
    for block_index, (left, top, right, bottom, (red, green, blue, alpha)) in enumerate(
        blocks, start=1
    ):
        if alpha == 0:
            continue

        pen.goto(start_x + left * pixel_size, start_y - bottom * pixel_size)
        draw_block(
            pen,
            (right - left) * pixel_size,
            (bottom - top) * pixel_size,
            (red, green, blue),
        )
        if not fast and block_index % update_interval == 0:
            screen.update()

    pen.hideturtle()
    screen.update()
    return screen


def launch_uploader(args):
    root_class = TkinterDnD.Tk if TkinterDnD is not None else tk.Tk
    root = root_class()
    root.title("Pixel Art Generator - Open an Image")
    root.geometry("720x700")

    content = ttk.Frame(root, padding=24)
    content.pack(fill="both", expand=True)
    ttk.Label(
        content,
        text="Turn an image into pixel art",
        font=("Segoe UI", 17, "bold"),
    ).pack(pady=(8, 16))

    preset_var = tk.StringVar(value=PROCESSING_PRESETS[args.preset]["label"])
    detail_var = tk.IntVar(
        value=args.detail
        if args.detail is not None
        else PROCESSING_PRESETS[args.preset]["detail"]
    )
    colors_var = tk.StringVar(
        value="Auto" if args.colors is None else str(args.colors)
    )
    grid_var = tk.BooleanVar(
        value=PROCESSING_PRESETS[args.preset]["suppress_grid"]
    )
    selected_image = None
    selected_path = None
    output_image = None
    preview_photo = None

    options = ttk.LabelFrame(content, text="Image style and output", padding=12)
    options.pack(fill="x", pady=(0, 12))

    ttk.Label(options, text="Input style").grid(row=0, column=0, sticky="w", pady=4)
    preset_box = ttk.Combobox(
        options,
        textvariable=preset_var,
        values=tuple(PRESET_LABELS),
        state="readonly",
    )
    preset_box.grid(row=0, column=1, sticky="ew", pady=4)

    ttk.Label(options, text="Pixel detail").grid(row=1, column=0, sticky="w", pady=4)
    detail_box = ttk.Spinbox(
        options,
        from_=1,
        to=240,
        increment=8,
        textvariable=detail_var,
        width=8,
    )
    detail_box.grid(row=1, column=1, sticky="w", pady=4)
    ttk.Label(
        options,
        text="More detail means smaller squares and slower drawing.",
    ).grid(row=2, column=0, columnspan=2, sticky="w", pady=(0, 4))

    ttk.Label(options, text="Palette colors").grid(row=3, column=0, sticky="w", pady=4)
    colors_box = ttk.Combobox(
        options,
        textvariable=colors_var,
        values=("Auto", "4", "8", "12", "16", "24", "32", "48", "64", "128", "256"),
        state="readonly",
        width=8,
    )
    colors_box.grid(row=3, column=1, sticky="w", pady=4)
    grid_check = ttk.Checkbutton(
        options,
        text="Reduce faint grid lines (for grid-paper drawings)",
        variable=grid_var,
    )
    grid_check.grid(row=4, column=0, columnspan=2, sticky="w", pady=4)
    options.columnconfigure(1, weight=1)

    def apply_preset(event):
        selected = PRESET_LABELS[event.widget.get()]
        settings = PROCESSING_PRESETS[selected]
        detail_var.set(settings["detail"])
        grid_var.set(settings["suppress_grid"])
        colors_var.set("Auto")

    preset_box.bind("<<ComboboxSelected>>", apply_preset)

    drop_area = tk.Label(
        content,
        text="Drop an image here",
        font=("Segoe UI", 12),
        relief="groove",
        borderwidth=2,
        background="#f2f2f2",
        height=4,
    )
    drop_area.pack(fill="both", expand=True, pady=(0, 14))

    selected_preview = ttk.Label(content, text="No image selected")
    selected_preview.pack(pady=(0, 8))
    status_label = ttk.Label(content, text="Choose an image, then select Generate.")
    status_label.pack(pady=(0, 8))

    actions = ttk.Frame(content)
    actions.pack(fill="x")

    output_frame = ttk.Frame(root)
    comparison_frame = ttk.Frame(root)

    def show_settings():
        output_frame.pack_forget()
        comparison_frame.pack_forget()
        content.pack(fill="both", expand=True)

    def save_output():
        if output_image is None:
            return
        path = filedialog.asksaveasfilename(
            parent=root,
            title="Save pixel art",
            defaultextension=".png",
            filetypes=[("PNG image", "*.png")],
            initialfile=(
                f"{selected_path.stem}_pixel_art.png"
                if selected_path is not None
                else "pixel_art.png"
            ),
        )
        if not path:
            return
        try:
            output_image.save(path, format="PNG")
        except OSError as error:
            messagebox.showerror(
                "Could not save image",
                f"Unable to save '{path}':\n{error}",
                parent=root,
            )
            return
        messagebox.showinfo(
            "Image saved",
            f"Pixel art saved to:\n{path}",
            parent=root,
        )

    def display_output(prepared, detail, colors, preset):
        nonlocal output_image
        output_image = prepared[2]
        content.pack_forget()
        comparison_frame.pack_forget()
        for child in output_frame.winfo_children():
            child.destroy()
        output_frame.pack(fill="both", expand=True)
        toolbar = ttk.Frame(output_frame, padding=8)
        toolbar.pack(fill="x")
        ttk.Button(toolbar, text="Back to settings", command=show_settings).pack(
            side="left", padx=4
        )
        ttk.Button(
            toolbar,
            text="Choose another image",
            command=lambda: (show_settings(), browse_for_image()),
        ).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Save PNG...", command=save_output).pack(
            side="right", padx=4
        )
        drawing_frame = ttk.Frame(output_frame)
        drawing_frame.pack(fill="both", expand=True)
        root.update()
        render_pixel_art(
            selected_image,
            pixel_size=args.pixel_size,
            scale=args.scale,
            margin=args.margin,
            background=args.background,
            title=args.title,
            fast=args.fast,
            root=root,
            detail=detail,
            colors=colors,
            preset=preset,
            suppress_grid=grid_var.get(),
            render_parent=drawing_frame,
            processed_result=prepared,
        )

    def generate_output():
        if selected_image is None:
            messagebox.showinfo(
                "Choose an image first",
                "Choose or drop an image before generating pixel art.",
                parent=root,
            )
            return
        try:
            selected_detail = int(detail_var.get())
            selected_colors = (
                None if colors_var.get() == "Auto" else int(colors_var.get())
            )
        except ValueError:
            messagebox.showerror(
                "Invalid output settings",
                "Enter a whole-number pixel detail value and choose a valid color count.",
                parent=root,
            )
            return
        if not 1 <= selected_detail <= 240:
            messagebox.showerror(
                "Invalid pixel detail",
                "Pixel detail must be between 24 and 240.",
                parent=root,
            )
            return
        preset = PRESET_LABELS[preset_var.get()]
        source = selected_image
        if args.scale is not None:
            if args.scale <= 0:
                messagebox.showerror(
                    "Invalid scale",
                    "Scale must be greater than zero.",
                    parent=root,
                )
                return
            source = source.resize(
                (
                    max(1, int(source.width * args.scale)),
                    max(1, int(source.height * args.scale)),
                ),
                Image.Resampling.NEAREST,
            )
        prepared = process_pixel_art(
            source,
            selected_detail,
            selected_colors,
            preset,
            suppress_grid=grid_var.get(),
        )
        display_output(prepared, selected_detail, selected_colors, preset)

    def compare_settings(kind):
        if selected_image is None:
            messagebox.showinfo(
                "Choose an image first",
                "Choose or drop an image before comparing settings.",
                parent=root,
            )
            return
        try:
            current_detail = int(detail_var.get())
        except ValueError:
            current_detail = PROCESSING_PRESETS[
                PRESET_LABELS[preset_var.get()]
            ]["detail"]
        detail_values = sorted(
            {
                max(24, min(240, round(current_detail * factor)))
                for factor in (0.65, 0.85, 1.0, 1.25)
            }
        )
        variants = (
            [(value, None, f"Detail: {value}") for value in detail_values]
            if kind == "detail"
            else [
                (current_detail, value, f"Colors: {value}")
                for value in (8, 16, 32, 64)
            ]
        )
        preset = PRESET_LABELS[preset_var.get()]
        source = selected_image
        if args.scale is not None:
            if args.scale <= 0:
                messagebox.showerror(
                    "Invalid scale",
                    "Scale must be greater than zero.",
                    parent=root,
                )
                return
            source = source.resize(
                (
                    max(1, int(source.width * args.scale)),
                    max(1, int(source.height * args.scale)),
                ),
                Image.Resampling.NEAREST,
            )
        content.pack_forget()
        output_frame.pack_forget()
        for child in comparison_frame.winfo_children():
            child.destroy()
        comparison_frame.pack(fill="both", expand=True)
        toolbar = ttk.Frame(comparison_frame, padding=8)
        toolbar.pack(fill="x")
        ttk.Button(toolbar, text="Back to settings", command=show_settings).pack(
            side="left"
        )
        ttk.Label(
            toolbar,
            text="Choose a result to use those settings, then generate it.",
        ).pack(side="left", padx=12)
        grid = ttk.Frame(comparison_frame, padding=8)
        grid.pack(fill="both", expand=True)
        for index, (variant_detail, variant_colors, label) in enumerate(variants):
            result = process_pixel_art(
                source,
                variant_detail,
                variant_colors,
                preset,
                suppress_grid=grid_var.get(),
            )
            preview = result[2].copy()
            preview.thumbnail((300, 280), Image.Resampling.NEAREST)
            photo = ImageTk.PhotoImage(preview)
            cell = ttk.LabelFrame(grid, text=label, padding=8)
            cell.grid(
                row=index // 2,
                column=index % 2,
                sticky="nsew",
                padx=6,
                pady=6,
            )
            image_label = ttk.Label(cell, image=photo)
            image_label.image = photo
            image_label.pack(expand=True)

            def select_variant(
                selected_detail=variant_detail,
                selected_colors=variant_colors,
            ):
                detail_var.set(selected_detail)
                if selected_colors is not None:
                    colors_var.set(str(selected_colors))
                show_settings()

            ttk.Button(
                cell,
                text="Use these settings",
                command=select_variant,
            ).pack(pady=(6, 0))
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)
        grid.rowconfigure(0, weight=1)
        grid.rowconfigure(1, weight=1)

    ttk.Button(actions, text="Generate pixel art", command=generate_output).pack(
        side="left", padx=(0, 6)
    )
    ttk.Button(
        actions,
        text="Compare detail",
        command=lambda: compare_settings("detail"),
    ).pack(side="left", padx=6)
    ttk.Button(
        actions,
        text="Compare colors",
        command=lambda: compare_settings("colors"),
    ).pack(side="left", padx=6)
    ttk.Button(
        actions,
        text="Choose another image...",
        command=lambda: browse_for_image(),
    ).pack(side="right", padx=6)

    def browse_for_image():
        path = filedialog.askopenfilename(
            parent=root,
            title="Choose an image",
            filetypes=[
                ("Image files", "*.png *.jpg *.jpeg *.gif *.bmp *.webp *.tif *.tiff"),
                ("All files", "*.*"),
            ],
        )
        if path:
            open_image(path)

    def open_image(path):
        nonlocal selected_image, selected_path, preview_photo, output_image
        image_path = Path(path)
        try:
            selected_image = load_image(image_path)
        except (OSError, ValueError) as error:
            messagebox.showerror(
                "Could not open image",
                f"Unable to open '{image_path}':\n{error}",
                parent=root,
            )
            return
        selected_path = image_path
        thumbnail = selected_image.copy()
        thumbnail.thumbnail((260, 180), Image.Resampling.LANCZOS)
        preview_photo = ImageTk.PhotoImage(thumbnail)
        selected_preview.configure(
            image=preview_photo,
            text=f"Selected: {image_path.name}",
            compound="top",
        )
        status_label.configure(
            text="Image loaded. Adjust options, then generate or compare."
        )
        output_image = None

    if TkinterDnD is not None:
        drop_area.drop_target_register(DND_FILES)
        drop_area.dnd_bind(
            "<<Drop>>",
            lambda event: open_image(root.tk.splitlist(event.data)[0]),
        )
    else:
        drop_area.configure(
            text="Drag and drop requires tkinterdnd2.\nUse the button below to browse for an image."
        )

    ttk.Button(content, text="Browse for image...", command=browse_for_image).pack()
    root.mainloop()


def main():
    args = parse_args()
    if args.image is None:
        launch_uploader(args)
        return

    source_path = Path(args.image)
    if not source_path.exists():
        raise FileNotFoundError(f"Image not found: {source_path}")

    image = load_image(source_path)
    screen = render_pixel_art(
        image,
        pixel_size=args.pixel_size,
        scale=args.scale,
        margin=args.margin,
        background=args.background,
        title=args.title,
        fast=args.fast,
        detail=args.detail,
        colors=args.colors,
        preset=args.preset,
    )
    screen.mainloop()
    t.done()


if __name__ == "__main__":
    main()
