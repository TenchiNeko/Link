# Link Research Tools Reference Notes

This folder is the proper home for Link-native research/code search tools.

Raw imported TypeScript tool source stays in the research intake archive:

`.link_research_intake/research-mining-20260524T153654Z-2772421/extracted/Research/Research/src/tools/`

Use these as references only:

- `GrepTool/GrepTool.ts`
- `GrepTool/prompt.ts`
- `GlobTool/GlobTool.ts`
- `GlobTool/prompt.ts`
- `FileReadTool/FileReadTool.ts`
- `FileReadTool/limits.ts`
- `BashTool/readOnlyValidation.ts`
- `BashTool/pathValidation.ts`
- `BashTool/bashSecurity.ts`

Primary Link-native CLI:

`python3 tools/research/link_research_file_tools.py grep "PATTERN" --root research`

Return `path:line` evidence whenever possible.
