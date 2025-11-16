import psycopg2
from dotenv import load_dotenv
import os

load_dotenv()

conn = psycopg2.connect(os.getenv("DATABASE_URL"), sslmode='require')
cursor = conn.cursor()

# List all tables in the database
print("=" * 80)
print("ALL TABLES IN DATABASE")
print("=" * 80)
cursor.execute("""
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema = 'public'
    ORDER BY table_name;
""")

tables = cursor.fetchall()
print(f"\nTotal tables: {len(tables)}\n")
for table in tables:
    print(f"  • {table[0]}")

print("\n" + "=" * 80)
print("POSTER_GENERATIONS TABLE DETAILS")
print("=" * 80)

# Check if poster_generations table exists
cursor.execute("""
    SELECT EXISTS (
        SELECT FROM information_schema.tables 
        WHERE table_name = 'poster_generations'
    );
""")
table_exists = cursor.fetchone()[0]
print(f"\nTable exists: {table_exists}\n")

if table_exists:
    # Get column information
    print("COLUMNS:")
    cursor.execute("""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns 
        WHERE table_name = 'poster_generations'
        ORDER BY ordinal_position;
    """)
    columns = cursor.fetchall()
    for col in columns:
        nullable = "NULL" if col[2] == "YES" else "NOT NULL"
        print(f"  • {col[0]:<20} {col[1]:<20} {nullable}")
    
    print("\n" + "-" * 80)
    print("TABLE RECORDS:")
    
    # Get all records from poster_generations
    cursor.execute("SELECT * FROM poster_generations ORDER BY id DESC LIMIT 10;")
    records = cursor.fetchall()
    
    print(f"\nTotal records: {len(records)}\n")
    
    if len(records) > 0:
        for record in records:
            print(f"ID: {record[0]}")
            print(f"Created: {record[1]}")
            print(f"Tenant: {record[2]}")
            print(f"Image URL: {record[3]}")
            print(f"Caption: {record[4][:100] if record[4] else 'None'}...")
            print("-" * 80)
    else:
        print("No records found in poster_generations table")
else:
    print("poster_generations table does not exist")

cursor.close()
conn.close()
