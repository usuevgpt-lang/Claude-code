// SVGO 4.x config for icons and equipment pictograms.
// Run only after the user approved the drawing and agreed to npx:
//   npx svgo@4.1.0 --config <skill>/svgo.config.mjs in.svg -o out/in.svg
//   npx svgo@4.1.0 --config <skill>/svgo.config.mjs -f src -o dist
// Never write the output over the original file.
export default {
  multipass: true,
  floatPrecision: 2,
  plugins: [
    // preset-default in SVGO 4 keeps viewBox and <title>; keep ids used by <defs>/<use>/clipPath
    { name: 'preset-default', params: { overrides: { cleanupIds: false } } },
    'removeScripts', // strips <script>, on* event handlers and javascript: URLs (not a full sanitiser)
    'removeXlink',   // xlink:href -> href (SVG 2)
  ],
};
