import time
import io
import sys
from blazelang.lexer.lexer import Lexer
from blazelang.parser.parser import Parser
from blazelang.interpreter.interpreter import Interpreter

BENCHMARKS = {
    'startup_and_simple': """
var x = 1
var y = 2
var z = x + y
""",

    'arithmetic_1M': """
var a = 0
for i in range(1000000) {
    a = a + i * 2 - 1
}
""",

    'sum_10M_range': """
var total = 0
for i in range(1, 10000001) {
    total += i
}
""",

    'while_loop_1M': """
var i = 0
var total = 0
while i < 1000000 {
    total = total + i
    i += 1
}
""",

    'for_in_list_500k': """
var total = 0
var items = [1, 2, 3, 4, 5]
for i in range(100000) {
    for x in items {
        total = total + x
    }
}
""",

    'func_calls_100k': """
Function add(a, b) {
    return a + b
}
var total = 0
for i in range(100000) {
    total = add(total, 1)
}
""",

    'recursion_fib20': """
Function fib(n) {
    if n <= 1 {
        return n
    }
    return fib(n - 1) + fib(n - 2)
}
var r = fib(20)
""",

    'closure_100k': """
Function makeCounter() {
    var count = 0
    return function() {
        count += 1
        return count
    }
}
var counter = makeCounter()
var res = 0
for i in range(100000) {
    res = counter()
}
""",

    'struct_50k': """
Struct Point { x y }
var total = 0
for i in range(50000) {
    var p = Point(i, i + 1)
    total = total + p.x + p.y
}
""",

    'string_ops_100k': """
var s = "hello world"
var total = 0
for i in range(100000) {
    var u = Upper(s)
    total = total + len(u)
}
""",

    'lexer_parser_large': """
Function process(data) {
    var total = 0
    for x in data {
        if x > 10 {
            total = total + x * 2
        } else {
            total = total + x
        }
    }
    return total
}
""" * 100
}

def run_benchmarks():
    results = {}
    header = "%-25s | %-15s | %-12s | %-12s" % ("Benchmark", "Lex+Parse (ms)", "Exec (s)", "Total (s)")
    print(header)
    print("-" * len(header))
    for name, code in BENCHMARKS.items():
        lp_times = []
        for _ in range(3):
            t0 = time.perf_counter()
            tokens = Lexer(code, '<bench>').tokenize()
            ast = Parser(tokens).parse()
            lp_times.append(time.perf_counter() - t0)
        best_lp = min(lp_times)

        exec_times = []
        for _ in range(3):
            tokens = Lexer(code, '<bench>').tokenize()
            ast = Parser(tokens).parse()
            interp = Interpreter(filename='<bench>')
            t0 = time.perf_counter()
            interp.interpret(ast)
            exec_times.append(time.perf_counter() - t0)
        best_exec = min(exec_times)

        results[name] = {
            'lex_parse_ms': best_lp * 1000,
            'exec_s': best_exec,
            'total_s': best_lp + best_exec
        }
        row = "%-25s | %-15.2f | %-12.4f | %-12.4f" % (name, best_lp * 1000, best_exec, best_lp + best_exec)
        print(row)
    return results

if __name__ == '__main__':
    run_benchmarks()
