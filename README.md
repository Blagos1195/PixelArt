# Pixel Art Generator

A desktop pixel-art generator and a separate browser edition for GitHub Pages.

## Browser edition

The website is a static application. It uses JavaScript, Canvas and a Web Worker, so images are processed locally in the browser and are not uploaded to a server.

The browser edition includes the six desktop processing presets, adaptive rectangular blocks, representative colours, palette reduction, background snapping, optional grid suppression, near-black snapping and small isolated-colour cleanup.

The drawing stage intentionally does not simply display the finished image. It paints each block in sequence and moves a small turtle cursor across the canvas. The drawing speed can be adjusted, paused, restarted or skipped. The result can be exported as a PNG.

The browser implementation is a translation of the desktop processing approach, not a pixel-for-pixel port of Pillow. Palette quantisation and image filters differ between the two environments, so some images may produce slightly different results.

## Publish with GitHub Pages

1. Open the repository's **Settings**.
2. Open **Pages** under **Code and automation**.
3. Under **Build and deployment**, choose **Deploy from a branch**.
4. Select the `master` branch and the `/(root)` folder, then save.
5. GitHub Pages will publish the root `index.html` site.

No GitHub Actions workflow is needed. Do not add test, build or deployment workflows. GitHub Pages' built-in branch publishing handles website publication.

## Desktop application

The original Tkinter/Turtle desktop application remains in `draw.py`. Its requirements and packaged Windows distribution are unchanged. The browser edition does not replace or depend on the desktop application.

## Files

- `index.html`: browser interface
- `style.css`: responsive interface styling
- `app.js`: image loading, drawing animation, comparisons and PNG export
- `processor.js`: browser-side image processing worker
- `draw.py`: original desktop application
- `dist/`: existing packaged desktop distribution
