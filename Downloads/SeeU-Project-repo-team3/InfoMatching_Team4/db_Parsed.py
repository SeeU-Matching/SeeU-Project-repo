import sqlite3

# Create SQLite database and table
connection = sqlite3.connect('my_database_parsed.db')
cursor = connection.cursor()

# table 1: resume
cursor.execute('''
    CREATE TABLE IF NOT EXISTS uploads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_name TEXT NOT NULL UNIQUE,
        file_name TEXT NOT NULL,
        parsed_file JSON,
        uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
''')

# table 2: job description
cursor.execute('''
    CREATE TABLE IF NOT EXISTS job_description (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_company TEXT NOT NULL,                    
        job_title TEXT NOT NULL,
        job_description TEXT NOT NULL,
        job_application_url TEXT NOT NULL,
        parsed_file JSON, 
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
''')

connection.commit()
connection.close()

print("Data inserted successfully!")