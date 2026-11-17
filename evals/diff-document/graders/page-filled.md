---
type: regex
pattern: '\{\{(標題|結論)'
match: not_contains
target: { source: file, path: report-diff.html }
---
