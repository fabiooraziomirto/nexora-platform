# Nexora brand assets

Visual identity for the Nexora platform. The mark is a central **hub** (the
control plane) circled by an **orbit** carrying three **fleet nodes** — devices
orbiting the control plane across the cloud-edge continuum. The orbit also
echoes the *-ora* (aurora / orbit) in the name.

## Colors

| Token        | Hex       | Use                                          |
|--------------|-----------|----------------------------------------------|
| Indigo       | `#4F46E5` | Primary. Hub, ring, wordmark mark on light.  |
| Teal         | `#14B8A6` | Accent. Fleet nodes on light backgrounds.    |
| Teal (light) | `#2DD4BF` | Fleet nodes on dark / reversed backgrounds.  |
| Ink          | `#1B1B2E` | Wordmark text on light backgrounds.          |
| Dark surface | `#16162A` | Reference dark background for reversed marks.|

Reversed lockups use white (`#FFFFFF`) for the hub, ring, and wordmark.

## Files

```
nexora-mark.svg            Color mark (transparent bg) — default
nexora-mark-reversed.svg   White + teal mark for dark backgrounds
nexora-mark-mono.svg       Single color via currentColor (inherits text color)
nexora-mark-512.png        Color mark, 512px raster (slides, docs)
nexora-logo.svg            Horizontal lockup: mark + "nexora"
nexora-logo-reversed.svg   Horizontal lockup for dark backgrounds
nexora-logo.png            Horizontal lockup, 1020x300 raster
nexora-app-icon.svg        Rounded indigo square + white mark
nexora-app-icon-180.png    Raster app icon (180px)
nexora-app-icon-512.png    Raster app icon (512px)
nexora-app-icon-1024.png   Raster app icon (store / high-res)
favicon/
  favicon.svg              Scalable favicon (weighted for small sizes)
  favicon.ico              Multi-resolution 16/32/48
  favicon-16.png           16px
  favicon-32.png           32px
  favicon-48.png           48px
  apple-touch-icon.png     180px, for iOS home-screen
```

## Usage

Web `<head>`:

```html
<link rel="icon" href="/brand/favicon/favicon.svg" type="image/svg+xml">
<link rel="icon" href="/brand/favicon/favicon.ico" sizes="any">
<link rel="apple-touch-icon" href="/brand/favicon/apple-touch-icon.png">
```

Markdown (README header):

```markdown
<img src="docs/brand/nexora-logo.svg" alt="Nexora" height="64">
```

Monochrome mark inherits the surrounding color, so in HTML/CSS you can recolor
it with `color:` on the parent element.

## Guidelines

- Keep clear space around the mark equal to the radius of the hub.
- Don't recolor the mark outside the tokens above; for single-color contexts
  use `nexora-mark-mono.svg`.
- Don't add gradients, shadows, or outlines — the mark is flat by design.
- Minimum sizes: mark ~16px, full lockup ~96px wide.
- The wordmark in the `.svg` lockups uses a system sans-serif font stack. For
  print or to guarantee identical rendering everywhere, outline the text to
  paths in a vector editor before export.
```
