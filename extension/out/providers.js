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
exports.signatureHelpProvider = signatureHelpProvider;
exports.semanticProvider = semanticProvider;
exports.symbolProvider = symbolProvider;
exports.definitionProvider = definitionProvider;
exports.formatter = formatter;
exports.codeActions = codeActions;

const vscode = __importStar(require("vscode"));

// Rich Python-style Builtins Metadata
const builtins = {
    Show: {
        sig: 'Show(*args)',
        snippet: 'Show(${1:value})',
        doc: 'Prints one or more values to standard output with automatic spacing and trailing newline.\n\n```blaze\nShow("Count:", 42, true)\n```'
    },
    Print: {
        sig: 'Print(*args)',
        snippet: 'Print(${1:value})',
        doc: 'Prints values to standard output without appending a trailing newline.\n\n```blaze\nPrint("Processing...")\n```'
    },
    Input: {
        sig: 'Input(prompt: String) -> String',
        snippet: 'Input("${1:Enter prompt: }")',
        doc: 'Reads a line of user input from standard terminal input.\n\n```blaze\nvar name = Input("Enter name: ")\n```'
    },
    len: {
        sig: 'len(collection: Array | Object | String) -> Integer',
        snippet: 'len(${1:collection})',
        doc: 'Returns the number of elements in an array, keys in an object, or characters in a string.\n\n```blaze\nvar count = len([1, 2, 3]) // 3\n```'
    },
    range: {
        sig: 'range(start: Integer, stop: Integer, step: Integer = 1) -> Array',
        snippet: 'range(${1:0}, ${2:10})',
        doc: 'Generates an arithmetic sequence of numbers from start to stop (exclusive).\n\n```blaze\nfor i in range(0, 10) {\n    Show(i)\n}\n```'
    },
    type: {
        sig: 'type(value: Any) -> String',
        snippet: 'type(${1:value})',
        doc: 'Returns the runtime data type name of a value ("Integer", "Float", "String", "Boolean", "Array", "Object", "Null").'
    },
    Int: {
        sig: 'Int(value: Any) -> Integer',
        snippet: 'Int(${1:value})',
        doc: 'Converts a string or float into a 64-bit signed integer.'
    },
    Float: {
        sig: 'Float(value: Any) -> Float',
        snippet: 'Float(${1:value})',
        doc: 'Converts a string or integer into a double-precision floating point number.'
    },
    String: {
        sig: 'String(value: Any) -> String',
        snippet: 'String(${1:value})',
        doc: 'Converts any value into its canonical string representation.'
    },
    Bool: {
        sig: 'Bool(value: Any) -> Boolean',
        snippet: 'Bool(${1:value})',
        doc: 'Evaluates the truthiness of any value (0 and null evaluate to false).'
    },
    Upper: {
        sig: 'Upper(str: String) -> String',
        snippet: 'Upper(${1:str})',
        doc: 'Converts all ASCII characters in a string to uppercase.'
    },
    Lower: {
        sig: 'Lower(str: String) -> String',
        snippet: 'Lower(${1:str})',
        doc: 'Converts all ASCII characters in a string to lowercase.'
    },
    Trim: {
        sig: 'Trim(str: String) -> String',
        snippet: 'Trim(${1:str})',
        doc: 'Removes leading and trailing whitespace characters.'
    },
    Split: {
        sig: 'Split(str: String, delimiter: String) -> Array[String]',
        snippet: 'Split(${1:str}, "${2:delimiter}")',
        doc: 'Splits a string into an array of substrings based on a delimiter.'
    },
    Join: {
        sig: 'Join(list: Array, delimiter: String) -> String',
        snippet: 'Join(${1:list}, "${2:delimiter}")',
        doc: 'Concatenates an array of elements into a single string separated by delimiter.'
    },
    Replace: {
        sig: 'Replace(str: String, target: String, replacement: String) -> String',
        snippet: 'Replace(${1:str}, "${2:target}", "${3:replacement}")',
        doc: 'Replaces occurrences of target substring with replacement.'
    },
    Contains: {
        sig: 'Contains(collection: Array | String, item: Any) -> Boolean',
        snippet: 'Contains(${1:collection}, ${2:item})',
        doc: 'Returns true if collection contains the specified item or substring.'
    },
    StartsWith: {
        sig: 'StartsWith(str: String, prefix: String) -> Boolean',
        snippet: 'StartsWith(${1:str}, "${2:prefix}")',
        doc: 'Returns true if string starts with prefix.'
    },
    EndsWith: {
        sig: 'EndsWith(str: String, suffix: String) -> Boolean',
        snippet: 'EndsWith(${1:str}, "${2:suffix}")',
        doc: 'Returns true if string ends with suffix.'
    },
    Find: {
        sig: 'Find(str: String, target: String) -> Integer',
        snippet: 'Find(${1:str}, "${2:target}")',
        doc: 'Returns the 0-based index of target in str, or -1 if not found.'
    },
    Reverse: {
        sig: 'Reverse(collection: Array | String) -> Array | String',
        snippet: 'Reverse(${1:collection})',
        doc: 'Returns a reversed copy of the array or string.'
    },
    Random: {
        sig: 'Random(min: Integer = 0, max: Integer = 1) -> Float | Integer',
        snippet: 'Random(${1:0}, ${2:100})',
        doc: 'Returns a random number between min and max.'
    },
    Sleep: {
        sig: 'Sleep(milliseconds: Integer)',
        snippet: 'Sleep(${1:1000})',
        doc: 'Suspends the execution of the current thread for the specified milliseconds.'
    },
    Exit: {
        sig: 'Exit(code: Integer = 0)',
        snippet: 'Exit(${1:0})',
        doc: 'Terminates the program process with an exit status code.'
    },
    eval: {
        sig: 'eval(expression: String) -> Any',
        snippet: 'eval(${1:expression})',
        doc: 'Dynamically parses and evaluates a BlazeLang expression string.'
    },
    evalFile: {
        sig: 'evalFile(path: String) -> Any',
        snippet: 'evalFile("${1:path.blz}")',
        doc: 'Loads and executes a BlazeLang source file dynamically.'
    }
};

// Keywords with rich docs & snippet completion expansions
const keywords = {
    var: { sig: 'var name = value', doc: 'Declares a mutable variable.', snippet: 'var ${1:name} = ${2:value}' },
    constant: { sig: 'constant NAME = value', doc: 'Declares an immutable constant (reassignment causes error).', snippet: 'constant ${1:NAME} = ${2:value}' },
    bind: { sig: 'bind state = initialValue', doc: 'Declares a reactive state container with .value, .previous, .origin, and .history tracking.', snippet: 'bind ${1:state} = ${2:initialValue}' },
    Function: { sig: 'Function Name(params...) { ... }', doc: 'Declares a named function with return value support.', snippet: 'Function ${1:name}(${2:params}) {\n\t${0}\n}' },
    Class: { sig: 'Class Name { Constructor(...) { ... } }', doc: 'Declares an object-oriented class.', snippet: 'Class ${1:Name} {\n\tConstructor(${2:params}) {\n\t\t${0}\n\t}\n}' },
    Struct: { sig: 'Struct Name { field = default, ... }', doc: 'Declares a lightweight structured record.', snippet: 'Struct ${1:Name} {\n\t${0:field = default}\n}' },
    Enum: { sig: 'Enum Name { A, B, C }', doc: 'Declares a set of named integer constants.', snippet: 'Enum ${1:Name} {\n\t${0:Value}\n}' },
    Constructor: { sig: 'Constructor(params...) { ... }', doc: 'Initializes instance fields for a Class.', snippet: 'Constructor(${1:params}) {\n\t${0}\n}' },
    if: { sig: 'if condition { ... } else { ... }', doc: 'Conditional branching control flow.', snippet: 'if ${1:condition} {\n\t${0}\n}' },
    else: { sig: 'else { ... }', doc: 'Fallback branch for conditional statements.', snippet: 'else {\n\t${0}\n}' },
    while: { sig: 'while condition { ... }', doc: 'Executes a block repeatedly while condition is true.', snippet: 'while ${1:condition} {\n\t${0}\n}' },
    for: { sig: 'for item in collection { ... }', doc: 'Iterates through an array, range, or object.', snippet: 'for ${1:item} in ${2:collection} {\n\t${0}\n}' },
    in: { sig: 'item in collection', doc: 'Iteration membership keyword.', snippet: 'in ${1:collection}' },
    return: { sig: 'return value', doc: 'Returns a value from a function.', snippet: 'return ${0}' },
    Break: { sig: 'Break', doc: 'Terminates the innermost loop immediately.', snippet: 'Break' },
    Continue: { sig: 'Continue', doc: 'Skips to the next iteration of the loop.', snippet: 'Continue' },
    Import: { sig: 'Import Module from "path_or_pkg"', doc: 'Imports a standard or package module.', snippet: 'Import ${1:Module} from "${2:module}"' },
    Export: { sig: 'Export Symbol', doc: 'Exports a function, class, or variable from module.', snippet: 'Export ${1:Symbol}' },
    try: { sig: 'try { ... } catch err { ... } finally { ... }', doc: 'Structured exception handling block.', snippet: 'try {\n\t${1}\n} catch ${2:err} {\n\t${0}\n}' },
    catch: { sig: 'catch error { ... }', doc: 'Catches and handles an exception.', snippet: 'catch ${1:error} {\n\t${0}\n}' },
    finally: { sig: 'finally { ... }', doc: 'Guaranteed execution block following try/catch.', snippet: 'finally {\n\t${0}\n}' },
    throw: { sig: 'throw "Error description"', doc: 'Raises a runtime exception.', snippet: 'throw "${1:error message}"' },
    this: { sig: 'this.property', doc: 'Refers to the current class instance.', snippet: 'this.' },
    and: { sig: 'a and b', doc: 'Logical AND operator.', snippet: 'and ' },
    or: { sig: 'a or b', doc: 'Logical OR operator.', snippet: 'or ' },
    not: { sig: 'not a', doc: 'Logical NOT operator.', snippet: 'not ' },
    true: { sig: 'true', doc: 'Boolean truth literal.', snippet: 'true' },
    false: { sig: 'false', doc: 'Boolean false literal.', snippet: 'false' },
    null: { sig: 'null', doc: 'Null reference literal.', snippet: 'null' }
};

// Standard Library Modules & Deep Member API Definitions
const standardModules = {
    Math: {
        doc: 'Mathematical constants and functions.',
        members: {
            sqrt: { sig: 'Math.sqrt(x: Number) -> Float', snippet: 'Math.sqrt(${1:x})', doc: 'Square root of x.' },
            pow: { sig: 'Math.pow(base: Number, exp: Number) -> Number', snippet: 'Math.pow(${1:base}, ${2:exp})', doc: 'Base raised to exponent.' },
            sin: { sig: 'Math.sin(rad: Number) -> Float', snippet: 'Math.sin(${1:rad})', doc: 'Sine of angle in radians.' },
            cos: { sig: 'Math.cos(rad: Number) -> Float', snippet: 'Math.cos(${1:rad})', doc: 'Cosine of angle in radians.' },
            tan: { sig: 'Math.tan(rad: Number) -> Float', snippet: 'Math.tan(${1:rad})', doc: 'Tangent of angle in radians.' },
            abs: { sig: 'Math.abs(x: Number) -> Number', snippet: 'Math.abs(${1:x})', doc: 'Absolute value.' },
            floor: { sig: 'Math.floor(x: Number) -> Integer', snippet: 'Math.floor(${1:x})', doc: 'Largest integer <= x.' },
            ceil: { sig: 'Math.ceil(x: Number) -> Integer', snippet: 'Math.ceil(${1:x})', doc: 'Smallest integer >= x.' },
            round: { sig: 'Math.round(x: Number) -> Integer', snippet: 'Math.round(${1:x})', doc: 'Rounds to nearest integer.' },
            min: { sig: 'Math.min(a: Number, b: Number) -> Number', snippet: 'Math.min(${1:a}, ${2:b})', doc: 'Minimum of two numbers.' },
            max: { sig: 'Math.max(a: Number, b: Number) -> Number', snippet: 'Math.max(${1:a}, ${2:b})', doc: 'Maximum of two numbers.' },
            exp: { sig: 'Math.exp(x: Number) -> Float', snippet: 'Math.exp(${1:x})', doc: 'Natural exponential e^x.' },
            log: { sig: 'Math.log(x: Number) -> Float', snippet: 'Math.log(${1:x})', doc: 'Natural logarithm ln(x).' },
            PI: { sig: 'Math.PI -> Float', snippet: 'Math.PI', doc: 'Ratio of circumference to diameter (3.1415926535...)' },
            E: { sig: 'Math.E -> Float', snippet: 'Math.E', doc: 'Base of natural logarithms (2.7182818284...)' }
        }
    },
    Vector: {
        doc: 'Native AI vector mathematics and similarity metrics.',
        members: {
            DotProduct: { sig: 'Vector.DotProduct(a: Array[Float], b: Array[Float]) -> Float', snippet: 'Vector.DotProduct(${1:a}, ${2:b})', doc: 'Computes sum of element-wise products.' },
            CosineSimilarity: { sig: 'Vector.CosineSimilarity(a: Array[Float], b: Array[Float]) -> Float', snippet: 'Vector.CosineSimilarity(${1:a}, ${2:b})', doc: 'Computes cosine angle similarity between two embedding vectors.' },
            Magnitude: { sig: 'Vector.Magnitude(v: Array[Float]) -> Float', snippet: 'Vector.Magnitude(${1:v})', doc: 'Computes Euclidean length (L2 norm) of a vector.' },
            Normalize: { sig: 'Vector.Normalize(v: Array[Float]) -> Array[Float]', snippet: 'Vector.Normalize(${1:v})', doc: 'Returns unit-length normalized vector (norm = 1.0).' },
            Add: { sig: 'Vector.Add(a: Array, b: Array) -> Array', snippet: 'Vector.Add(${1:a}, ${2:b})', doc: 'Element-wise vector addition.' },
            Subtract: { sig: 'Vector.Subtract(a: Array, b: Array) -> Array', snippet: 'Vector.Subtract(${1:a}, ${2:b})', doc: 'Element-wise vector subtraction.' }
        }
    },
    NN: {
        doc: 'Neural network Multi-Layer Perceptron (MLP) layers and activations.',
        members: {
            Linear: { sig: 'NN.Linear(in_features: Integer, out_features: Integer) -> Layer', snippet: 'NN.Linear(${1:in_features}, ${2:out_features})', doc: 'Initializes dense linear feed-forward layer.' },
            Forward: { sig: 'NN.Forward(inputs: Array, weights: Array, bias: Array) -> Array', snippet: 'NN.Forward(${1:inputs}, ${2:weights}, ${3:bias})', doc: 'Performs matrix dot-product forward pass.' },
            Sigmoid: { sig: 'NN.Sigmoid(z: Number) -> Float', snippet: 'NN.Sigmoid(${1:z})', doc: 'Sigmoid activation 1 / (1 + exp(-z)).' },
            ReLU: { sig: 'NN.ReLU(z: Number) -> Number', snippet: 'NN.ReLU(${1:z})', doc: 'Rectified Linear Unit max(0, z).' },
            Softmax: { sig: 'NN.Softmax(logits: Array[Number]) -> Array[Float]', snippet: 'NN.Softmax(${1:logits})', doc: 'Normalizes logits into probability distribution.' }
        }
    },
    ML: {
        doc: 'Statistical machine learning algorithms.',
        members: {
            LinearRegression: { sig: 'ML.LinearRegression() -> Model', snippet: 'ML.LinearRegression()', doc: 'Ordinary least squares linear regression model.' },
            LogisticRegression: { sig: 'ML.LogisticRegression() -> Model', snippet: 'ML.LogisticRegression()', doc: 'Binary classification logistic regression.' },
            Fit: { sig: 'ML.Fit(model: Model, X: Array, y: Array)', snippet: 'ML.Fit(${1:model}, ${2:X}, ${3:y})', doc: 'Trains model on feature matrix X and target y.' },
            Predict: { sig: 'ML.Predict(model: Model, X: Array) -> Array', snippet: 'ML.Predict(${1:model}, ${2:X})', doc: 'Generates predictions for inputs.' },
            Score: { sig: 'ML.Score(y_true: Array, y_pred: Array) -> Float', snippet: 'ML.Score(${1:y_true}, ${2:y_pred})', doc: 'Computes R2 or accuracy classification score.' }
        }
    },
    Tokenizer: {
        doc: 'LLM sub-word vocabulary tokenizer and encoding engine.',
        members: {
            Create: { sig: 'Tokenizer.Create(vocab: Object) -> Tokenizer', snippet: 'Tokenizer.Create(${1:vocab})', doc: 'Creates vocabulary tokenizer instance.' },
            Encode: { sig: 'Tokenizer.Encode(text: String) -> Array[Integer]', snippet: 'Tokenizer.Encode(${1:text})', doc: 'Encodes text string into integer token IDs with BOS/EOS framing.' },
            Decode: { sig: 'Tokenizer.Decode(ids: Array[Integer]) -> String', snippet: 'Tokenizer.Decode(${1:ids})', doc: 'Decodes token ID sequence back into text string.' },
            Lookup: { sig: 'Tokenizer.Lookup(token: String) -> Integer', snippet: 'Tokenizer.Lookup("${1:token}")', doc: 'Gets integer ID for a token word.' }
        }
    },
    Json: {
        doc: 'JSON parsing and serialization.',
        members: {
            Parse: { sig: 'Json.Parse(jsonString: String) -> Any', snippet: 'Json.Parse(${1:jsonString})', doc: 'Parses JSON text into objects, arrays, and primitive values.' },
            Stringify: { sig: 'Json.Stringify(value: Any) -> String', snippet: 'Json.Stringify(${1:value})', doc: 'Serializes a BlazeLang value into JSON text.' },
            Pretty: { sig: 'Json.Pretty(value: Any, indent: Integer = 2) -> String', snippet: 'Json.Pretty(${1:value}, ${2:2})', doc: 'Formats value as human-readable indented JSON.' }
        }
    },
    Http: {
        doc: 'HTTP client for REST and web APIs.',
        members: {
            Get: { sig: 'Http.Get(url: String, headers: Object = {}) -> HttpResponse', snippet: 'Http.Get("${1:https://api.example.com}")', doc: 'Performs HTTP GET request.' },
            Post: { sig: 'Http.Post(url: String, body: String | Object, headers: Object = {}) -> HttpResponse', snippet: 'Http.Post("${1:https://api.example.com}", ${2:body})', doc: 'Performs HTTP POST request.' },
            Put: { sig: 'Http.Put(url: String, body: String | Object, headers: Object = {}) -> HttpResponse', snippet: 'Http.Put("${1:https://api.example.com}", ${2:body})', doc: 'Performs HTTP PUT request.' },
            Delete: { sig: 'Http.Delete(url: String, headers: Object = {}) -> HttpResponse', snippet: 'Http.Delete("${1:https://api.example.com}")', doc: 'Performs HTTP DELETE request.' },
            Head: { sig: 'Http.Head(url: String) -> HttpResponse', snippet: 'Http.Head("${1:https://api.example.com}")', doc: 'Performs HTTP HEAD request.' },
            Download: { sig: 'Http.Download(url: String, destPath: String) -> Boolean', snippet: 'Http.Download("${1:url}", "${2:destPath}")', doc: 'Downloads remote resource directly to file on disk.' }
        }
    },
    HttpServer: {
        doc: 'Native concurrent HTTP server daemon.',
        members: {
            Create: { sig: 'HttpServer.Create(port: Integer = 8080) -> Server', snippet: 'HttpServer.Create(${1:8080})', doc: 'Initializes an HTTP server listening on port.' },
            Get: { sig: 'server.Get(path: String, handler: Function(req, res))', snippet: 'server.Get("${1:/}", Function(req, res) {\n\t${0:res.Send("OK")}\n})', doc: 'Registers GET route endpoint.' },
            Post: { sig: 'server.Post(path: String, handler: Function(req, res))', snippet: 'server.Post("${1:/}", Function(req, res) {\n\t${0:res.Send("OK")}\n})', doc: 'Registers POST route endpoint.' },
            Listen: { sig: 'server.Listen()', snippet: 'server.Listen()', doc: 'Starts server event loop accepting connections.' }
        }
    },
    File: {
        doc: 'File system read/write operations.',
        members: {
            Read: { sig: 'File.Read(path: String) -> String', snippet: 'File.Read("${1:filepath}")', doc: 'Reads entire file content as UTF-8 string.' },
            Write: { sig: 'File.Write(path: String, content: String) -> Boolean', snippet: 'File.Write("${1:filepath}", ${2:content})', doc: 'Writes text to file (overwriting existing content).' },
            Append: { sig: 'File.Append(path: String, content: String) -> Boolean', snippet: 'File.Append("${1:filepath}", ${2:content})', doc: 'Appends text to the end of a file.' },
            Exists: { sig: 'File.Exists(path: String) -> Boolean', snippet: 'File.Exists("${1:filepath}")', doc: 'Checks if file or directory exists.' },
            Delete: { sig: 'File.Delete(path: String) -> Boolean', snippet: 'File.Delete("${1:filepath}")', doc: 'Deletes a file from disk.' },
            ListDir: { sig: 'File.ListDir(dirPath: String) -> Array[String]', snippet: 'File.ListDir("${1:dirPath}")', doc: 'Lists entries in a directory.' }
        }
    },
    Process: {
        doc: 'Child process execution and lifecycle management.',
        members: {
            Run: { sig: 'Process.Run(command: String, args: Array[String] = []) -> Object', snippet: 'Process.Run("${1:command}", [${2}])', doc: 'Executes command synchronously and returns { stdout, stderr, exit_code }.' },
            Start: { sig: 'Process.Start(command: String, args: Array[String] = []) -> Handle', snippet: 'Process.Start("${1:command}", [${2}])', doc: 'Launches process in background and returns process handle.' },
            Wait: { sig: 'Process.Wait(handle: Handle) -> Integer', snippet: 'Process.Wait(${1:handle})', doc: 'Waits for process handle to finish and returns exit code.' },
            Kill: { sig: 'Process.Kill(handle: Handle) -> Boolean', snippet: 'Process.Kill(${1:handle})', doc: 'Forcefully terminates running background process.' },
            PID: { sig: 'Process.PID(handle: Handle) -> Integer', snippet: 'Process.PID(${1:handle})', doc: 'Gets process ID.' },
            IsRunning: { sig: 'Process.IsRunning(handle: Handle) -> Boolean', snippet: 'Process.IsRunning(${1:handle})', doc: 'Returns true if process is actively executing.' }
        }
    },
    Date: {
        doc: 'Date, time, and timestamp utilities.',
        members: {
            Now: { sig: 'Date.Now() -> DateObject', snippet: 'Date.Now()', doc: 'Returns current date and time.' },
            Timestamp: { sig: 'Date.Timestamp() -> Integer', snippet: 'Date.Timestamp()', doc: 'Returns Unix epoch timestamp in seconds.' },
            Format: { sig: 'Date.Format(date: DateObject, formatString: String) -> String', snippet: 'Date.Format(${1:date}, "${2:%Y-%m-%d}")', doc: 'Formats date according to format string.' }
        }
    },
    Time: {
        doc: 'Time and timer utilities.',
        members: {
            Now: { sig: 'Time.Now() -> Float', snippet: 'Time.Now()', doc: 'High-resolution monotonic timer in seconds.' },
            Sleep: { sig: 'Time.Sleep(ms: Integer)', snippet: 'Time.Sleep(${1:1000})', doc: 'Pauses execution for specified milliseconds.' }
        }
    },
    System: {
        doc: 'System environment and host runtime inspection.',
        members: {
            OS: { sig: 'System.OS() -> String', snippet: 'System.OS()', doc: 'Returns host OS ("windows", "linux", "darwin").' },
            Arch: { sig: 'System.Arch() -> String', snippet: 'System.Arch()', doc: 'Returns CPU architecture ("x64", "arm64").' },
            Args: { sig: 'System.Args() -> Array[String]', snippet: 'System.Args()', doc: 'Returns CLI arguments passed to script.' },
            Exit: { sig: 'System.Exit(code: Integer = 0)', snippet: 'System.Exit(${1:0})', doc: 'Exits process with status code.' }
        }
    },
    Env: {
        doc: 'Environment variables access.',
        members: {
            Get: { sig: 'Env.Get(key: String) -> String | Null', snippet: 'Env.Get("${1:VAR_NAME}")', doc: 'Gets value of environment variable.' },
            Set: { sig: 'Env.Set(key: String, value: String) -> Boolean', snippet: 'Env.Set("${1:VAR_NAME}", "${2:value}")', doc: 'Sets environment variable.' }
        }
    },
    Random: {
        doc: 'Random number generators and sequence shuffling.',
        members: {
            Int: { sig: 'Random.Int(min: Integer, max: Integer) -> Integer', snippet: 'Random.Int(${1:1}, ${2:100})', doc: 'Random integer between min and max inclusive.' },
            Float: { sig: 'Random.Float(min: Float = 0.0, max: Float = 1.0) -> Float', snippet: 'Random.Float(${1:0.0}, ${2:1.0})', doc: 'Random float.' },
            Choice: { sig: 'Random.Choice(list: Array) -> Any', snippet: 'Random.Choice(${1:list})', doc: 'Returns a random element from list.' },
            Shuffle: { sig: 'Random.Shuffle(list: Array) -> Array', snippet: 'Random.Shuffle(${1:list})', doc: 'Returns a randomly shuffled copy of list.' }
        }
    },
    Crypto: {
        doc: 'Cryptographic hashing, HMAC message authentication, encoding, UUID, and secure password hashing.',
        members: {
            MD5: { sig: 'Crypto.MD5(data: String) -> String', snippet: 'Crypto.MD5(${1:data})', doc: 'Computes 128-bit MD5 hex hash digest.' },
            SHA1: { sig: 'Crypto.SHA1(data: String) -> String', snippet: 'Crypto.SHA1(${1:data})', doc: 'Computes 160-bit SHA-1 hex hash digest.' },
            SHA256: { sig: 'Crypto.SHA256(data: String) -> String', snippet: 'Crypto.SHA256(${1:data})', doc: 'Computes 256-bit SHA-256 hex hash digest.' },
            SHA512: { sig: 'Crypto.SHA512(data: String) -> String', snippet: 'Crypto.SHA512(${1:data})', doc: 'Computes 512-bit SHA-512 hex hash digest.' },
            HMAC_MD5: { sig: 'Crypto.HMAC_MD5(key: String, message: String) -> String', snippet: 'Crypto.HMAC_MD5(${1:key}, ${2:message})', doc: 'Computes HMAC-MD5 keyed-hash message authentication code.' },
            HMAC_SHA1: { sig: 'Crypto.HMAC_SHA1(key: String, message: String) -> String', snippet: 'Crypto.HMAC_SHA1(${1:key}, ${2:message})', doc: 'Computes HMAC-SHA1 keyed-hash message authentication code.' },
            HMAC_SHA256: { sig: 'Crypto.HMAC_SHA256(key: String, message: String) -> String', snippet: 'Crypto.HMAC_SHA256(${1:key}, ${2:message})', doc: 'Computes HMAC-SHA256 keyed-hash message authentication code.' },
            HMAC_SHA512: { sig: 'Crypto.HMAC_SHA512(key: String, message: String) -> String', snippet: 'Crypto.HMAC_SHA512(${1:key}, ${2:message})', doc: 'Computes HMAC-SHA512 keyed-hash message authentication code.' },
            Base64Encode: { sig: 'Crypto.Base64Encode(data: String) -> String', snippet: 'Crypto.Base64Encode(${1:data})', doc: 'Encodes text or binary data into standard Base64 format.' },
            Base64Decode: { sig: 'Crypto.Base64Decode(encoded: String) -> String', snippet: 'Crypto.Base64Decode(${1:encoded})', doc: 'Decodes standard Base64 string back into original data.' },
            Base64UrlEncode: { sig: 'Crypto.Base64UrlEncode(data: String) -> String', snippet: 'Crypto.Base64UrlEncode(${1:data})', doc: 'Encodes data into URL-safe Base64 (RFC 4648 §5).' },
            Base64UrlDecode: { sig: 'Crypto.Base64UrlDecode(encoded: String) -> String', snippet: 'Crypto.Base64UrlDecode(${1:encoded})', doc: 'Decodes URL-safe Base64 string.' },
            HexEncode: { sig: 'Crypto.HexEncode(data: String) -> String', snippet: 'Crypto.HexEncode(${1:data})', doc: 'Encodes string into lowercase hex representation.' },
            HexDecode: { sig: 'Crypto.HexDecode(hex: String) -> String', snippet: 'Crypto.HexDecode(${1:hex})', doc: 'Decodes hex string back into original string.' },
            RandomBytes: { sig: 'Crypto.RandomBytes(length: Integer = 32) -> String', snippet: 'Crypto.RandomBytes(${1:32})', doc: 'Generates cryptographically secure random bytes as hex string.' },
            RandomHex: { sig: 'Crypto.RandomHex(length: Integer = 16) -> String', snippet: 'Crypto.RandomHex(${1:16})', doc: 'Generates secure random hex token.' },
            UUID: { sig: 'Crypto.UUID() -> String', snippet: 'Crypto.UUID()', doc: 'Generates a random RFC 4122 Version 4 UUID string.' },
            HashPassword: { sig: 'Crypto.HashPassword(password: String, iterations: Integer = 10000) -> String', snippet: 'Crypto.HashPassword(${1:password}, ${2:10000})', doc: 'Securely hashes password using salted PBKDF2-HMAC-SHA256.' },
            VerifyPassword: { sig: 'Crypto.VerifyPassword(password: String, hash: String) -> Boolean', snippet: 'Crypto.VerifyPassword(${1:password}, ${2:hash})', doc: 'Verifies password against stored PBKDF2 hash using constant-time comparison.' },
            TimingSafeEqual: { sig: 'Crypto.TimingSafeEqual(a: String, b: String) -> Boolean', snippet: 'Crypto.TimingSafeEqual(${1:a}, ${2:b})', doc: 'Compares two strings in constant time to prevent timing attacks.' }
        }
    }
};

const bindProperties = {
    value: { sig: 'bindVar.value', doc: 'Current value of the reactive variable.' },
    previous: { sig: 'bindVar.previous', doc: 'Value prior to the most recent mutation.' },
    origin: { sig: 'bindVar.origin', doc: 'Original value specified at declaration.' },
    history: { sig: 'bindVar.history', doc: 'Array of all past values in temporal order.' },
    changes: { sig: 'bindVar.changes', doc: 'Total count of mutations.' }
};

function completionProvider(service) {
    return {
        provideCompletionItems(document, position) {
            const linePrefix = document.lineAt(position.line).text.slice(0, position.character);
            const items = [];

            // 1. Dot triggers: e.g. "Math.", "Http.", "Vector.", "state."
            const dotMatch = /([A-Za-z_][A-Za-z0-9_]*)\.\s*([A-Za-z_]*)$/.exec(linePrefix);
            if (dotMatch) {
                const objectName = dotMatch[1];
                
                // Standard module methods (e.g. Math.sqrt, Vector.CosineSimilarity)
                if (standardModules[objectName]) {
                    for (const [memberName, info] of Object.entries(standardModules[objectName].members)) {
                        const item = new vscode.CompletionItem(memberName, vscode.CompletionItemKind.Method);
                        item.detail = info.sig;
                        item.documentation = new vscode.MarkdownString(info.doc);
                        if (info.snippet) {
                            item.insertText = new vscode.SnippetString(info.snippet.replace(new RegExp(`^${objectName}\\.`), ''));
                        }
                        items.push(item);
                    }
                    return items;
                }

                // Reactive Bind Properties
                const symbol = service.symbols(document).find(s => s.name === objectName);
                if (symbol && symbol.detail && symbol.detail.includes('bind')) {
                    for (const [propName, info] of Object.entries(bindProperties)) {
                        const item = new vscode.CompletionItem(propName, vscode.CompletionItemKind.Property);
                        item.detail = info.sig;
                        item.documentation = new vscode.MarkdownString(info.doc);
                        items.push(item);
                    }
                    return items;
                }
            }

            const range = document.getWordRangeAtPosition(position);

            // 2. Keywords Suggester & Snippets (Top Priority)
            for (const [name, info] of Object.entries(keywords)) {
                const item = new vscode.CompletionItem(name, vscode.CompletionItemKind.Keyword);
                item.detail = info.sig;
                item.documentation = new vscode.MarkdownString(info.doc);
                item.insertText = info.snippet ? new vscode.SnippetString(info.snippet) : name;
                item.filterText = name + ' ' + name.toLowerCase();
                item.sortText = `0_${name.toLowerCase()}`;
                items.push(item);
            }

            // Keyword Aliases for ergonomic typing (e.g. class -> Class, fn -> Function, func -> Function, import -> Import)
            const aliases = {
                fn: keywords.Function,
                func: keywords.Function,
                function: keywords.Function,
                class: keywords.Class,
                struct: keywords.Struct,
                enum: keywords.Enum,
                ctor: keywords.Constructor,
                constructor: keywords.Constructor,
                import: keywords.Import,
                export: keywords.Export,
                break: keywords.Break,
                continue: keywords.Continue,
                const: keywords.constant,
                let: keywords.var,
                ifelse: { sig: 'if condition { ... } else { ... }', doc: 'If-else conditional block.', snippet: 'if ${1:condition} {\n\t${2}\n} else {\n\t${0}\n}' },
                foreach: { sig: 'for i in range(0, 10) { ... }', doc: 'Iterate over numeric range.', snippet: 'for ${1:i} in range(${2:0}, ${3:10}) {\n\t${0}\n}' },
                trycatch: { sig: 'try { ... } catch err { ... }', doc: 'Structured try-catch exception handling.', snippet: 'try {\n\t${1}\n} catch ${2:err} {\n\t${0}\n}' },
                tryfinally: { sig: 'try { ... } catch err { ... } finally { ... }', doc: 'Try-catch-finally block.', snippet: 'try {\n\t${1}\n} catch ${2:err} {\n\t${3}\n} finally {\n\t${0}\n}' }
            };
            for (const [alias, info] of Object.entries(aliases)) {
                const item = new vscode.CompletionItem(alias, vscode.CompletionItemKind.Snippet);
                item.detail = `(Snippet) ${info.sig}`;
                item.documentation = new vscode.MarkdownString(info.doc);
                item.insertText = info.snippet ? new vscode.SnippetString(info.snippet) : alias;
                item.filterText = alias;
                item.sortText = `0_${alias}`;
                items.push(item);
            }

            // 3. Builtin Functions with snippets & documentation
            for (const [name, info] of Object.entries(builtins)) {
                const item = new vscode.CompletionItem(name, vscode.CompletionItemKind.Function);
                item.detail = info.sig;
                item.documentation = new vscode.MarkdownString(info.doc);
                if (info.snippet) {
                    item.insertText = new vscode.SnippetString(info.snippet);
                }
                item.filterText = name + ' ' + name.toLowerCase();
                item.sortText = `1_${name.toLowerCase()}`;
                items.push(item);

                // Lowercase builtin alias (e.g. show -> Show, print -> Print, input -> Input)
                if (name[0] >= 'A' && name[0] <= 'Z') {
                    const lower = name.toLowerCase();
                    const lowerItem = new vscode.CompletionItem(lower, vscode.CompletionItemKind.Snippet);
                    lowerItem.detail = `(Alias) ${info.sig}`;
                    lowerItem.documentation = new vscode.MarkdownString(info.doc);
                    if (info.snippet) {
                        lowerItem.insertText = new vscode.SnippetString(info.snippet);
                    }
                    lowerItem.filterText = lower;
                    lowerItem.sortText = `1_${lower}`;
                    items.push(lowerItem);
                }
            }

            // 4. Standard Library Modules
            for (const [modName, info] of Object.entries(standardModules)) {
                const item = new vscode.CompletionItem(modName, vscode.CompletionItemKind.Module);
                item.detail = `BlazeLang Standard Module: std:${modName.toLowerCase()}`;
                item.documentation = new vscode.MarkdownString(info.doc);
                item.filterText = modName + ' ' + modName.toLowerCase();
                item.sortText = `2_${modName.toLowerCase()}`;
                items.push(item);
            }

            // 5. User-Defined Symbols (Functions, Classes, Structs, Variables)
            for (const sym of service.symbols(document)) {
                const item = new vscode.CompletionItem(sym.name, completionKindFor(sym));
                item.detail = sym.detail || `${sym.kind} declaration`;
                item.sortText = `3_${sym.name.toLowerCase()}`;
                items.push(item);
            }

            return items;
        }
    };
}

function hoverProvider(service) {
    return {
        provideHover(document, position) {
            const range = document.getWordRangeAtPosition(position);
            if (!range) return;

            const word = document.getText(range);
            const line = document.lineAt(position.line).text;
            
            // Check member hover (e.g. Math.sqrt)
            const memberMatch = new RegExp(`([A-Za-z_][A-Za-z0-9_]*)\\.${word}\\b`).exec(line);
            if (memberMatch) {
                const parentObj = memberMatch[1];
                if (standardModules[parentObj] && standardModules[parentObj].members[word]) {
                    const info = standardModules[parentObj].members[word];
                    const md = new vscode.MarkdownString();
                    md.appendCodeblock(info.sig, 'blazelang');
                    md.appendMarkdown(`\n\n${info.doc}`);
                    return new vscode.Hover(md, range);
                }
            }

            // Builtins Hover
            if (builtins[word]) {
                const info = builtins[word];
                const md = new vscode.MarkdownString();
                md.appendCodeblock(info.sig, 'blazelang');
                md.appendMarkdown(`\n\n${info.doc}`);
                return new vscode.Hover(md, range);
            }

            // Keywords Hover
            if (keywords[word]) {
                const info = keywords[word];
                const md = new vscode.MarkdownString();
                md.appendCodeblock(info.sig, 'blazelang');
                md.appendMarkdown(`\n\n${info.doc}`);
                return new vscode.Hover(md, range);
            }

            // Standard Modules Hover
            if (standardModules[word]) {
                const info = standardModules[word];
                const md = new vscode.MarkdownString();
                md.appendCodeblock(`Import ${word} from "${word.toLowerCase()}"`, 'blazelang');
                md.appendMarkdown(`\n\n**BlazeLang Standard Module**\n\n${info.doc}`);
                return new vscode.Hover(md, range);
            }

            // User Symbols Hover
            const symbol = service.symbols(document).find(item => item.name === word);
            if (symbol) {
                const md = new vscode.MarkdownString();
                md.appendCodeblock(`${symbol.detail || symbol.name}`, 'blazelang');
                md.appendMarkdown(`\n\n*Declared at line ${symbol.range.start.line + 1}*`);
                return new vscode.Hover(md, range);
            }

            return undefined;
        }
    };
}

// Python-style Signature Help: pops up active parameter hint while typing '(' or ','
function signatureHelpProvider(service) {
    return {
        provideSignatureHelp(document, position) {
            const lineText = document.lineAt(position.line).text.slice(0, position.character);
            
            // Match function call before open parenthesis: funcName(arg1, arg2,
            const match = /([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)?)\s*\(([^()]*)$/.exec(lineText);
            if (!match) return undefined;

            const funcCall = match[1];
            const argsText = match[2];
            const activeParam = argsText.split(',').length - 1;

            let sigText = '';
            let docText = '';

            if (funcCall.includes('.')) {
                const parts = funcCall.split('.');
                const mod = parts[0];
                const fn = parts[1];
                if (standardModules[mod] && standardModules[mod].members[fn]) {
                    sigText = standardModules[mod].members[fn].sig;
                    docText = standardModules[mod].members[fn].doc;
                }
            } else if (builtins[funcCall]) {
                sigText = builtins[funcCall].sig;
                docText = builtins[funcCall].doc;
            } else {
                // User function signature
                const sym = service.symbols(document).find(s => s.name === funcCall && s.kind === 'function');
                if (sym) {
                    sigText = sym.detail || `${funcCall}()`;
                    docText = `User-defined function at line ${sym.range.start.line + 1}.`;
                }
            }

            if (!sigText) return undefined;

            const help = new vscode.SignatureHelp();
            const sigInfo = new vscode.SignatureInformation(sigText, new vscode.MarkdownString(docText));
            
            // Extract parameter names inside signature ()
            const paramMatch = /\(([^)]*)\)/.exec(sigText);
            if (paramMatch && paramMatch[1].trim()) {
                const params = paramMatch[1].split(',').map(p => p.trim());
                sigInfo.parameters = params.map(p => new vscode.ParameterInformation(p));
            }

            help.signatures = [sigInfo];
            help.activeSignature = 0;
            help.activeParameter = Math.min(activeParam, (sigInfo.parameters?.length || 1) - 1);
            return help;
        }
    };
}

function semanticProvider() {
    const legend = new vscode.SemanticTokensLegend(['keyword', 'class', 'function', 'method', 'variable', 'parameter', 'property', 'string', 'number', 'comment']);
    const token = { keyword: 0, class: 1, function: 2, variable: 4, comment: 9 };
    return [{
        provideDocumentSemanticTokens(document) {
            const builder = new vscode.SemanticTokensBuilder(legend);
            const declaration = /\b(Class|Struct|Enum|Function|function|Meta|var|constant|bind)\s+([A-Za-z_]\w*)/g;
            for (let line = 0; line < document.lineCount; line += 1) {
                const text = document.lineAt(line).text;
                const comment = text.indexOf('//');
                if (comment >= 0) {
                    builder.push(line, comment, text.length - comment, token.comment);
                }
                declaration.lastIndex = 0;
                for (let m = declaration.exec(text); m; m = declaration.exec(text)) {
                    builder.push(line, m.index, m[1].length, token.keyword);
                    builder.push(line, m.index + m[0].lastIndexOf(m[2]), m[2].length, (m[1] === 'Class' || m[1] === 'Struct' || m[1] === 'Enum') ? token.class : ((m[1] === 'var' || m[1] === 'constant' || m[1] === 'bind') ? token.variable : token.function));
                }
            }
            return builder.build();
        }
    }, legend];
}

function symbolProvider(service) {
    return {
        provideDocumentSymbols(document) {
            return service.symbols(document).filter(s => s.kind !== 'import').map(s => new vscode.DocumentSymbol(s.name, s.detail ?? '', kindFor(s), s.range, s.selectionRange));
        },
        provideWorkspaceSymbols(query) {
            const results = [];
            for (const document of vscode.workspace.textDocuments.filter(d => d.languageId === 'blazelang')) {
                for (const symbol of service.symbols(document)) {
                    if (symbol.name.toLowerCase().includes(query.toLowerCase())) {
                        results.push(new vscode.SymbolInformation(symbol.name, kindFor(symbol), symbol.range, document.uri));
                    }
                }
            }
            return results;
        }
    };
}

function definitionProvider(service) {
    return {
        provideDefinition(document, position) {
            const range = service.wordRange(document, position);
            if (!range) return;
            const word = document.getText(range);
            const symbols = service.symbols(document).filter(s => s.name === word);
            return symbols.map(s => new vscode.Location(document.uri, s.selectionRange));
        },
        provideReferences(document, position) {
            const range = service.wordRange(document, position);
            if (!range) return [];
            const expression = new RegExp(`\\b${escape(document.getText(range))}\\b`, 'g');
            const locations = [];
            for (let i = 0; i < document.lineCount; i += 1) {
                const text = document.lineAt(i).text;
                for (let m = expression.exec(text); m; m = expression.exec(text)) {
                    locations.push(new vscode.Location(document.uri, new vscode.Range(i, m.index, i, m.index + m[0].length)));
                }
            }
            return locations;
        },
        prepareRename(document, position) {
            return service.wordRange(document, position);
        },
        provideRenameEdits(document, position, newName) {
            const edits = new vscode.WorkspaceEdit();
            const range = service.wordRange(document, position);
            if (!range || !/^[A-Za-z_]\w*$/.test(newName)) return;
            for (const location of this.provideReferences(document, position, { includeDeclaration: true }, new vscode.CancellationTokenSource().token)) {
                edits.replace(location.uri, location.range, newName);
            }
            return edits;
        }
    };
}

function formatter() {
    return {
        provideDocumentFormattingEdits(document, options) {
            let depth = 0;
            const size = vscode.workspace.getConfiguration('blazelang.format', document.uri).get('indentSize', options.tabSize);
            const lines = document.getText().split(/\r?\n/).map(raw => {
                const trimmed = raw.trim();
                if (/^[}\]]/.test(trimmed)) depth = Math.max(0, depth - 1);
                const line = trimmed ? `${' '.repeat(depth * size)}${trimmed.replace(/\s+$/g, '')}` : '';
                if (/[{\[]\s*(?:\/\/.*)?$/.test(trimmed)) depth += 1;
                return line;
            });
            return [vscode.TextEdit.replace(new vscode.Range(0, 0, document.lineCount, 0), lines.join('\n'))];
        }
    };
}

function codeActions() {
    return {
        provideCodeActions(document, _range, context) {
            const actions = [];
            for (const diagnostic of context.diagnostics) {
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
            }
            return actions;
        }
    };
}

function kindFor(symbol) {
    return { class: vscode.SymbolKind.Class, struct: vscode.SymbolKind.Struct, enum: vscode.SymbolKind.Enum, function: vscode.SymbolKind.Function, meta: vscode.SymbolKind.Method, constant: vscode.SymbolKind.Constant, import: vscode.SymbolKind.Module, variable: vscode.SymbolKind.Variable, parameter: vscode.SymbolKind.Variable }[symbol.kind] || vscode.SymbolKind.Variable;
}

function completionKindFor(symbol) {
    return { class: vscode.CompletionItemKind.Class, struct: vscode.CompletionItemKind.Struct, enum: vscode.CompletionItemKind.Enum, function: vscode.CompletionItemKind.Function, meta: vscode.CompletionItemKind.Method, constant: vscode.CompletionItemKind.Constant, import: vscode.CompletionItemKind.Module, variable: vscode.CompletionItemKind.Variable, parameter: vscode.CompletionItemKind.Variable }[symbol.kind] || vscode.CompletionItemKind.Variable;
}

function escape(value) {
    return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

