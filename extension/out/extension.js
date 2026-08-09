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
    context.subscriptions.push(
        vscode.languages.registerCompletionItemProvider(selector, (0, providers_1.completionProvider)(service), '.', '"', "'"),
        vscode.languages.registerHoverProvider(selector, (0, providers_1.hoverProvider)(service)),
        vscode.languages.registerDocumentSymbolProvider(selector, (0, providers_1.symbolProvider)(service)),
        vscode.languages.registerWorkspaceSymbolProvider((0, providers_1.symbolProvider)(service)),
        vscode.languages.registerDefinitionProvider(selector, (0, providers_1.definitionProvider)(service)),
        vscode.languages.registerReferenceProvider(selector, (0, providers_1.definitionProvider)(service)),
        vscode.languages.registerRenameProvider(selector, (0, providers_1.definitionProvider)(service)),
        vscode.languages.registerDocumentFormattingEditProvider(selector, (0, providers_1.formatter)()),
        vscode.languages.registerCodeActionsProvider(selector, (0, providers_1.codeActions)(), { providedCodeActionKinds: [vscode.CodeActionKind.QuickFix] })
    );

    const [semanticTokens, legend] = (0, providers_1.semanticProvider)();
    context.subscriptions.push(vscode.languages.registerDocumentSemanticTokensProvider(selector, semanticTokens, legend));

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
        vscode.commands.registerCommand('blazelang.runCurrentFile', () => runCurrentFile())
    );
}

function configuredCommand() {
    return vscode.workspace.getConfiguration('blazelang').get('interpreterPath', '').trim() || 'blz';
}

async function runCurrentFile() {
    const editor = vscode.window.activeTextEditor;
    if (!editor || editor.document.languageId !== 'blazelang') {
        vscode.window.showWarningMessage('Open a BlazeLang (.blz) file first.');
        return;
    }
    if (editor.document.isDirty)
        await editor.document.save();
    const command = configuredCommand();
    const terminal = vscode.window.createTerminal('BlazeLang');
    terminal.show();
    terminal.sendText(`${quote(command)} run ${quote(editor.document.uri.fsPath)}`);
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
function deactivate() { }