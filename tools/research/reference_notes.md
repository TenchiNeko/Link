# Link research tools

This directory contains Link-native helpers for inspecting user-supplied research inputs. They report bounded `path:line` evidence and do not bundle or vendor external repositories.

Use the file-tools CLI with an input directory supplied at runtime:

```bash
python3 tools/research/link_research_file_tools.py grep "PATTERN" --root /path/to/research-input
```

Downloaded archives and extracted source trees belong outside the repository. Keep any resulting proposal or review data redacted and preserve enough provenance for a contributor to understand where an observation came from.
