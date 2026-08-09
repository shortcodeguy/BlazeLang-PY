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
exports.completionProvider = completionProvider;
exports.hoverProvider = hoverProvider;
exports.semanticProvider = semanticProvider;
exports.symbolProvider = symbolProvider;
exports.definitionProvider = definitionProvider;
exports.formatter = formatter;
exports.codeActions = codeActions;
const vscode = __importStar(require("vscode"));
const builtins = {
    Show: 'Show(value, ...) — print values followed by a newline.', Print: 'Print(value, ...) — print values without a newline.', Input: 'Input(prompt) — read a line of terminal input.', len: 'len(value) — return collection or string length.', range: 'range(stop), range(start, stop), range(start, stop, step) — create an array of numbers.', type: 'type(value) — return a BlazeLang type name.', Int: 'Int(value) — convert to integer.', Float: 'Float(value) — convert to float.', String: 'String(value) — convert to string.', Bool: 'Bool(value) — convert to boolean.',
};
const keywords = { var: 'Declare a mutable variable.', constant: 'Declare an immutable variable.', Function: 'Declare a value-returning function.', Meta: 'Declare a no-return routine.', Class: 'Declare a class.', Import: 'Import a built-in or local module.', Export: 'Export a declaration from a module.', try: 'Start error-handling block.', throw: 'Raise a runtime error.' };
const standardModules = ['math', 'random', 'date', 'time', 'path', 'system', 'env', 'file', 'http', 'json'];
function completionProvider(service) {
    return { provideCompletionItems(document, position) {
            const range = document.getWordRangeAtPosition(position);
            const items = [];
            for (const [name, detail] of Object.entries({ ...keywords, ...builtins })) {
                const item = new vscode.CompletionItem(name, name in builtins ? vscode.CompletionItemKind.Function : vscode.CompletionItemKind.Keyword);
                item.detail = detail;
                item.range = range;
                items.push(item);
            }
            for (const symbol of service.symbols(document)) {
                const item = new vscode.CompletionItem(symbol.name, completionKindFor(symbol));
                item.detail = symbol.detail;
                item.range = range;
                items.push(item);
            }
            for (const module of standardModules) {
                const item = new vscode.CompletionItem(module, vscode.CompletionItemKind.Module);
                item.detail = 'BlazeLang standard module';
                item.range = range;
                items.push(item);
            }
            return items;
        } };
}
function hoverProvider(service) {
    return { provideHover(document, position) { const range = service.wordRange(document, position); if (!range)
            return; const word = document.getText(range); const symbol = service.symbols(document).find(item => item.name === word); const detail = builtins[word] ?? keywords[word] ?? (symbol ? `${symbol.detail}\n\nDeclared at line ${symbol.range.start.line + 1}.` : undefined); return detail ? new vscode.Hover(new vscode.MarkdownString(`**${word}**\n\n${detail}`), range) : undefined; } };
}
function semanticProvider() {
    const legend = new vscode.SemanticTokensLegend(['keyword', 'class', 'function', 'method', 'variable', 'parameter', 'property', 'string', 'number', 'comment']);
    const token = { keyword: 0, class: 1, function: 2, variable: 4, comment: 9 };
    return [{ provideDocumentSemanticTokens(document) { const builder = new vscode.SemanticTokensBuilder(legend); const declaration = /\b(Class|Function|Meta|var|constant)\s+([A-Za-z_]\w*)/g; for (let line = 0; line < document.lineCount; line += 1) {
                const text = document.lineAt(line).text;
                const comment = text.indexOf('//');
                if (comment >= 0)
                    builder.push(line, comment, text.length - comment, token.comment);
                declaration.lastIndex = 0;
                for (let m = declaration.exec(text); m; m = declaration.exec(text)) {
                    builder.push(line, m.index, m[1].length, token.keyword);
                    builder.push(line, m.index + m[0].lastIndexOf(m[2]), m[2].length, m[1] === 'Class' ? token.class : (m[1] === 'var' || m[1] === 'constant' ? token.variable : token.function));
                }
            } return builder.build(); } }, legend];
}
function symbolProvider(service) {
    return { provideDocumentSymbols(document) { return service.symbols(document).filter(s => s.kind !== 'import').map(s => new vscode.DocumentSymbol(s.name, s.detail ?? '', kindFor(s), s.range, s.selectionRange)); }, provideWorkspaceSymbols(query) { const results = []; for (const document of vscode.workspace.textDocuments.filter(d => d.languageId === 'blazelang'))
            for (const symbol of service.symbols(document))
                if (symbol.name.toLowerCase().includes(query.toLowerCase()))
                    results.push(new vscode.SymbolInformation(symbol.name, kindFor(symbol), symbol.range, document.uri)); return results; } };
}
function definitionProvider(service) {
    return { provideDefinition(document, position) { const range = service.wordRange(document, position); if (!range)
            return; const word = document.getText(range); const symbols = service.symbols(document).filter(s => s.name === word); return symbols.map(s => new vscode.Location(document.uri, s.selectionRange)); }, provideReferences(document, position) { const range = service.wordRange(document, position); if (!range)
            return []; const expression = new RegExp(`\\b${escape(document.getText(range))}\\b`, 'g'); const locations = []; for (let i = 0; i < document.lineCount; i += 1) {
            const text = document.lineAt(i).text;
            for (let m = expression.exec(text); m; m = expression.exec(text))
                locations.push(new vscode.Location(document.uri, new vscode.Range(i, m.index, i, m.index + m[0].length)));
        } return locations; }, prepareRename(document, position) { return service.wordRange(document, position); }, provideRenameEdits(document, position, newName) { const edits = new vscode.WorkspaceEdit(); const range = service.wordRange(document, position); if (!range || !/^[A-Za-z_]\w*$/.test(newName))
            return; const oldName = document.getText(range); for (const location of this.provideReferences(document, position, { includeDeclaration: true }, new vscode.CancellationTokenSource().token))
            edits.replace(location.uri, location.range, newName); return edits; } };
}
function formatter() { return { provideDocumentFormattingEdits(document, options) { let depth = 0; const size = vscode.workspace.getConfiguration('blazelang.format', document.uri).get('indentSize', options.tabSize); const lines = document.getText().split(/\r?\n/).map(raw => { const trimmed = raw.trim(); if (/^[}\]]/.test(trimmed))
        depth = Math.max(0, depth - 1); const line = trimmed ? `${' '.repeat(depth * size)}${trimmed.replace(/\s+$/g, '')}` : ''; if (/[{\[]\s*(?:\/\/.*)?$/.test(trimmed))
        depth += 1; return line; }); return [vscode.TextEdit.replace(new vscode.Range(0, 0, document.lineCount, 0), lines.join('\n'))]; } }; }
function codeActions() { return { provideCodeActions(document, _range, context) { const actions = []; for (const diagnostic of context.diagnostics) {
        if (String(diagnostic.code) === 'BLZ1004') {
            const action = new vscode.CodeAction('Remove duplicate import/declaration', vscode.CodeActionKind.QuickFix);
            action.diagnostics = [diagnostic];
            action.edit = new vscode.WorkspaceEdit();
            action.edit.delete(document.uri, document.lineAt(diagnostic.range.start.line).rangeIncludingLineBreak);
            actions.push(action);
        }
        if (String(diagnostic.code) === 'BLZ1001' && diagnostic.message.includes('semicolon')) {
            const action = new vscode.CodeAction('Remove semicolon', vscode.CodeActionKind.QuickFix);
            action.diagnostics = [diagnostic];
            action.edit = new vscode.WorkspaceEdit();
            action.edit.delete(document.uri, diagnostic.range);
            actions.push(action);
        }
    } return actions; } }; }
function kindFor(symbol) { return { class: vscode.SymbolKind.Class, function: vscode.SymbolKind.Function, meta: vscode.SymbolKind.Method, constant: vscode.SymbolKind.Constant, import: vscode.SymbolKind.Module, variable: vscode.SymbolKind.Variable, parameter: vscode.SymbolKind.Variable }[symbol.kind]; }
function completionKindFor(symbol) { return { class: vscode.CompletionItemKind.Class, function: vscode.CompletionItemKind.Function, meta: vscode.CompletionItemKind.Method, constant: vscode.CompletionItemKind.Constant, import: vscode.CompletionItemKind.Module, variable: vscode.CompletionItemKind.Variable, parameter: vscode.CompletionItemKind.Variable }[symbol.kind]; }
function escape(value) { return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); }
//# sourceMappingURL=providers.js.map