const fs = require("fs");
const path = require("path");
const ts = require("typescript");
const root = path.resolve(__dirname, "../../apps/web/src");
const errors = [];
function walk(directory) {
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    const filename = path.join(directory, entry.name);
    if (entry.isDirectory()) walk(filename);
    else if (/\.tsx?$/.test(entry.name)) {
      const source = fs.readFileSync(filename, "utf8");
      const result = ts.transpileModule(source, {
        fileName: filename,
        reportDiagnostics: true,
        compilerOptions: {
          target: ts.ScriptTarget.ES2022,
          module: ts.ModuleKind.ESNext,
          jsx: ts.JsxEmit.ReactJSX,
        },
      });
      for (const diagnostic of result.diagnostics || []) {
        if (diagnostic.category === ts.DiagnosticCategory.Error) {
          errors.push(`${filename}: ${ts.flattenDiagnosticMessageText(diagnostic.messageText, " ")}`);
        }
      }
    }
  }
}
walk(root);
if (errors.length) {
  console.error(errors.join("\n"));
  process.exit(1);
}
console.log("TypeScript and TSX syntax validation passed.");
