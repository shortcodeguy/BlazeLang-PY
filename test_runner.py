#!/usr/bin/env python3
"""
BlazeLang Test Runner
Runs all example files and reports results
"""

import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def run_test(filename):
    """Run a single test file"""
    print(f"\n{'='*60}")
    print(f"Testing: {filename}")
    print(f"{'='*60}")
    
    if not os.path.exists(filename):
        print(f"SKIP: File not found: {filename}")
        return False
    
    with open(filename, 'r', encoding='utf-8') as f:
        source = f.read()
    
    try:
        from blazelang.lexer.lexer import Lexer
        from blazelang.parser.parser import Parser
        from blazelang.interpreter.interpreter import Interpreter
        
        lexer = Lexer(source, filename)
        tokens = lexer.tokenize()
        
        parser = Parser(tokens)
        ast = parser.parse()
        
        interpreter = Interpreter(filename=filename)
        interpreter.interpret(ast)
        
        print(f"PASS: {filename}")
        return True
        
    except Exception as e:
        print(f"FAIL: {filename}")
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all test files"""
    test_files = [
        "blazelang/examples/hello.blz",
        "blazelang/examples/full_demo.blz",
        "blazelang/examples/functions_demo.blz",
        "blazelang/examples/class_demo.blz",
    ]
    
    print("BlazeLang Test Suite")
    print("=" * 60)
    
    results = []
    for test_file in test_files:
        result = run_test(test_file)
        results.append((test_file, result))
    
    print(f"\n{'='*60}")
    print("Test Results Summary")
    print(f"{'='*60}")
    
    passed = sum(1 for _, r in results if r)
    failed = sum(1 for _, r in results if not r)
    
    for test_file, result in results:
        status = "PASS" if result else "FAIL"
        print(f"  [{status}] {test_file}")
    
    print(f"\nTotal: {len(results)} | Passed: {passed} | Failed: {failed}")
    
    return 0 if failed == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
