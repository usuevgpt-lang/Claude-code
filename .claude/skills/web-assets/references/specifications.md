# Web Asset Specifications and Best Practices

> Upstream: alonw0/web-asset-generator (MIT). Locally modified: ICO sizes, SVG favicon,
> manifest and maskable icons, WebP/JPEG, X validator note, Russian platforms. See `../NOTICE.md`.

## Favicon Specifications

### Standard Sizes
- **16x16px**: Classic favicon size, shown in browser tabs
- **32x32px**: Standard browser favicon, taskbar icons
- **96x96px**: Google TV favicon
- **favicon.ico**: Multi-resolution ICO file with **16x16, 32x32 and 48x48** frames, built from
  a large square image (Pillow ignores ICO sizes larger than the image it saves from)
- **icon.svg**: Scalable favicon for modern browsers. It is used only when the source logo is
  already SVG; it is copied as-is. Must not contain `<script>` or external references.

### Best Practices
- Use simple, recognizable designs that work at small sizes — for НОВАПРОМ a square mark,
  not the full wordmark, reads best at 16x16
- Ensure good contrast for visibility
- Test how the icon looks on both light and dark backgrounds
- Avoid too much detail - it won't be visible at 16x16
- Non-square logos are fitted ("contain") and centred, never stretched
- Browsers and search crawlers also request `/favicon.ico` at the site root: put a copy there

## App Icons (PWA/Mobile)

### Sizes
- **180x180px**: Apple touch icon (iOS Safari). Must be opaque (iOS fills transparency with black)
- **192x192px**: Android Chrome icon (listed in `site.webmanifest`)
- **512x512px**: Android Chrome high-res icon, PWA splash screens
- **512x512px maskable** (`purpose: "maskable"`): opaque, full-bleed background. The platform
  crops it to a circle/squircle; keep the logo inside the **safe zone — a centred circle with a
  radius of 40% of the icon** (W3C Web App Manifest). The generator scales the logo so that its
  diagonal fits that circle.

### Best Practices
- Use square images with no transparency (or solid background)
- Avoid text that becomes unreadable at smaller sizes
- Design should be recognizable as your brand
- Consider safe area: iOS rounds corners, Android may apply masks

## Web App Manifest (`site.webmanifest`)

```json
{
  "name": "НОВАПРОМ",
  "short_name": "НОВАПРОМ",
  "lang": "ru",
  "start_url": "/",
  "display": "browser",
  "theme_color": "#1C1C1C",
  "background_color": "#FFFFFF",
  "icons": [
    {"src": "android-chrome-192x192.png", "sizes": "192x192", "type": "image/png"},
    {"src": "android-chrome-512x512.png", "sizes": "512x512", "type": "image/png"},
    {"src": "maskable-icon-512x512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"}
  ]
}
```

- UTF-8 JSON; `short_name` ideally ≤ 12 characters.
- Icon `src` values are relative to the manifest URL, so keep the manifest in the same folder as the icons.
- `display: browser` suits a corporate site that is not meant to be installed as an app.

## Open Graph (Social Media Meta Images)

### Primary Sizes
- **1200x630px** (1.91:1 ratio): Facebook, LinkedIn, WhatsApp, VK, Telegram, most platforms
- **1200x675px** (16:9 ratio): Twitter summary card with large image
- **1200x1200px** (1:1 ratio): Square variant for some contexts

### Formats
- `og:image`: **PNG or JPEG**, RGB (no transparency — transparent areas render black or white
  depending on the platform). JPEG is usually smaller; use it when the PNG is large.
- **WebP** variants are generated for on-site use (`<picture>`, cards). Do not rely on WebP for
  `og:image`: crawler support differs between platforms.
- Logos are placed with "contain" on a brand background (#1C1C1C or #FFFFFF), never cropped.
  "cover" (crop to fill) is only for photos.

### Platform-Specific Notes

#### Facebook
- Recommended: 1200x630px
- Minimum: 600x315px
- Ratio: 1.91:1
- File size: <8MB
- Shown in news feed, shared posts, link previews

#### Twitter / X
- Summary card large image: 1200x675px (16:9)
- Summary card: 1200x1200px (1:1)
- Minimum: 300x157px
- File size: <5MB
- Use `twitter:card` meta tag to specify card type

#### WhatsApp
- Uses Open Graph tags (same as Facebook)
- Recommended: 1200x630px
- Shows preview when link is shared

#### LinkedIn
- Recommended: 1200x627px
- Minimum: 1200x628px
- Aspect ratio: 1.91:1

#### VK, Telegram (main audience of novaprom.ru)
- Both read Open Graph tags; 1200x630 works.
- Both cache previews. Telegram: send the URL to @WebpageBot to refresh the preview.

### Content Best Practices
- Keep important content in the "safe zone" (center 80% of image)
- Use large, readable text (minimum 60pt font)
- Include your logo or branding
- Avoid clutter - less is more for social sharing
- Test on both desktop and mobile previews
- Use high-contrast colors for readability
- Consider how image looks in small previews

### Text Guidelines
- Maximum ~40 characters per line for readability
- Use 2-3 lines of text maximum
- Font size: 80-120px for 1200px width
- Leave breathing room around text
- Cyrillic needs a font that contains it: brand font Raleway (OFL, has Cyrillic), otherwise
  Arial/Segoe UI (Windows) or DejaVu/Liberation (Linux). Never Pillow's built-in bitmap font.

## HTML Implementation

### Favicon HTML Tags
With an SVG favicon (the `sizes="32x32"` on the ICO stops Chrome from preferring the ICO over the SVG):
```html
<link rel="icon" href="/favicon.ico" sizes="32x32">
<link rel="icon" href="/icon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png">
<link rel="manifest" href="/site.webmanifest">
<meta name="theme-color" content="#1C1C1C">
```
Without an SVG:
```html
<link rel="icon" href="/favicon.ico" sizes="32x32">
<link rel="icon" type="image/png" sizes="32x32" href="/favicon-32x32.png">
<link rel="icon" type="image/png" sizes="16x16" href="/favicon-16x16.png">
<link rel="icon" type="image/png" sizes="96x96" href="/favicon-96x96.png">
<link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png">
<link rel="manifest" href="/site.webmanifest">
<meta name="theme-color" content="#1C1C1C">
```

### Open Graph Meta Tags
```html
<!-- Basic Open Graph -->
<meta property="og:title" content="Your Page Title">
<meta property="og:description" content="Your page description">
<meta property="og:image" content="https://yoursite.com/og-image.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="Description of the image">
<meta property="og:url" content="https://yoursite.com/page">
<meta property="og:type" content="website">

<!-- Twitter Card -->
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="Your Page Title">
<meta name="twitter:description" content="Your page description">
<meta name="twitter:image" content="https://yoursite.com/twitter-image.png">
<meta name="twitter:image:alt" content="Description of the image">
```
`og:image` must be an **absolute https:// URL**; `og:image:type` must match the real file format.

## File Format Guidelines

### For Favicons and Icons
- **Format**: PNG with transparency (apple-touch and maskable icons: opaque)
- **Color mode**: RGBA
- **Optimization**: Use PNG optimization (e.g., pngquant)
- **ICO file**: For favicon.ico, include 16x16, 32x32 and 48x48 sizes

### For Open Graph Images
- **Format**: PNG or JPEG (+ WebP copies for the site itself)
- **PNG**: Better for graphics with text, logos, flat colors
- **JPEG**: Better for photos, complex images
- **File size**: Keep under 1MB for fast loading
- **Color mode**: RGB (not CMYK), no alpha channel

## Color Considerations

### Contrast
- Ensure sufficient contrast for readability (WCAG AA minimum 4.5:1; 3:1 for large bold text)
- Test on various backgrounds (light mode, dark mode)
- НОВАПРОМ pairs (WCAG ratio): white on #1C1C1C ≈ 17.0:1; #FDB913 on #1C1C1C ≈ 9.8:1;
  #4D7C90 on white ≈ 4.6:1; #FDB913 on white ≈ 1.7:1 (never use for text)

### Brand Colors
- Use brand colors consistently across assets
- Consider how colors appear at different sizes
- Test color visibility in small icons

## Testing Your Assets

### Tools
- `python scripts/check_assets.py <folders>` — local check of real pixel sizes, formats, ICO frames, manifest
- [Facebook Sharing Debugger](https://developers.facebook.com/tools/debug/)
- X/Twitter: the Card Validator no longer shows previews (removed in 2022); check by composing a post
- [LinkedIn Post Inspector](https://www.linkedin.com/post-inspector/)
- Telegram: @WebpageBot (refreshes cached previews)

Online validators need the page to be public; they are run by the user after deployment.

### Checklist
- [ ] View favicon in browser tab at 100% and 200% zoom
- [ ] Test Open Graph preview on target platforms
- [ ] Check mobile rendering
- [ ] Verify image loads quickly
- [ ] Confirm text is readable at all sizes
- [ ] Test with various link sharing methods

## Common Pitfalls to Avoid

1. **Too much detail in small icons**: Simplify designs for favicons
2. **Text too small**: Use large fonts (80px+) for Open Graph images
3. **Forgetting safe zones**: Keep content away from edges
4. **Wrong aspect ratios**: Using 1:1 image for 1.91:1 requirement causes cropping
5. **Large file sizes**: Optimize images to reduce load time
6. **Absolute URLs**: Use absolute URLs for Open Graph images (https://...)
7. **Missing alt text**: Always provide descriptive alt text for accessibility
8. **Not testing**: Always test how assets appear on actual platforms
9. **Wrong declared type**: a JPEG saved as `.png` or declared as `image/png` (seen on novaprom.ru)
10. **Stretched logos**: resizing a non-square logo straight to a square distorts it
