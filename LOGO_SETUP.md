# Logo Setup

Posts can include a company logo when one is available. The app looks for logo files in `assets/logos/`.

## Resolving "Found 0 logos"

If you see "Found 0 logos" in logs, add at least one logo file to the logos directory:

```bash
cp /path/to/truststack_logo.png assets/logos/truststack_logo.png
ls -la assets/logos
```

Supported formats (e.g. PNG, JPG) and naming are defined in your config (e.g. `config.yaml` under `logos`). A typical default filename is `truststack_logo.png`.
