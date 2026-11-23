#!/usr/bin/env python3
"""Slice an approved long master at supplied pixel boundaries and verify it losslessly."""
import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageChops


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('master', type=Path)
    parser.add_argument('output_dir', type=Path)
    parser.add_argument('--cuts', required=True, help='comma-separated interior y coordinates in pixels')
    args = parser.parse_args()
    source = args.master.resolve(strict=True)
    out = args.output_dir.resolve()
    cuts = [int(v.strip()) for v in args.cuts.split(',') if v.strip()]
    with Image.open(source) as opened:
        opened.load()
        image = opened.copy()
    width, height = image.size
    if not cuts or cuts != sorted(set(cuts)) or cuts[0] <= 0 or cuts[-1] >= height:
        parser.error('cuts must be unique, increasing interior positions within the master height')
    bounds = [0, *cuts, height]
    targets = [out / f'{i:02d}.png' for i in range(1, len(bounds))]
    manifest_path = out / 'manifest.json'
    if any(path.exists() for path in [*targets, manifest_path]):
        raise FileExistsError('output already exists; choose a new output directory')
    out.mkdir(parents=True, exist_ok=True)
    restored = Image.new(image.mode, image.size)
    records = []
    for i, (top, bottom) in enumerate(zip(bounds, bounds[1:])):
        part = image.crop((0, top, width, bottom))
        part.save(targets[i], format='PNG')
        with Image.open(targets[i]) as check:
            check.load()
            if check.size != (width, bottom - top) or check.mode != image.mode:
                raise ValueError(f'Failed size or mode validation: {targets[i]}')
            restored.paste(check, (0, top))
        records.append({'file': targets[i].name, 'top': top, 'bottom_exclusive': bottom,
                        'width': width, 'height': bottom - top})
    difference = ImageChops.difference(image, restored)
    if any(band.getbbox() is not None for band in difference.split()):
        raise ValueError('Restored pixels differ from the master')
    manifest = {'master': str(source), 'master_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
                'width': width, 'height': height, 'mode': image.mode, 'panels': records,
                'pixel_reconstruction_verified': True}
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'panels': len(records), 'size': [width, height],
                      'pixel_reconstruction_verified': True, 'manifest': str(manifest_path)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
