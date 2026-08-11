"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
exports.BlazeLanguageService = void 0;
const vscode = __importStar(require("vscode"));
const declaration = /\b(var|constant|Function|Meta|Class)\s+([A-Za-z_][A-Za-z0-9_]*)/g;
const importPattern = /^\s*Import\s+(?:(\w+)\s+from\s+|\*\s+as\s+(\w+)\s+from\s+|\{([^}]+)\}\s+from\s+)?["']?([^"'\s]+)["']?/;
const keywords = new Set(['var', 'constant', 'Function', 'Meta', 'Class', 'Constructor', 'if', 'else', 'while', 'for', 'in', 'return', 'Break', 'Continue', 'Import', 'Export', 'Default', 'from', 'as', 'try', 'catch', 'finally', 'throw', 'static', 'public', 'private', 'this', 'super', 'and', 'or', 'not', 'true', 'false', 'null']);

class BlazeLanguageService {
    cache = new Map();

    analyze(document) {
        const cached = this.cache.get(document.uri.toString());
        if (cached && cached.version === document.version)
            return cached;

        const symbols = [];
        const imports = new Map();
        const diagnostics = [];
        const braces = [];
        let blockComment = false;

        // Scope-aware duplicate detection: each brace-delimited block (Class
        // body, Function/Meta body, if/while/for body, or any other `{ }`
        // block) gets its own declaration set, pushed when a `{` is seen and
        // popped when its matching `}` is seen. A `var`/`constant` name is
        // only compared against names already declared in the *current*
        // (innermost) scope -- not against every declaration in the file --
        // so the same name can be reused freely across separate Meta
        // functions, classes, or sibling blocks, while a real duplicate
        // within the same scope is still reported.
        const scopeStack = [new Map()];
        const currentScope = () => scopeStack[scopeStack.length - 1];

        for (let lineNo = 0; lineNo < document.lineCount; lineNo += 1) {
            const line = document.lineAt(lineNo).text;
            const code = this.codePart(line, () => blockComment, value => (blockComment = value));
            const structuralCode = this.maskStrings(code);

            this.validateLine(structuralCode, lineNo, diagnostics);

            // Walk declarations and braces on this line together, in
            // left-to-right column order, so a scope-introducing `{` that
            // appears earlier on the same line as a later declaration (e.g.
            // `if x { var n = 10 }` all on one line) still assigns that
            // declaration to the *new* inner scope, while a `Class`/`Meta`/
            // `Function` name is recorded in whichever scope was active at
            // its own position -- normally the enclosing scope, since its
            // own trailing `{` comes after its name.
            declaration.lastIndex = 0;
            const lineDeclarations = [];
            for (let match = declaration.exec(code); match; match = declaration.exec(code)) {
                const kind = this.symbolKind(match[1]);
                const start = match.index + match[0].lastIndexOf(match[2]);
                lineDeclarations.push({ match, kind, start });
            }
            let declIndex = 0;

            for (let column = 0; column < structuralCode.length; column += 1) {
                while (declIndex < lineDeclarations.length && lineDeclarations[declIndex].start === column) {
                    const { match, kind, start } = lineDeclarations[declIndex];
                    const range = new vscode.Range(lineNo, start, lineNo, start + match[2].length);
                    symbols.push({ name: match[2], kind, range, selectionRange: range, detail: `${match[1]} declaration` });

                    // Class/Function/Meta declare a *name* visible in the
                    // scope active at this column (normally the enclosing
                    // scope, since their own trailing `{` is still ahead on
                    // the line); the scope they introduce for their own body
                    // is a fresh frame pushed below once that `{` is reached
                    // -- so a `var` of the same name inside two different
                    // Meta bodies is never compared against each other here.
                    const scope = currentScope();
                    const prior = scope.get(match[2]);
                    if (prior && kind !== 'parameter') {
                        diagnostics.push(this.diagnostic(lineNo, start, match[2].length, 'BLZ1004', `Duplicate declaration '${match[2]}'`, vscode.DiagnosticSeverity.Warning));
                    }
                    else
                        scope.set(match[2], range);
                    declIndex += 1;
                }

                const char = structuralCode[column];
                if (char === '{') {
                    braces.push(new vscode.Position(lineNo, column));
                    scopeStack.push(new Map());
                }
                if (char === '}') {
                    if (braces.length === 0)
                        diagnostics.push(this.diagnostic(lineNo, column, 1, 'BLZ1001', 'Unexpected closing brace'));
                    else {
                        braces.pop();
                        // Guard scopeStack.length > 1 so a stray/unmatched
                        // closing brace (already reported above) can never
                        // pop the outermost (global) scope.
                        if (scopeStack.length > 1)
                            scopeStack.pop();
                    }
                }
            }
            // Any declarations positioned at or past the end of the
            // structural code (should not normally happen, since matches
            // come from `code` which is at least as long as
            // `structuralCode`) are still recorded in whatever scope is
            // current once the column scan finishes.
            while (declIndex < lineDeclarations.length) {
                const { match, kind, start } = lineDeclarations[declIndex];
                const range = new vscode.Range(lineNo, start, lineNo, start + match[2].length);
                symbols.push({ name: match[2], kind, range, selectionRange: range, detail: `${match[1]} declaration` });
                const scope = currentScope();
                const prior = scope.get(match[2]);
                if (prior && kind !== 'parameter') {
                    diagnostics.push(this.diagnostic(lineNo, start, match[2].length, 'BLZ1004', `Duplicate declaration '${match[2]}'`, vscode.DiagnosticSeverity.Warning));
                }
                else
                    scope.set(match[2], range);
                declIndex += 1;
            }

            const imported = importPattern.exec(code);
            if (imported) {
                const module = imported[4];
                const start = code.lastIndexOf(module);
                const range = new vscode.Range(lineNo, start, lineNo, start + module.length);
                const existing = imports.get(module) ?? [];
                existing.push(range);
                imports.set(module, existing);
                [imported[1], imported[2]].filter(Boolean).forEach(name => symbols.push({ name: name, kind: 'import', range, selectionRange: range, detail: `Import from ${module}` }));
            }
        }

        // Underline any unclosed braces directly at their opening location
        for (const open of braces) {
            const range = new vscode.Range(open, new vscode.Position(open.line, open.character + 1));
            const diag = new vscode.Diagnostic(range, 'BLZ1008: Unclosed brace; missing closing "}"', vscode.DiagnosticSeverity.Error);
            diag.code = 'BLZ1008';
            diag.source = 'BlazeLang';
            diagnostics.push(diag);
        }

        const result = Object.assign({ symbols, imports, diagnostics }, { version: document.version });
        this.cache.set(document.uri.toString(), result);
        return result;
    }

    clear() { this.cache.clear(); }
    symbols(document) { return this.analyze(document).symbols; }
    wordRange(document, position) { return document.getWordRangeAtPosition(position, /[A-Za-z_][A-Za-z0-9_]*/); }
    isKeyword(word) { return keywords.has(word); }
    symbolKind(word) { return { var: 'variable', constant: 'constant', Function: 'function', Meta: 'meta', Class: 'class' }[word] ?? 'variable'; }

    diagnostic(line, start, length, code, message, severity = vscode.DiagnosticSeverity.Error) {
        // Enforce a minimum underline span of 1 character to guarantee VS Code renders it
        const safeLength = Math.max(length, 1);
        const range = new vscode.Range(line, start, line, start + safeLength);
        const result = new vscode.Diagnostic(range, `${code}: ${message}`, severity);
        result.code = code;
        result.source = 'BlazeLang';
        return result;
    }

    validateLine(code, line, diagnostics) {
        const semicolon = code.indexOf(';');
        if (semicolon >= 0)
            diagnostics.push(this.diagnostic(line, semicolon, 1, 'BLZ1001', 'Unexpected token ";". BlazeLang statements do not use semicolons.'));

        const equals = /\b(var|constant)\s*=/.exec(code);
        if (equals)
            diagnostics.push(this.diagnostic(line, equals.index + equals[0].indexOf('='), 1, 'BLZ1001', 'Expected an identifier after declaration keyword.'));
    }

    codePart(line, inBlock, setBlock) {
        let output = '';
        let quote = '';
        let escaped = false;
        for (let i = 0; i < line.length; i += 1) {
            if (inBlock()) {
                if (line.slice(i, i + 2) === '*/') {
                    setBlock(false);
                    i += 1;
                }
                continue;
            }
            const pair = line.slice(i, i + 2);
            if (!quote && pair === '/*') {
                setBlock(true);
                i += 1;
                continue;
            }
            if (!quote && pair === '//')
                break;
            const char = line[i];
            output += char;
            if ((char === '"' || char === "'") && !escaped)
                quote = quote === char ? '' : (quote || char);
            escaped = char === '\\' && !escaped;
            if (char !== '\\')
                escaped = false;
        }
        return output;
    }

    maskStrings(code) {
        let output = '';
        let quote = '';
        let escaped = false;
        for (const char of code) {
            if (quote) {
                output += ' ';
                if (char === quote && !escaped)
                    quote = '';
                escaped = char === '\\' && !escaped;
                if (char !== '\\')
                    escaped = false;
            }
            else if (char === '"' || char === "'") {
                quote = char;
                output += ' ';
            }
            else
                output += char;
        }
        return output;
    }
}
exports.BlazeLanguageService = BlazeLanguageService;