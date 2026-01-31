"""
Test script for PostgreSQL connectivity.
Run this locally after getting the RDS endpoint from AWS Console.

Usage:
    1. Get RDS endpoint from AWS Console or run:
       aws rds describe-db-instances --db-instance-identifier traffic-manager-infra-dev-postgres --profile traffic-manager

    2. Set environment variables:
       export RDS_HOST=<endpoint>
       export RDS_PORT=5432
       export RDS_DATABASE=trafficmanager
       export RDS_USERNAME=trafficmanager_admin
       export RDS_PASSWORD=<your-password>

    3. Run: python src/scripts/test_postgres.py
"""
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv
load_dotenv()

from src.services.postgres_service import PostgresService

def execute(params):
    try:
        main()
        return {
            "status": "success",
            "message": "PostgreSQL connectivity test passed"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }


def main():
    print("Testing PostgreSQL connectivity...\n")

    # Check environment variables
    required_vars = ['RDS_HOST', 'RDS_PORT', 'RDS_DATABASE', 'RDS_USERNAME', 'RDS_PASSWORD']
    missing = [var for var in required_vars if not os.environ.get(var)]

    if missing:
        print(f"Missing environment variables: {', '.join(missing)}")
        print("\nPlease set them in your .env file or export them.")
        return

    print(f"RDS_HOST: {os.environ.get('RDS_HOST')}")
    print(f"RDS_PORT: {os.environ.get('RDS_PORT')}")
    print(f"RDS_DATABASE: {os.environ.get('RDS_DATABASE')}")
    print(f"RDS_USERNAME: {os.environ.get('RDS_USERNAME')}")
    print()

    try:
        service = PostgresService()

        # Health check
        print("1. Running health check...")
        health = service.health_check()
        print(f"   Status: {health.get('status')}")
        if health.get('status') == 'healthy':
            print(f"   Version: {health.get('version')}")
            print(f"   Database: {health.get('database')}")
            print(f"   User: {health.get('user')}")
        else:
            print(f"   Error: {health.get('error')}")
            return

        print()

        # Test table creation
        print("2. Creating test table...")
        service.create_table("_connection_test", {
            "id": "SERIAL PRIMARY KEY",
            "test_value": "VARCHAR(255)",
            "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
        })
        print("   Table created successfully")

        # Verify table exists
        print("3. Verifying table exists...")
        exists = service.table_exists("_connection_test")
        print(f"   Table exists: {exists}")

        # Insert test data
        print("4. Inserting test data...")
        rows = service.execute_write(
            "INSERT INTO _connection_test (test_value) VALUES (%s)",
            ("Hello from Traffic Manager!",)
        )
        print(f"   Inserted {rows} row(s)")

        # Query test data
        print("5. Querying test data...")
        results = service.execute_query("SELECT * FROM _connection_test")
        for row in results:
            print(f"   Row: {row}")

        # Cleanup
        print("6. Cleaning up test table...")
        service.drop_table("_connection_test")
        print("   Table dropped")

        print("\n[OK] All tests passed! PostgreSQL connectivity is working.")

    except Exception as e:
        print(f"\n[ERROR] {e}")
        raise


if __name__ == "__main__":
    main()
