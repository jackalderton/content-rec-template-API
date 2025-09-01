from core.extract import process_url
from core.types import ExtractOptions

opts = ExtractOptions(exclude_selectors=[])
meta, lines = process_url("https://developers.google.com/search/docs/appearance/google-images", opts)

print("=== META ===")
for k, v in meta.items():
    print(k, ":", v[:200] if isinstance(v, str) else v)  # shorten long schema

print("\n=== FIRST 5 LINES ===")
print("\n".join(lines[:5]))
