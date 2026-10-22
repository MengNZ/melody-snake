// Bundle the segmentation CLI into a single runnable JS file (used by the Python
// benchmark). Requires esbuild (already a vite dependency).
import { build } from 'esbuild';

await build({
  entryPoints: ['scripts/segment-cli.ts'],
  bundle: true,
  platform: 'node',
  format: 'esm',
  target: 'node18',
  outfile: 'dist/segment-cli.mjs',
});

console.log('built dist/segment-cli.mjs');
