import os

class Config:
    # Change these to match your MySQL setup
    MYSQL_HOST = 'localhost'
    MYSQL_USER = 'root'
    MYSQL_PASSWORD = '270906'   # <-- Change this to ur sql if running there
    MYSQL_DB = 'expense_tracker'

    SECRET_KEY = os.urandom(24)   # Flask session secret key

    CATEGORIES = [
        'Food',
        'Travel',
        'Bills',
        'Health',
        'Shopping',
        'Entertainment',
        'Education',
        'Other'
    ]
