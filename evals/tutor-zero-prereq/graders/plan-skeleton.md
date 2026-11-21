---
type: regex
pattern: '(先備|前置|Σ|自由度|df)[\s\S]*(辨別|觸發|排除|paired|independent)|(?:辨別|觸發|排除|paired|independent)[\s\S]*(先備|前置|Σ|自由度|df)'
target: { source: file, path: tutor/plan.md }
arm: with-only
---
