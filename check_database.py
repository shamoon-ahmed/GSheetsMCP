import psycopg2
from dotenv import load_dotenv
import os

load_dotenv()

conn = psycopg2.connect(os.getenv("DATABASE_URL"), sslmode='require')
cursor = conn.cursor()

# Check if table exists
cursor.execute("""
    SELECT EXISTS (
        SELECT FROM information_schema.tables 
        WHERE table_name = 'poster_generations'
    );
""")
print(f"Table exists: {cursor.fetchone()[0]}")

# Get all records
cursor.execute("SELECT * FROM poster_generations ORDER BY created_date DESC;")
records = cursor.fetchall()

print(f"\nTotal records: {len(records)}\n")

for record in records:
    print(f"ID: {record[0]}")
    print(f"Created: {record[1]}")
    print(f"Tenant: {record[2]}")
    print(f"Image URL: {record[3]}")
    print(f"Caption: {record[4][:80] if record[4] else 'None'}...")
    print("-" * 80)

cursor.close()
conn.close()