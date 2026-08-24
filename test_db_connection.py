#!/usr/bin/env python3
"""
Database connection diagnostic tool.
Run this to troubleshoot database connectivity issues.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

load_dotenv()


def check_env_vars():
    """Check if environment variables are set."""
    print("=" * 70)
    print("1. CHECKING ENVIRONMENT VARIABLES")
    print("=" * 70)

    required_vars = ["DB_USER", "DB_PASSWORD", "DB_HOST", "DB_PORT", "DB_NAME"]
    all_present = True

    for var in required_vars:
        value = os.getenv(var)
        if value:
            # Mask password for security
            display_value = "***" if var == "DB_PASSWORD" else value
            print(f"  ✓ {var}: {display_value}")
        else:
            print(f"  ✗ {var}: NOT SET")
            all_present = False

    if not all_present:
        print("\n⚠ Some environment variables are missing. Check your .env file.")
        return False

    print("\n✓ All environment variables are set.\n")
    return True


def check_postgres_running():
    """Check if PostgreSQL is running and accessible."""
    print("=" * 70)
    print("2. CHECKING POSTGRESQL CONNECTION")
    print("=" * 70)

    db_host = os.getenv("DB_HOST")
    db_port = os.getenv("DB_PORT", "5432")
    db_user = os.getenv("DB_USER")
    db_password = os.getenv("DB_PASSWORD")
    db_name = os.getenv("DB_NAME")

    print(f"  Connecting to: {db_user}@{db_host}:{db_port}/{db_name}")

    try:
        import psycopg2

        conn = psycopg2.connect(
            host=db_host,
            port=int(db_port),
            user=db_user,
            password=db_password,
            database=db_name,
        )
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]
        cursor.close()
        conn.close()

        print(f"  ✓ Connection successful!")
        print(f"  Database version: {version}")
        return True

    except ImportError:
        print("  ✗ psycopg2 not installed. Installing would help diagnose connection issues.")
        print("     Run: pip install psycopg2-binary")
    except Exception as e:
        print(f"  ✗ Connection failed: {type(e).__name__}")
        print(f"     Error: {e}")
        print("\n  Troubleshooting steps:")
        print("  1. Ensure PostgreSQL is running on your system")
        print("  2. Check if the host/port are correct")
        print("  3. Verify the username and password")
        print("  4. Verify the database exists")
        return False


def check_sqlalchemy_connection():
    """Check if SQLAlchemy can connect."""
    print("\n" + "=" * 70)
    print("3. CHECKING SQLALCHEMY CONNECTION")
    print("=" * 70)

    try:
        from config.Database import engine
        from sqlalchemy import text

        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1"))
            connection.commit()
            print("  ✓ SQLAlchemy connection successful!")
            return True

    except Exception as e:
        print(f"  ✗ SQLAlchemy connection failed: {type(e).__name__}")
        print(f"     Error: {e}")
        return False


def check_tables_exist():
    """Check if database tables exist."""
    print("\n" + "=" * 70)
    print("4. CHECKING DATABASE TABLES")
    print("=" * 70)

    try:
        from config.Database import engine
        from sqlalchemy import inspect as sqlalchemy_inspect

        inspector = sqlalchemy_inspect(engine)
        existing_tables = inspector.get_table_names()

        print(f"  Existing tables: {existing_tables if existing_tables else 'None'}")

        required_tables = ["sessions", "messages", "documents"]
        missing_tables = [t for t in required_tables if t not in existing_tables]

        if missing_tables:
            print(f"\n  ✗ Missing tables: {missing_tables}")
            print(f"\n  ➜ Run: python init_db.py")
            return False

        print("\n  ✓ All required tables exist!")
        return True

    except Exception as e:
        print(f"  ✗ Failed to check tables: {type(e).__name__}")
        print(f"     Error: {e}")
        return False


def main():
    """Run all diagnostic checks."""
    print("\n")
    print("╔" + "=" * 68 + "╗")
    print("║" + " DATABASE CONNECTION DIAGNOSTIC ".center(68) + "║")
    print("╚" + "=" * 68 + "╝")
    print()

    results = []

    # Check 1: Environment variables
    results.append(("Environment Variables", check_env_vars()))

    if not results[-1][1]:
        print("\n✗ Cannot proceed without environment variables.")
        print("  Fix your .env file and try again.")
        return False

    # Check 2: PostgreSQL running
    results.append(("PostgreSQL Connection", check_postgres_running()))

    # Check 3: SQLAlchemy connection
    results.append(("SQLAlchemy Connection", check_sqlalchemy_connection()))

    # Check 4: Tables exist
    results.append(("Database Tables", check_tables_exist()))

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    for check_name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {check_name}: {status}")

    all_passed = all(passed for _, passed in results)

    print("\n" + "=" * 70)
    if all_passed:
        print("✓ All checks passed! Your database is ready.")
        print("=" * 70)
        return True
    else:
        print("✗ Some checks failed. See above for details.")
        print("=" * 70)
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
