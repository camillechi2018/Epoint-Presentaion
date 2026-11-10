const fs = require('fs');
const path = require('path');
const modulePath = process.env.EPOINT_SHARP_MODULE || 'sharp';
const sharp = require(modulePath);
const [input, output, width, height] = process.argv.slice(2);
if (!input || !output || !width || !height) throw new Error('usage: rasterize_svg.cjs input.svg output.png width height');
sharp(fs.readFileSync(input), { density: 300 }).resize(Number(width), Number(height), { fit: 'fill' }).png().toFile(output).catch(e => { console.error(e); process.exitCode = 1; });
