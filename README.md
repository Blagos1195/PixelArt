# Pixel Art Generator

A desktop pixel-art generator and a separate browser edition for GitHub Pages.

## Repository layout

- `app/`: original Python desktop application, dependencies, PyInstaller spec and packaged Windows distribution
- `web/`: static browser edition
- `README.md`: project overview and publishing instructions

## Browser edition

The website uses JavaScript, Canvas and a Web Worker. Images are processed locally in the browser and are not uploaded to a server.

It includes six processing presets, adaptive rectangular blocks, representative colours, palette reduction, background snapping, optional grid suppression, near-black snapping and isolated-colour cleanup.

The drawing stage paints each block in sequence and moves a turtle cursor across the canvas. Drawing speed can be adjusted, paused, restarted or skipped. Results can be exported as PNG.

The browser implementation recreates the desktop processing approach; it is not a pixel-for-pixel port of Pillow. Palette quantisation and image filters differ between the two environments, so some images can produce different results.

## Publish with GitHub Pages

GitHub Pages' built-in branch publishing supports the repository root or a `/docs` folder, not an arbitrary `/web` folder. The root `index.html` therefore redirects visitors to `web/`.

1. Open the repository's **Settings**.
2. Open **Pages** under **Code and automation**.
3. Under **Build and deployment**, choose **Deploy from a branch**.
4. Select the `master` branch and the `/(root)` folder, then save.

No GitHub Actions workflow is needed. GitHub Pages' built-in publishing handles the website.

## Desktop application

The original Tkinter/Turtle application is in `app/draw.py`. To install dependencies, run `pip install -r requirements.txt` from `app/`. The PyInstaller spec and existing `dist/` package are kept alongside it.
