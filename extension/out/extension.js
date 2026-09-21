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
exports.activate = activate;
exports.deactivate = deactivate;

const node_child_process_1 = require("node:child_process");
const node_util_1 = require("node:util");
const vscode = __importStar(require("vscode"));
const service_1 = require("./language/service");
const providers_1 = require("./providers");

const selector = { language: 'blazelang', scheme: 'file' };
const execFileAsync = (0, node_util_1.promisify)(node_child_process_1.execFile);

let activeTerminal;
let activeProcess;

function activate(context) {
    const service = new service_1.BlazeLanguageService();
    const diagnostics = vscode.languages.createDiagnosticCollection('blazelang');
    context.subscriptions.push(diagnostics);

    const refresh = (document) => {
        if (!document || document.languageId !== 'blazelang')
            return;
        
        const enabled = vscode.workspace.getConfiguration('blazelang', document.uri).get('enableDiagnostics', true);
        const items = enabled ? service.analyze(document).diagnostics : [];
        diagnostics.set(document.uri, items);
    };

    // Run diagnostics immediately on all currently open documents and active editor
    vscode.workspace.textDocuments.forEach(refresh);
    if (vscode.window.activeTextEditor) {
        refresh(vscode.window.activeTextEditor.document);
    }

    // Subscribe to document lifecycle events
    context.subscriptions.push(
        vscode.workspace.onDidOpenTextDocument(refresh),
        vscode.workspace.onDidChangeTextDocument(event => refresh(event.document)),
        vscode.workspace.onDidCloseTextDocument(document => diagnostics.delete(document.uri)),
        vscode.window.onDidChangeActiveTextEditor(editor => editor && refresh(editor.document))
    );

    // Language Providers
    const completionEnabled = () => vscode.workspace.getConfiguration('blazelang').get('enableCompletion', true);
    const formattingEnabled = () => vscode.workspace.getConfiguration('blazelang').get('enableFormatting', true);

    context.subscriptions.push(
        vscode.languages.registerCompletionItemProvider(selector, wrapCompletion((0, providers_1.completionProvider)(service), completionEnabled), '.', '"', "'", '@'),
        vscode.languages.registerHoverProvider(selector, (0, providers_1.hoverProvider)(service)),
        vscode.languages.registerSignatureHelpProvider(selector, (0, providers_1.signatureHelpProvider)(service), '(', ','),
        vscode.languages.registerDocumentSymbolProvider(selector, (0, providers_1.symbolProvider)(service)),
        vscode.languages.registerWorkspaceSymbolProvider((0, providers_1.symbolProvider)(service)),
        vscode.languages.registerDefinitionProvider(selector, (0, providers_1.definitionProvider)(service)),
        vscode.languages.registerReferenceProvider(selector, (0, providers_1.definitionProvider)(service)),
        vscode.languages.registerRenameProvider(selector, (0, providers_1.definitionProvider)(service)),
        vscode.languages.registerDocumentFormattingEditProvider(selector, wrapFormatter((0, providers_1.formatter)(), formattingEnabled)),
        vscode.languages.registerCodeActionsProvider(selector, (0, providers_1.codeActions)(), { providedCodeActionKinds: [vscode.CodeActionKind.QuickFix] })
    );

    const [semanticTokens, legend] = (0, providers_1.semanticProvider)();
    context.subscriptions.push(vscode.languages.registerDocumentSemanticTokensProvider(selector, semanticTokens, legend));

    // Terminal link provider: makes "file.blz:line:col" locations in BlazeLang
    // CLI output (e.g. "BLZ1002 ParserError\nmain.blz:12:5") clickable, opening
    // the file at that exact line/column.
    context.subscriptions.push(vscode.window.registerTerminalLinkProvider({
        provideTerminalLinks(lineContext) {
            const pattern = /([A-Za-z0-9_.\-\\/: ]+?\.blz):(\d+):(\d+)/g;
            const links = [];
            let match;
            while ((match = pattern.exec(lineContext.line))) {
                links.push({
                    startIndex: match.index,
                    length: match[0].length,
                    tooltip: 'Open in editor',
                    data: { file: match[1].trim(), line: Number(match[2]), column: Number(match[3]) }
                });
            }
            return links;
        },
        async handleTerminalLink(link) {
            const { file, line, column } = link.data;
            const uri = await resolveBlazeFile(file);
            if (!uri)
                return;
            const document = await vscode.workspace.openTextDocument(uri);
            const editor = await vscode.window.showTextDocument(document);
            const position = new vscode.Position(Math.max(0, line - 1), Math.max(0, column - 1));
            editor.selection = new vscode.Selection(position, position);
            editor.revealRange(new vscode.Range(position, position), vscode.TextEditorRevealType.InCenter);
        }
    }));

    // Status Bar Item
    const status = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);
    status.name = 'BlazeLang';
    status.text = '$(flame) BlazeLang Ready';
    status.tooltip = 'BlazeLang language tools are active';
    status.show();
    context.subscriptions.push(status);

    void runVersion(configuredCommand()).then(version => {
        if (version) {
            status.text = `$(flame) BlazeLang ${version}`;
            status.tooltip = `BlazeLang interpreter ${version}`;
        }
    });

    // Registered Commands
    context.subscriptions.push(
        vscode.commands.registerCommand('blazelang.formatDocument', () => vscode.commands.executeCommand('editor.action.formatDocument')),
        vscode.commands.registerCommand('blazelang.restartLanguageServer', () => { 
            service.clear(); 
            vscode.workspace.textDocuments.forEach(refresh); 
            vscode.window.setStatusBarMessage('BlazeLang language service restarted.', 3000); 
        }),
        vscode.commands.registerCommand('blazelang.newFile', async () => { 
            const document = await vscode.workspace.openTextDocument({ language: 'blazelang', content: 'Show("Hello, BlazeLang!")\n' }); 
            await vscode.window.showTextDocument(document); 
        }),
        vscode.commands.registerCommand('blazelang.showVersion', async () => { 
            const command = configuredCommand(); 
            const version = await runVersion(command); 
            vscode.window.showInformationMessage(version ? `BlazeLang ${version}` : 'BlazeLang tools are ready. Configure blazelang.interpreterPath to detect a runtime version.'); 
        }),
        vscode.commands.registerCommand('blazelang.runCurrentFile', () => runCurrentFile()),
        vscode.commands.registerCommand('blazelang.runFile', () => runCurrentFile()),
        vscode.commands.registerCommand('blazelang.runFileWithArgs', () => runCurrentFile({ withArgs: true })),
        vscode.commands.registerCommand('blazelang.runProject', () => runProject()),
        vscode.commands.registerCommand('blazelang.stop', () => stopRunning())
    );

    context.subscriptions.push({ dispose: () => stopRunning(true) });
}

function configuredCommand() {
    const cliPath = vscode.workspace.getConfiguration('blazelang').get('cliPath', '').trim();
    if (cliPath)
        return cliPath;
    const legacy = vscode.workspace.getConfiguration('blazelang').get('interpreterPath', '').trim();
    return legacy || 'blz';
}

function autoSaveEnabled() {
    return vscode.workspace.getConfiguration('blazelang').get('run.autoSave', true);
}

/** Verify the configured BlazeLang CLI is actually resolvable before we try to use it. */
async function ensureCliAvailable(command) {
    try {
        await execFileAsync(command, ['version'], { windowsHide: true, timeout: 4000 });
        return true;
    }
    catch (error) {
        const notFound = error && (error.code === 'ENOENT' || /not recognized|not found|no such file/i.test(String(error.message)));
        if (notFound) {
            const choice = await vscode.window.showErrorMessage(`BlazeLang CLI ('${command}') was not found. Install BlazeLang and make sure 'blz' is on your PATH, or set "blazelang.cliPath" to its full location.`, 'Open Settings');
            if (choice === 'Open Settings')
                await vscode.commands.executeCommand('workbench.action.openSettings', 'blazelang.cliPath');
            return false;
        }
        // Any other error (e.g. non-zero exit from `version`) still means the
        // executable itself was found and is runnable.
        return true;
    }
}

function getOrCreateTerminal() {
    if (activeTerminal && vscode.window.terminals.includes(activeTerminal))
        return activeTerminal;
    activeTerminal = vscode.window.createTerminal('BlazeLang');
    return activeTerminal;
}

async function runCurrentFile(options = {}) {
    const editor = vscode.window.activeTextEditor;
    if (!editor || editor.document.languageId !== 'blazelang') {
        vscode.window.showWarningMessage('Open a BlazeLang (.blz) file first.');
        return;
    }
    if (editor.document.isDirty && autoSaveEnabled())
        await editor.document.save();

    const command = configuredCommand();
    if (!(await ensureCliAvailable(command)))
        return;

    let extraArgs = '';
    if (options.withArgs) {
        const input = await vscode.window.showInputBox({
            prompt: 'Arguments to pass to your BlazeLang program',
            placeHolder: 'e.g. --verbose input.txt'
        });
        if (input === undefined)
            return; // user cancelled
        if (input.trim())
            extraArgs = ` -- ${input.trim()}`;
    }

    const terminal = getOrCreateTerminal();
    terminal.show();
    terminal.sendText(`${commandToken(command)} run ${quote(editor.document.uri.fsPath)}${extraArgs}`);
}

async function runProject() {
    // A BlazeLang "project" has no required manifest file (see language spec:
    // a single .blz file is a valid project on its own). We look for a
    // conventional entry point, then fall back to the active file.
    const entryNames = ['main.blz', 'index.blz', 'app.blz'];
    let entryUri;
    for (const name of entryNames) {
        const found = await vscode.workspace.findFiles(`**/${name}`, '**/node_modules/**', 1);
        if (found.length > 0) {
            entryUri = found[0];
            break;
        }
    }
    if (!entryUri) {
        const editor = vscode.window.activeTextEditor;
        if (editor && editor.document.languageId === 'blazelang')
            entryUri = editor.document.uri;
    }
    if (!entryUri) {
        vscode.window.showWarningMessage('No BlazeLang entry point (main.blz / index.blz / app.blz) was found, and no .blz file is active.');
        return;
    }

    const document = await vscode.workspace.openTextDocument(entryUri);
    if (document.isDirty && autoSaveEnabled())
        await document.save();

    const command = configuredCommand();
    if (!(await ensureCliAvailable(command)))
        return;

    const terminal = getOrCreateTerminal();
    terminal.show();
    terminal.sendText(`${commandToken(command)} run ${quote(entryUri.fsPath)}`);
}

function stopRunning(silent = false) {
    if (activeTerminal && vscode.window.terminals.includes(activeTerminal)) {
        // Send Ctrl+C to interrupt whatever the terminal is running, then
        // dispose it. This only ever touches the extension's own
        // 'BlazeLang' terminal, never other terminals in the workspace.
        activeTerminal.sendText('\u0003', false);
        activeTerminal.dispose();
        activeTerminal = undefined;
        if (!silent)
            vscode.window.setStatusBarMessage('BlazeLang: stopped.', 3000);
    }
    else if (!silent) {
        vscode.window.showInformationMessage('No running BlazeLang process to stop.');
    }
}

async function resolveBlazeFile(rawPath) {
    const folders = vscode.workspace.workspaceFolders ?? [];
    const path = require('node:path');
    if (path.isAbsolute(rawPath)) {
        return vscode.Uri.file(rawPath);
    }
    for (const folder of folders) {
        const candidate = vscode.Uri.joinPath(folder.uri, rawPath);
        try {
            await vscode.workspace.fs.stat(candidate);
            return candidate;
        }
        catch {
            continue;
        }
    }
    const editor = vscode.window.activeTextEditor;
    if (editor) {
        const path2 = require('node:path');
        return vscode.Uri.file(path2.join(path2.dirname(editor.document.uri.fsPath), rawPath));
    }
    return undefined;
}

function wrapCompletion(provider, isEnabled) {
    return { provideCompletionItems(...args) { return isEnabled() ? provider.provideCompletionItems(...args) : []; } };
}

function wrapFormatter(provider, isEnabled) {
    return { provideDocumentFormattingEdits(...args) { return isEnabled() ? provider.provideDocumentFormattingEdits(...args) : []; } };
}

async function runVersion(command) {
    try {
        const { stdout } = await execFileAsync(command, ['version'], { windowsHide: true, timeout: 4000 });
        return stdout.trim().split(/\r?\n/).find(Boolean);
    }
    catch {
        return undefined;
    }
}

function quote(value) { return `"${value.replace(/"/g, '\\"')}"`; }

/**
 * Build the invocable token for the CLI executable. Only quotes when the
 * path actually contains a space (the common 'blz' case is left bare), and
 * on Windows prefixes the PowerShell call operator '&' when quoting is
 * needed -- PowerShell (the default integrated shell on Windows) treats a
 * bare quoted string as an expression, not a command, and errors with
 * "Unexpected token 'run'" otherwise.
 */
function commandToken(command) {
    if (!/\s/.test(command))
        return command;
    return process.platform === 'win32' ? `& ${quote(command)}` : quote(command);
}
function deactivate() { }