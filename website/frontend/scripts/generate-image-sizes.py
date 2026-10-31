"""Rebuild public screenshot dimensions with Pillow; never modify source images."""
from pathlib import Path
import json
from PIL import Image

root = Path(__file__).resolve().parents[1]
result = {}
invalid = []
for path in sorted((root / 'public').rglob('*')):
    if path.suffix.lower() not in {'.png', '.jpg', '.jpeg', '.webp'}:
        continue
    try:
        with Image.open(path) as image:
            image.load()
            result['/' + path.relative_to(root / 'public').as_posix()] = {'width': image.width, 'height': image.height}
    except OSError:
        invalid.append(path.relative_to(root / 'public').as_posix())
(root / 'src/config/officialImageSizes.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'dimensions': len(result), 'invalidAssets': invalid}, ensure_ascii=False))
