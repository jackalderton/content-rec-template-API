from content_rec_template.core.extract import process_url
from content_rec_template.core.types import ExtractOptions

# Configure extraction options
opts = ExtractOptions(exclude_selectors=[])

# Run extraction on a test URL
meta, lines = process_url(
    "https://developers.google.com/search/docs/appearance/google-images",
    opts
)

# Print metadata
print("=== META ===")
for k, v in meta.items():
    if isinstance(v, str):
        print(f"{k}: {v[:200]}{'...' if len(v) > 200 else ''}")
    else:
        print(f"{k}: {v}")

# Print first few extracted lines
print("\n=== FIRST 5 LINES ===")
for line in lines[:5]:
    print(line)
