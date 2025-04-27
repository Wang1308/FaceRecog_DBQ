# database.py
import psycopg2

def connect_db():
    return psycopg2.connect(
        host="localhost",
        database="face_attendance",
        user="postgres",       
        password="quang"  
    )
