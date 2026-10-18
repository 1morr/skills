# report.json

Text fields take light Markdown: paragraphs, `- ` and `1. ` lists, `` `code` ``, `**bold**`, `[text](https://…)`. Paths are relative to the report directory.

```json
{
  "title": "Search results keep their scroll position",
  "lang": "en",
  "range": { "base": "a1b2c3d", "head": "e4f5a6b", "base_ref": "main", "head_ref": "fix/scroll" },
  "summary": "Going back from a result now returns to the same spot in the list.",
  "why": {
    "text": "Users lost their place after every click on long result lists.",
    "sources": ["#212", "commit e4f5a6b"]
  },
  "how": "The list stores its offset when a result opens and restores it on return.",
  "decisions": [
    {
      "decision": "Keep the offset in memory, not in the URL",
      "why": "Offsets in the URL would break shared links.",
      "alternatives": "URL query parameter; session storage",
      "basis": "stated",
      "source": "#212 discussion"
    }
  ],
  "files": {
    "src/search/ResultList.tsx": "Saves and restores the scroll offset.",
    "src/search/ResultList.test.tsx": "Covers the restore.",
    "*.lock": "Dependency bump pulled in by the test helper."
  },
  "hunks": [
    { "file": "src/search/ResultList.tsx", "match": "scrollTop", "note": "Restores after the list renders, so the offset exists." }
  ],
  "evidence": {
    "level": "before-after",
    "why_not_higher": "",
    "items": [
      { "kind": "compare", "caption": "Back from result 40", "before": "before-back.jpg", "after": "after-back.jpg" },
      { "kind": "image", "caption": "Empty results", "after": "after-empty.jpg" },
      { "kind": "output", "caption": "Unit tests", "command": "npm test -- ResultList", "after_file": "tests-after.txt" }
    ]
  },
  "try_it": ["`npm run dev`, search `test`, open result 40, press back"],
  "unverified": ["Safari", "Lists over 10 000 items"]
}
```

| Field | Required | Meaning |
|---|---|---|
| `title` | yes | The change as a reader would name it. |
| `lang` | no | Label language: `en` (default) or `zh-Hant`. |
| `range.base` | yes | Any git revision. |
| `range.head` | yes | A git revision, or `null` for the working tree including untracked files. |
| `range.base_ref`, `range.head_ref` | no | Branch names shown beside the SHAs. Shown only when the branch points at that commit; otherwise dropped with a warning. |
| `summary` | yes | User-facing effect. |
| `why.text`, `why.sources` | no | Empty `sources` renders as awaiting the author, with any `text` marked inferred. |
| `how` | no | Approach. |
| `decisions[]` | no | `decision`, `why`, optional `alternatives`, `basis` (`stated` or `inferred`, default `inferred`), optional `source`. |
| `files` | yes | Changed path or glob → note. Every path in the diff needs one, dot-directories included. A key matches the whole repo-relative path; exact paths win over globs; `*` crosses `/`. |
| `hunks[]` | no | `file`, optional `match` (keeps hunks whose text contains it; all hunks without it), `note`. |
| `evidence.level` | yes | `before-after`, `after`, `tests` or `static`. |
| `evidence.why_not_higher` | below `before-after` | The obstacle. |
| `evidence.items[]` | no | See kinds below. |
| `try_it[]`, `unverified[]` | no | One step or gap per string. |

Evidence kinds:

- `image`: `after` image path. A screenshot of the head only.
- `compare`: `before` and `after` image paths. Rendered side by side, with a slider when the two images share a size.
- `output`: optional `command`, `after` text or `after_file`, optional `before` text or `before_file` (the same command on base). Without `command` it shows a file as is, such as a reproduction written for the showcase. Text shows in `pr.md` too.

The renderer warns about home-directory paths and secret-looking values in `report.json` and text evidence. It cannot read text inside images; scrub screenshots yourself.

Images: `.png`, `.jpg`, `.jpeg`, `.webp`, `.gif`, `.svg`.
