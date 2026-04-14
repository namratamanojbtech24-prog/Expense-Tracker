from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from config import Config
import re

app = Flask(__name__)
app.config.from_object(Config)

# MySQL config
import os

app.config['MYSQL_HOST'] = os.getenv('MYSQLHOST')
app.config['MYSQL_USER'] = os.getenv('MYSQLUSER')
app.config['MYSQL_PASSWORD'] = os.getenv('MYSQLPASSWORD')
app.config['MYSQL_DB'] = os.getenv('MYSQLDATABASE')
app.config['MYSQL_PORT'] = int(os.getenv('MYSQLPORT', 3306))
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'

app.secret_key = os.getenv('SECRET_KEY', 'fallback-secret')
# ── Auth decorator ──────────────────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


# ── Auth Routes ─────────────────────────────────────────────────────────────

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email    = request.form.get('email', '').strip()
        password = request.form.get('password', '')

        errors = []
        if not username or len(username) < 3:
            errors.append('Username must be at least 3 characters.')
        if not re.match(r'^[\w.-]+@[\w.-]+\.\w+$', email):
            errors.append('Invalid email address.')
        if len(password) < 6:
            errors.append('Password must be at least 6 characters.')

        if errors:
            return render_template('register.html', errors=errors, username=username, email=email)

        cur = mysql.connection.cursor()
        cur.execute('SELECT id FROM users WHERE email = %s OR username = %s', (email, username))
        existing = cur.fetchone()
        if existing:
            return render_template('register.html', errors=['Email or username already in use.'], username=username, email=email)

        pw_hash = generate_password_hash(password)
        cur.execute('INSERT INTO users (username, email, password_hash) VALUES (%s, %s, %s)',
                    (username, email, pw_hash))
        mysql.connection.commit()
        cur.close()

        flash('Account created! Please log in.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html', errors=[], username='', email='')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        identifier = request.form.get('identifier', '').strip()
        password   = request.form.get('password', '')

        cur = mysql.connection.cursor()
        cur.execute('SELECT * FROM users WHERE email = %s OR username = %s', (identifier, identifier))
        user = cur.fetchone()
        cur.close()

        if user and check_password_hash(user['password_hash'], password):
            session['user_id']  = user['id']
            session['username'] = user['username']
            session['email']    = user['email']
            return redirect(url_for('dashboard'))

        return render_template('login.html', error='Invalid credentials. Please try again.', identifier=identifier)

    return render_template('login.html', error=None, identifier='')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

#-─ Dashboard ───────────────────────────────────────────────────────────────
@app.route('/dashboard')
@login_required
def dashboard():
    category_filter = request.args.get('category', '')
    date_from       = request.args.get('date_from', '')
    date_to         = request.args.get('date_to', '')

    cur = mysql.connection.cursor()
    query = 'SELECT * FROM expenses WHERE user_id = %s'
    params = [session['user_id']]

    if category_filter:
        query += ' AND category = %s'
        params.append(category_filter)
    if date_from:
        query += ' AND date >= %s'
        params.append(date_from)
    if date_to:
        query += ' AND date <= %s'
        params.append(date_to)

    query += ' ORDER BY date DESC'
    cur.execute(query, params)
    expenses = cur.fetchall()

    # ── Summary stats (all time) ──
    cur.execute('SELECT COALESCE(SUM(amount),0) as total FROM expenses WHERE user_id = %s', [session['user_id']])
    total = cur.fetchone()['total']

    cur.execute('SELECT COUNT(*) as cnt FROM expenses WHERE user_id = %s', [session['user_id']])
    count = cur.fetchone()['cnt']

    # ── This month ──
    cur.execute('''
        SELECT COALESCE(SUM(amount),0) as total 
        FROM expenses
        WHERE user_id = %s 
        AND MONTH(date) = MONTH(CURDATE()) 
        AND YEAR(date) = YEAR(CURDATE())
    ''', [session['user_id']])
    month_total = cur.fetchone()['total']

    cur.execute('''
        SELECT COUNT(*) as cnt 
        FROM expenses
        WHERE user_id = %s 
        AND MONTH(date) = MONTH(CURDATE()) 
        AND YEAR(date) = YEAR(CURDATE())
    ''', [session['user_id']])
    month_count = cur.fetchone()['cnt']

    # ── Top category ──
    cur.execute('''
        SELECT category, SUM(amount) as cat_total 
        FROM expenses
        WHERE user_id = %s 
        GROUP BY category 
        ORDER BY cat_total DESC 
        LIMIT 1
    ''', [session['user_id']])
    top_cat = cur.fetchone()

    # ── Categories used ──
    cur.execute('SELECT COUNT(DISTINCT category) as cnt FROM expenses WHERE user_id = %s', [session['user_id']])
    categories_used = cur.fetchone()['cnt']

    # ── Budget logic (NEW) ──
    month = datetime.now().strftime('%Y-%m')

    cur.execute("""
        SELECT budget FROM budgets 
        WHERE user_id=%s AND month=%s
    """, (session['user_id'], month))

    budget_row = cur.fetchone()
    budget = budget_row['budget'] if budget_row else 0

    remaining = budget - month_total

    cur.close()

    return render_template('dashboard.html',
                           expenses=expenses,
                           total=total,
                           count=count,
                           month_total=month_total,
                           month_count=month_count,
                           top_cat=top_cat,
                           categories_used=categories_used,
                           categories=Config.CATEGORIES,
                           active_category=category_filter,
                           date_from=date_from,
                           date_to=date_to,
                           budget=budget,
                           remaining=remaining
                           )
# ── Expense CRUD (JSON API) ──────────────────────────────────────────────────

@app.route('/api/expense', methods=['POST'])
@login_required
def add_expense():
    data = request.get_json()
    amount      = data.get('amount')
    date        = data.get('date')
    category    = data.get('category')
    description = data.get('description', '')

    if not amount or not date or not category:
        return jsonify({'success': False, 'message': 'Amount, date, and category are required.'}), 400
    try:
        amount = float(amount)
        if amount <= 0:
            raise ValueError
    except ValueError:
        return jsonify({'success': False, 'message': 'Amount must be a positive number.'}), 400
    if category not in Config.CATEGORIES:
        return jsonify({'success': False, 'message': 'Invalid category.'}), 400

    cur = mysql.connection.cursor()
    cur.execute('INSERT INTO expenses (user_id, amount, date, category, description) VALUES (%s, %s, %s, %s, %s)',
                (session['user_id'], amount, date, category, description))
    mysql.connection.commit()
    new_id = cur.lastrowid
    cur.close()
    return jsonify({'success': True, 'id': new_id})


@app.route('/api/expense/<int:expense_id>', methods=['PUT'])
@login_required
def edit_expense(expense_id):
    cur = mysql.connection.cursor()
    cur.execute('SELECT user_id FROM expenses WHERE id = %s', [expense_id])
    exp = cur.fetchone()

    if not exp or exp['user_id'] != session['user_id']:
        cur.close()
        return jsonify({'success': False, 'message': 'Not found or unauthorized.'}), 403

    data = request.get_json()
    amount      = data.get('amount')
    date        = data.get('date')
    category    = data.get('category')
    description = data.get('description', '')

    try:
        amount = float(amount)
        if amount <= 0:
            raise ValueError
    except (ValueError, TypeError):
        return jsonify({'success': False, 'message': 'Amount must be a positive number.'}), 400
    if category not in Config.CATEGORIES:
        return jsonify({'success': False, 'message': 'Invalid category.'}), 400

    cur.execute('UPDATE expenses SET amount=%s, date=%s, category=%s, description=%s WHERE id=%s',
                (amount, date, category, description, expense_id))
    mysql.connection.commit()
    cur.close()
    return jsonify({'success': True})


@app.route('/api/expense/<int:expense_id>', methods=['DELETE'])
@login_required
def delete_expense(expense_id):
    cur = mysql.connection.cursor()
    cur.execute('SELECT user_id FROM expenses WHERE id = %s', [expense_id])
    exp = cur.fetchone()

    if not exp or exp['user_id'] != session['user_id']:
        cur.close()
        return jsonify({'success': False, 'message': 'Not found or unauthorized.'}), 403

    cur.execute('DELETE FROM expenses WHERE id = %s', [expense_id])
    mysql.connection.commit()
    cur.close()
    return jsonify({'success': True})

import csv
from io import StringIO
from flask import Response

@app.route('/export')
@login_required
def export_csv():
    category = request.args.get('category')
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')

    query = "SELECT amount, date, category, description FROM expenses WHERE user_id=%s"
    params = [session['user_id']]

    if category:
        query += " AND category=%s"
        params.append(category)
    if date_from:
        query += " AND date >= %s"
        params.append(date_from)
    if date_to:
        query += " AND date <= %s"
        params.append(date_to)

    cur = mysql.connection.cursor()
    cur.execute(query, params)
    rows = cur.fetchall()
    cur.close()

    si = StringIO()
    writer = csv.writer(si)

    # Header
    writer.writerow(['Amount', 'Date', 'Category', 'Description'])

    # Data
    for row in rows:
        writer.writerow([
            row['amount'],
            row['date'],
            row['category'],
            row['description']
        ])

    output = si.getvalue()

    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=expenses.csv"}
    )
from datetime import datetime
@app.route('/set_budget', methods=['POST'])
@login_required
def set_budget():
    data = request.get_json()
    budget = data.get('budget')

    if not budget:
        return jsonify({'success': False})

    month = datetime.now().strftime('%Y-%m')

    cur = mysql.connection.cursor()
    cur.execute("""
        INSERT INTO budgets (user_id, month, budget)
        VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE budget=%s
    """, (session['user_id'], month, budget, budget))

    mysql.connection.commit()
    cur.close()

    return jsonify({'success': True})


if __name__ == '__main__':
    app.run(debug=True)
