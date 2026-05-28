"""AI Code Review Tutor — Rule Engine (AST Parser + Knowledge Base + Inference).

Modul-modul utama:
- models             : Violation, Severity
- parser             : AST parsing & traversal helpers
- knowledge_base     : 15 IF-THEN rules antipattern
- inference_engine   : Forward chaining engine

Cara pakai cepat:
    >>> from inference_engine import InferenceEngine
    >>> engine = InferenceEngine()
    >>> violations = engine.run(source_code_string)

Project: Sistem AI Code Review Tutor Berbasis Rule-Based Reasoning dan LLM.
Mata Kuliah: Kecerdasan Buatan, Semester Genap 2025/2026.
Institusi: Institut Teknologi Bacharuddin Jusuf Habibie.
"""

__version__ = "0.1.0"
