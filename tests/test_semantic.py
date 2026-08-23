"""Tests for semantic diff detection."""

import pytest

from anubis.semantic import (
    extract_python_symbols,
    extract_js_symbols,
    detect_semantic_operations,
)


def test_extract_python_functions():
    """Test extracting function definitions from Python code."""
    code = '''
def hello():
    pass

async def fetch_data(url, timeout=30):
    pass

def _private():
    pass
'''
    symbols = extract_python_symbols(code)

    assert len(symbols) == 3
    names = [s.name for s in symbols]
    assert "hello" in names
    assert "fetch_data" in names
    assert "_private" in names

    fetch = next(s for s in symbols if s.name == "fetch_data")
    assert fetch.kind == "function"
    assert "url" in fetch.signature


def test_extract_python_classes():
    """Test extracting class definitions from Python code."""
    code = '''
class Animal:
    pass

class Dog(Animal):
    def bark(self):
        pass
'''
    symbols = extract_python_symbols(code)

    classes = [s for s in symbols if s.kind == "class"]
    assert len(classes) == 2

    dog = next(s for s in classes if s.name == "Dog")
    assert "Animal" in dog.signature


def test_extract_js_functions():
    """Test extracting function definitions from JavaScript code."""
    code = '''
function greet(name) {
    return "Hello " + name;
}

export async function fetchData(url) {
    return fetch(url);
}

const helper = (x) => x * 2;
'''
    symbols = extract_js_symbols(code)

    names = [s.name for s in symbols]
    assert "greet" in names
    assert "fetchData" in names
    assert "helper" in names


def test_extract_js_classes():
    """Test extracting class definitions from JavaScript code."""
    code = '''
class Component {
    render() {}
}

export class Button extends Component {
    click() {}
}
'''
    symbols = extract_js_symbols(code)

    classes = [s for s in symbols if s.kind == "class"]
    assert len(classes) == 2

    button = next(s for s in classes if s.name == "Button")
    assert "Component" in button.signature


def test_detect_new_file_operations():
    """Test detecting operations when a new file is added."""
    new_content = '''
def process(data):
    return data.strip()

class Handler:
    pass
'''
    ops = detect_semantic_operations("app.py", None, new_content)

    assert len(ops) == 2
    op_types = [op.op_type for op in ops]
    assert "add_function" in op_types
    assert "add_class" in op_types


def test_detect_deleted_file_operations():
    """Test detecting operations when a file is deleted."""
    old_content = '''
def old_function():
    pass
'''
    ops = detect_semantic_operations("app.py", old_content, None)

    assert len(ops) == 1
    assert ops[0].op_type == "delete_function"
    assert ops[0].target == "app.py:old_function"


def test_detect_added_function():
    """Test detecting a new function added to existing file."""
    old_content = '''
def existing():
    pass
'''
    new_content = '''
def existing():
    pass

def new_function():
    pass
'''
    ops = detect_semantic_operations("app.py", old_content, new_content)

    add_ops = [op for op in ops if op.op_type == "add_function"]
    assert len(add_ops) == 1
    assert "new_function" in add_ops[0].target


def test_detect_removed_function():
    """Test detecting a function removed from existing file."""
    old_content = '''
def keep_me():
    pass

def remove_me():
    pass
'''
    new_content = '''
def keep_me():
    pass
'''
    ops = detect_semantic_operations("app.py", old_content, new_content)

    delete_ops = [op for op in ops if op.op_type == "delete_function"]
    assert len(delete_ops) == 1
    assert "remove_me" in delete_ops[0].target


def test_detect_modified_signature():
    """Test detecting a function signature change."""
    old_content = '''
def process(data):
    pass
'''
    new_content = '''
def process(data, options=None):
    pass
'''
    ops = detect_semantic_operations("app.py", old_content, new_content)

    modify_ops = [op for op in ops if op.op_type == "modify_function"]
    assert len(modify_ops) == 1
    assert "process" in modify_ops[0].target
    assert "old_signature" in modify_ops[0].details
    assert "new_signature" in modify_ops[0].details
