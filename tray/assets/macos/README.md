# macOS menu bar glyphs

Four template images, one per capacity state, plus their `@2x` retina pairs.

`adr_005` settles why these are monochrome: a macOS menu bar icon is a *template
image*, black plus alpha with no background, and the system inverts it for the
current theme. Colour is therefore unavailable here, so capacity state is
carried by the glyph and never by a tint. The `Template` suffix in the PNG
filenames is load-bearing — it is what makes AppKit treat them as templates.

| Glyph | State | Reads as |
|---|---|---|
| `ok` | 25% remaining and above | the ring nearly closed |
| `low` | below 25% | the same ring drained to a symmetric arch |
| `critical` | below 5% | the ring open, urgency in the solid centre |
| `unknown` | nothing ever reported | eight dots on the ring, present but broken, never an empty gauge |

`CDX.icns` is the application icon, distinct from these glyphs: it is what
Finder, Login Items and notification banners show for the app itself, and it
keeps the full-colour brand artwork. The menu bar is the only surface that
cannot use colour.

The SVGs are the source; the PNGs are committed rather than generated so the
build needs no rasterizer. To change a glyph, edit its SVG and re-run:

```sh
for s in ok low critical unknown; do
  rsvg-convert -w 18 -h 18 $s.svg -o CDXTemplate-$s.png
  rsvg-convert -w 36 -h 36 $s.svg -o CDXTemplate-$s@2x.png
done
```

Geometry is shared on purpose: one centre, one radius, one stroke weight across
all four. `low` is symmetric about the top and `unknown` uses eight dots rather
than six, both because fewer or off-centre marks read as scattered rather than
as one ring. An earlier generated set had four different circle diameters and a
sub-pixel stroke, and at 18px it collapsed — `ok` and `unknown` became
indistinguishable, which is the one thing these glyphs exist to avoid. Keep the
circle constant when editing, and check the result at 18px rather than zoomed
in.
