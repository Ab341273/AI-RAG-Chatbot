#!/usr/bin/env python3
"""Test database tools directly"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from services.tools import (
    get_document_stats,
    check_database_documents,
    search_documents_by_module
)

print("\n" + "=" * 70)
print("TESTING DATABASE TOOLS")
print("=" * 70 + "\n")

# Test 1: Document Stats
print("1️⃣  TESTING: get_document_stats()")
print("-" * 70)
try:
    result = get_document_stats.invoke({})
    print(result)
except Exception as e:
    print(f"❌ ERROR: {e}")

print("\n" + "=" * 70 + "\n")

# Test 2: Check All Documents
print("2️⃣  TESTING: check_database_documents()")
print("-" * 70)
try:
    result = check_database_documents.invoke({})
    print(result)
except Exception as e:
    print(f"❌ ERROR: {e}")

print("\n" + "=" * 70 + "\n")

# Test 3: Search by Module
print("3️⃣  TESTING: search_documents_by_module('TM')")
print("-" * 70)
try:
    result = search_documents_by_module.invoke({"module": "TM"})
    print(result)
except Exception as e:
    print(f"❌ ERROR: {e}")

print("\n" + "=" * 70)
print("TOOL TESTING COMPLETE")
print("=" * 70 + "\n")
