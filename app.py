# ============================================================
# John Mark Cloth - E-Commerce Flask Application
# ============================================================
# A children's clothing e-commerce platform with:
# - Role-based authentication (Admin / User)
# - Product management (CRUD)
# - Analytics dashboard with Chart.js
# - SQLite database with auto-initialization
# ============================================================

from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash, jsonify
)
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os
from functools import wraps
from datetime import datetime, timedelta
import random

# ── App Configuration ────────────────────────────────────────
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'johnmark-cloth-secret-2024')

DATABASE = 'johnmark.db'

# ── Database Helpers ─────────────────────────────────────────

def get_db():
    """Open a new database connection."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row  # Access columns by name
    return conn


def init_db():
    """Create tables and seed default data if they don't exist."""
    conn = get_db()
    c = conn.cursor()

    # Users table
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            name      TEXT    NOT NULL,
            email     TEXT    UNIQUE NOT NULL,
            password  TEXT    NOT NULL,
            role      TEXT    NOT NULL DEFAULT 'user',
            created_at TEXT   NOT NULL DEFAULT (datetime('now'))
        )
    ''')

    # Products table
    c.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT    NOT NULL,
            category    TEXT    NOT NULL,
            age_group   TEXT    NOT NULL,
            size        TEXT    NOT NULL,
            color       TEXT    NOT NULL,
            price       REAL    NOT NULL,
            stock       INTEGER NOT NULL DEFAULT 0,
            description TEXT,
            added_by    INTEGER,
            created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (added_by) REFERENCES users(id)
        )
    ''')

    # Orders table (for analytics)
    c.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            product_id  INTEGER NOT NULL,
            quantity    INTEGER NOT NULL DEFAULT 1,
            total_price REAL    NOT NULL,
            status      TEXT    NOT NULL DEFAULT 'pending',
            ordered_at  TEXT    NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (user_id)    REFERENCES users(id),
            FOREIGN KEY (product_id) REFERENCES products(id)
        )
    ''')

    # ── Seed: Default Admin ──────────────────────────────────
    existing_admin = c.execute(
        "SELECT id FROM users WHERE email = 'admin@example.com'"
    ).fetchone()

    if not existing_admin:
        c.execute(
            "INSERT INTO users (name, email, password, role) VALUES (?, ?, ?, ?)",
            ('Admin', 'admin@example.com',
             generate_password_hash('admin123'), 'admin')
        )

    # ── Seed: Sample Products ────────────────────────────────
    product_count = c.execute("SELECT COUNT(*) FROM products").fetchone()[0]

    if product_count == 0:
        sample_products = [
            ('Floral Frock', 'Dress', '3-5 years', 'S', 'Pink', 599.00, 25,
             'Beautiful floral frock for little girls'),
            ('Denim Dungaree', 'Dungaree', '6-8 years', 'M', 'Blue', 799.00, 18,
             'Comfortable denim dungaree for active kids'),
            ('Cotton Kurta Set', 'Ethnic', '2-4 years', 'XS', 'Yellow', 449.00, 30,
             'Soft cotton kurta with matching pants'),
            ('Striped T-Shirt', 'Casual', '8-10 years', 'L', 'Red', 349.00, 40,
             'Colorful striped casual t-shirt'),
            ('Party Frock', 'Dress', '5-7 years', 'M', 'Purple', 999.00, 12,
             'Elegant party frock with lace trim'),
            ('Cargo Pants', 'Bottom', '9-12 years', 'XL', 'Khaki', 649.00, 22,
             'Durable cargo pants with multiple pockets'),
            ('Printed Onesie', 'Infant', '0-1 years', 'XS', 'White', 299.00, 50,
             'Soft printed onesie for newborns'),
            ('School Uniform Set', 'Uniform', '6-10 years', 'M', 'White/Blue', 549.00, 35,
             'Complete school uniform with shirt and trousers'),
        ]
        c.executemany(
            '''INSERT INTO products
               (name, category, age_group, size, color, price, stock, description, added_by)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)''',
            sample_products
        )

    # ── Seed: Sample Orders ──────────────────────────────────
    order_count = c.execute("SELECT COUNT(*) FROM orders").fetchone()[0]

    if order_count == 0:
        statuses = ['delivered', 'shipped', 'pending', 'cancelled']
        for i in range(30):
            days_ago = random.randint(0, 29)
            date_str = (datetime.now() - timedelta(days=days_ago)).strftime('%Y-%m-%d %H:%M:%S')
            prod_id  = random.randint(1, 8)
            qty      = random.randint(1, 3)
            price    = random.uniform(299, 999) * qty
            c.execute(
                '''INSERT INTO orders (user_id, product_id, quantity, total_price, status, ordered_at)
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (1, prod_id, qty, round(price, 2),
                 random.choice(statuses), date_str)
            )

    conn.commit()
    conn.close()


# ── Auth Decorators ──────────────────────────────────────────

def login_required(f):
    """Redirect to login if user is not authenticated."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to continue.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    """Restrict route to admin users only."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get('role') != 'admin':
            flash('Admin access required.', 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated


# ── DB Init on First Request ─────────────────────────────────
# FIX: Replaced the broken module-level `with app.app_context(): init_db()`
# with the correct Flask pattern. This runs safely after the app is fully
# loaded, whether started via `python app.py` or a WSGI server like gunicorn.

@app.before_request
def initialize_db_once():
    """Initialize DB on the very first request, then remove itself."""
    app.before_request_funcs[None].remove(initialize_db_once)
    init_db()


# ── Auth Routes ──────────────────────────────────────────────

@app.route('/')
def index():
    """Redirect root to dashboard or login."""
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Handle user login."""
    if 'user_id' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        # Validate inputs
        if not email or not password:
            flash('Please fill in all fields.', 'danger')
            return render_template('login.html')

        conn = get_db()
        user = conn.execute(
            "SELECT * FROM users WHERE email = ?", (email,)
        ).fetchone()
        conn.close()

        if user and check_password_hash(user['password'], password):
            # Set session variables
            session['user_id'] = user['id']
            session['name']    = user['name']
            session['email']   = user['email']
            session['role']    = user['role']
            flash(f"Welcome back, {user['name']}!", 'success')
            return redirect(url_for('admin_panel') if user['role'] == 'admin'
                            else url_for('dashboard'))

        flash('Invalid email or password.', 'danger')

    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    """Handle new user registration."""
    if 'user_id' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        name     = request.form.get('name', '').strip()
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm  = request.form.get('confirm_password', '')

        # Input validation
        errors = []
        if not name or len(name) < 2:
            errors.append('Name must be at least 2 characters.')
        if not email or '@' not in email:
            errors.append('Enter a valid email address.')
        if len(password) < 6:
            errors.append('Password must be at least 6 characters.')
        if password != confirm:
            errors.append('Passwords do not match.')

        if errors:
            for err in errors:
                flash(err, 'danger')
            return render_template('register.html')

        conn = get_db()
        existing = conn.execute(
            "SELECT id FROM users WHERE email = ?", (email,)
        ).fetchone()

        if existing:
            flash('Email already registered. Please login.', 'warning')
            conn.close()
            return render_template('register.html')

        conn.execute(
            "INSERT INTO users (name, email, password, role) VALUES (?, ?, ?, 'user')",
            (name, email, generate_password_hash(password))
        )
        conn.commit()
        conn.close()

        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/logout')
def logout():
    """Clear session and redirect to login."""
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))


# ── Dashboard (User) ─────────────────────────────────────────

@app.route('/dashboard')
@login_required
def dashboard():
    """User dashboard with product listing and stats."""
    conn = get_db()

    # Summary stats
    total_products = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    total_orders   = conn.execute(
        "SELECT COUNT(*) FROM orders WHERE user_id = ?", (session['user_id'],)
    ).fetchone()[0]
    total_spent    = conn.execute(
        "SELECT COALESCE(SUM(total_price), 0) FROM orders WHERE user_id = ? AND status != 'cancelled'",
        (session['user_id'],)
    ).fetchone()[0]
    in_stock       = conn.execute(
        "SELECT COUNT(*) FROM products WHERE stock > 0"
    ).fetchone()[0]

    # All products
    products = conn.execute(
        "SELECT * FROM products ORDER BY created_at DESC"
    ).fetchall()

    # Chart: category-wise product count
    category_data = conn.execute(
        "SELECT category, COUNT(*) as cnt FROM products GROUP BY category"
    ).fetchall()

    # Chart: monthly order trend (last 6 months)
    monthly_orders = conn.execute(
        '''SELECT strftime('%Y-%m', ordered_at) as month,
                  COUNT(*) as cnt,
                  COALESCE(SUM(total_price), 0) as revenue
           FROM orders
           WHERE ordered_at >= datetime('now', '-6 months')
           GROUP BY month ORDER BY month'''
    ).fetchall()

    conn.close()

    return render_template(
        'dashboard.html',
        products=products,
        total_products=total_products,
        total_orders=total_orders,
        total_spent=round(total_spent, 2),
        in_stock=in_stock,
        category_data=[dict(r) for r in category_data],
        monthly_orders=[dict(r) for r in monthly_orders],
    )


# ── Product CRUD ─────────────────────────────────────────────

@app.route('/product/add', methods=['GET', 'POST'])
@login_required
def add_product():
    """Add a new product (any logged-in user)."""
    if request.method == 'POST':
        fields = {
            'name':        request.form.get('name', '').strip(),
            'category':    request.form.get('category', '').strip(),
            'age_group':   request.form.get('age_group', '').strip(),
            'size':        request.form.get('size', '').strip(),
            'color':       request.form.get('color', '').strip(),
            'price':       request.form.get('price', 0),
            'stock':       request.form.get('stock', 0),
            'description': request.form.get('description', '').strip(),
        }

        # Basic validation
        if not all([fields['name'], fields['category'], fields['price']]):
            flash('Name, category, and price are required.', 'danger')
            return render_template('add_product.html')

        try:
            price = float(fields['price'])
            stock = int(fields['stock'])
        except ValueError:
            flash('Price and stock must be valid numbers.', 'danger')
            return render_template('add_product.html')

        conn = get_db()
        conn.execute(
            '''INSERT INTO products
               (name, category, age_group, size, color, price, stock, description, added_by)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (fields['name'], fields['category'], fields['age_group'],
             fields['size'], fields['color'], price, stock,
             fields['description'], session['user_id'])
        )
        conn.commit()
        conn.close()

        flash('Product added successfully!', 'success')
        return redirect(url_for('dashboard'))

    return render_template('add_product.html')


@app.route('/product/edit/<int:product_id>', methods=['GET', 'POST'])
@login_required
def edit_product(product_id):
    """Edit an existing product."""
    conn = get_db()
    product = conn.execute(
        "SELECT * FROM products WHERE id = ?", (product_id,)
    ).fetchone()

    if not product:
        flash('Product not found.', 'danger')
        conn.close()
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        name        = request.form.get('name', '').strip()
        category    = request.form.get('category', '').strip()
        age_group   = request.form.get('age_group', '').strip()
        size        = request.form.get('size', '').strip()
        color       = request.form.get('color', '').strip()
        description = request.form.get('description', '').strip()

        try:
            price = float(request.form.get('price', 0))
            stock = int(request.form.get('stock', 0))
        except ValueError:
            flash('Price and stock must be valid numbers.', 'danger')
            conn.close()
            return render_template('edit_product.html', product=product)

        conn.execute(
            '''UPDATE products
               SET name=?, category=?, age_group=?, size=?, color=?,
                   price=?, stock=?, description=?
               WHERE id=?''',
            (name, category, age_group, size, color,
             price, stock, description, product_id)
        )
        conn.commit()
        conn.close()

        flash('Product updated successfully!', 'success')
        return redirect(url_for('dashboard'))

    conn.close()
    return render_template('edit_product.html', product=product)


@app.route('/product/delete/<int:product_id>', methods=['POST'])
@login_required
def delete_product(product_id):
    """Delete a product."""
    conn = get_db()
    conn.execute("DELETE FROM products WHERE id = ?", (product_id,))
    conn.commit()
    conn.close()
    flash('Product deleted.', 'success')
    return redirect(url_for('dashboard'))


# ── Admin Panel ──────────────────────────────────────────────

@app.route('/admin')
@login_required
@admin_required
def admin_panel():
    """Admin dashboard with full system analytics."""
    conn = get_db()

    # Key metrics
    total_users    = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    total_products = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    total_orders   = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    total_revenue  = conn.execute(
        "SELECT COALESCE(SUM(total_price), 0) FROM orders WHERE status != 'cancelled'"
    ).fetchone()[0]

    # All users
    users = conn.execute(
        "SELECT id, name, email, role, created_at FROM users ORDER BY created_at DESC"
    ).fetchall()

    # All products with stock info
    products = conn.execute(
        "SELECT * FROM products ORDER BY created_at DESC"
    ).fetchall()

    # All orders (latest 20)
    orders = conn.execute(
        '''SELECT o.*, u.name as user_name, p.name as product_name
           FROM orders o
           JOIN users u ON o.user_id = u.id
           JOIN products p ON o.product_id = p.id
           ORDER BY o.ordered_at DESC LIMIT 20'''
    ).fetchall()

    # Chart: orders by status
    status_data = conn.execute(
        "SELECT status, COUNT(*) as cnt FROM orders GROUP BY status"
    ).fetchall()

    # Chart: top 5 products by revenue
    top_products = conn.execute(
        '''SELECT p.name, COALESCE(SUM(o.total_price), 0) as revenue
           FROM products p
           LEFT JOIN orders o ON p.id = o.product_id AND o.status != 'cancelled'
           GROUP BY p.id, p.name
           ORDER BY revenue DESC LIMIT 5'''
    ).fetchall()

    # Chart: daily revenue last 7 days
    daily_revenue = conn.execute(
        '''SELECT strftime('%d %b', ordered_at) as day,
                  COALESCE(SUM(total_price), 0) as revenue
           FROM orders
           WHERE ordered_at >= datetime('now', '-7 days')
             AND status != 'cancelled'
           GROUP BY strftime('%Y-%m-%d', ordered_at)
           ORDER BY ordered_at'''
    ).fetchall()

    # Chart: stock level by category
    stock_by_cat = conn.execute(
        "SELECT category, SUM(stock) as total_stock FROM products GROUP BY category"
    ).fetchall()

    conn.close()

    return render_template(
        'admin.html',
        total_users=total_users,
        total_products=total_products,
        total_orders=total_orders,
        total_revenue=round(total_revenue, 2),
        users=users,
        products=products,
        orders=orders,
        status_data=[dict(r) for r in status_data],
        top_products=[dict(r) for r in top_products],
        daily_revenue=[dict(r) for r in daily_revenue],
        stock_by_cat=[dict(r) for r in stock_by_cat],
    )


@app.route('/admin/delete_user/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    """Admin: delete a user account."""
    if user_id == session['user_id']:
        flash("You cannot delete your own account.", 'danger')
        return redirect(url_for('admin_panel'))
    conn = get_db()
    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    flash('User deleted.', 'success')
    return redirect(url_for('admin_panel'))


# ── API Endpoints (for AJAX) ─────────────────────────────────

@app.route('/api/stats')
@login_required
def api_stats():
    """Return live stats as JSON for dashboard refresh."""
    conn = get_db()
    data = {
        'total_products': conn.execute("SELECT COUNT(*) FROM products").fetchone()[0],
        'total_orders':   conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0],
        'total_revenue':  round(conn.execute(
            "SELECT COALESCE(SUM(total_price), 0) FROM orders WHERE status!='cancelled'"
        ).fetchone()[0], 2),
        'in_stock':       conn.execute(
            "from flask import Flask, jsonify, session, redirect, url_for
import os
import sqlite3

app = Flask(__name__)
app.secret_key = "secret-key"

# =========================
# DATABASE
# =========================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "app.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    return conn


def init_db():
    conn = get_db()
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        email TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        price REAL
    )
    """)

    conn.commit()
    conn.close()


# Initialize safely (Render-safe)
init_db()


# =========================
# ROUTES
# =========================
@app.route("/")
def home():
    return redirect(url_for("stats"))


@app.route("/stats")
def stats():
    conn = get_db()
    c = conn.cursor()

    users = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    products = c.execute("SELECT COUNT(*) FROM products").fetchone()[0]

    conn.close()

    return jsonify({
        "users": users,
        "products": products
    })


# =========================
# RENDER ENTRY POINT
# =========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os
from functools import wraps

# ============================================================
# CREATE APP (RENDER SAFE)
# ============================================================

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "default-secret")

# ============================================================
# DATABASE PATH (RENDER SAFE)
# ============================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "app.db")


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


# ============================================================
# INIT DB (SAFE - NO IMPORT CRASH)
# ============================================================
def init_db():
    conn = get_db()
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        email TEXT UNIQUE,
        password TEXT,
        role TEXT DEFAULT 'user'
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        category TEXT,
        price REAL,
        stock INTEGER
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        product_id INTEGER,
        quantity INTEGER,
        total_price REAL
    )
    """)

    # Seed admin only once
    admin = c.execute("SELECT * FROM users WHERE email=?", ("admin@example.com",)).fetchone()
    if not admin:
        c.execute(
            "INSERT INTO users (name,email,password,role) VALUES (?,?,?,?)",
            ("Admin", "admin@example.com",
             generate_password_hash("admin123"), "admin")
        )

    conn.commit()
    conn.close()


# ============================================================
# RUN INIT ONCE (SAFE FOR RENDER)
# ============================================================
with app.app_context():
    init_db()


# ============================================================
# AUTH DECORATOR
# ============================================================
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper


# ============================================================
# ROUTES
# ============================================================

@app.route("/")
def index():
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        conn = get_db()
        user = conn.execute(
            "SELECT * FROM users WHERE email=?",
            (email,)
        ).fetchone()
        conn.close()

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["name"] = user["name"]
            session["role"] = user["role"]
            return redirect(url_for("dashboard"))

        flash("Invalid credentials")

    return render_template("login.html")


@app.route("/dashboard")
@login_required
def dashboard():
    conn = get_db()
    products = conn.execute("SELECT * FROM products").fetchall()
    conn.close()
    return render_template("dashboard.html", products=products)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ============================================================
# API
# ============================================================
@app.route("/api/stats")
@login_required
def stats():
    conn = get_db()
    data = {
        "users": conn.execute("SELECT COUNT(*) FROM users").fetchone()[0],
        "products": conn.execute("SELECT COUNT(*) FROM products").fetchone()[0],
        "orders": conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    }
    conn.close()
    return jsonify(data)


# ============================================================
# RENDER ENTRY POINT
# ============================================================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os
from functools import wraps

# ============================================================
# APP FACTORY (REQUIRED FOR RENDER + GUNICORN)
# ============================================================

def create_app():
    app = Flask(__name__)

    app.secret_key = os.environ.get("SECRET_KEY", "johnmark-secret-key")

    # ✅ FIXED DATABASE PATH (Render-safe)
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DATABASE = os.path.join(BASE_DIR, "johnmark.db")

    # ============================================================
    # DATABASE
    # ============================================================
    def get_db():
        conn = sqlite3.connect(DATABASE)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db():
        conn = get_db()
        c = conn.cursor()

        # USERS
        c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            email TEXT UNIQUE,
            password TEXT,
            role TEXT DEFAULT 'user'
        )
        """)

        # PRODUCTS
        c.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            category TEXT,
            price REAL,
            stock INTEGER
        )
        """)

        # ORDERS
        c.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            product_id INTEGER,
            quantity INTEGER,
            total_price REAL
        )
        """)

        # ✅ Seed admin
        admin = c.execute(
            "SELECT * FROM users WHERE email='admin@example.com'"
        ).fetchone()

        if not admin:
            c.execute(
                "INSERT INTO users (name,email,password,role) VALUES (?,?,?,?)",
                ("Admin", "admin@example.com",
                 generate_password_hash("admin123"), "admin")
            )

        conn.commit()
        conn.close()

    # ============================================================
    # SAFE DB INIT (IMPORTANT FOR RENDER)
    # ============================================================
    with app.app_context():
        init_db()

    # ============================================================
    # AUTH DECORATOR
    # ============================================================
    def login_required(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if "user_id" not in session:
                return redirect(url_for("login"))
            return f(*args, **kwargs)
        return wrapper

    # ============================================================
    # ROUTES
    # ============================================================

    @app.route("/")
    def index():
        return redirect(url_for("login"))

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            email = request.form["email"]
            password = request.form["password"]

            conn = get_db()
            user = conn.execute(
                "SELECT * FROM users WHERE email=?",
                (email,)
            ).fetchone()
            conn.close()

            if user and check_password_hash(user["password"], password):
                session["user_id"] = user["id"]
                session["name"] = user["name"]
                session["role"] = user["role"]
                return redirect(url_for("dashboard"))

            flash("Invalid credentials")

        return render_template("login.html")

    @app.route("/dashboard")
    @login_required
    def dashboard():
        conn = get_db()
        products = conn.execute("SELECT * FROM products").fetchall()
        conn.close()
        return render_template("dashboard.html", products=products)

    @app.route("/logout")
    def logout():
        session.clear()
        return redirect(url_for("login"))

    @app.route("/api/stats")
    @login_required
    def stats():
        conn = get_db()
        data = {
            "users": conn.execute("SELECT COUNT(*) FROM users").fetchone()[0],
            "products": conn.execute("SELECT COUNT(*) FROM products").fetchone()[0],
            "orders": conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0],
        }
        conn.close()
        return jsonify(data)

    return app


# ============================================================
# RENDER ENTRY POINT
# ============================================================

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)## from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os
from functools import wraps
from datetime import datetime

# ─────────────────────────────────────────────
# App Factory (IMPORTANT FOR RENDER)
# ─────────────────────────────────────────────

def create_app():
    app = Flask(__name__)

    app.secret_key = os.environ.get("SECRET_KEY", "johnmark-secret")

    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DATABASE = os.path.join(BASE_DIR, "johnmark.db")

    # ── DB CONNECTION ──
    def get_db():
        conn = sqlite3.connect(DATABASE)
        conn.row_factory = sqlite3.Row
        return conn

    # ── INIT DB (SAFE) ──
    def init_db():
        conn = get_db()
        c = conn.cursor()

        c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            email TEXT UNIQUE,
            password TEXT,
            role TEXT DEFAULT 'user'
        )
        """)

        c.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            category TEXT,
            price REAL,
            stock INTEGER
        )
        """)

        c.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            product_id INTEGER,
            quantity INTEGER,
            total_price REAL
        )
        """)

        # seed admin
        admin = c.execute("SELECT * FROM users WHERE email='admin@example.com'").fetchone()
        if not admin:
            c.execute(
                "INSERT INTO users (name,email,password,role) VALUES (?,?,?,?)",
                ("Admin", "admin@example.com",
                 generate_password_hash("admin123"), "admin")
            )

        conn.commit()
        conn.close()

    # ── INIT DB ONCE ──
    with app.app_context():
        init_db()

    # ── DECORATORS ──
    def login_required(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if "user_id" not in session:
                return redirect(url_for("login"))
            return f(*args, **kwargs)
        return wrapper

    # ── ROUTES ──
    @app.route("/")
    def index():
        return redirect(url_for("login"))

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            email = request.form["email"]
            password = request.form["password"]

            conn = get_db()
            user = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
            conn.close()

            if user and check_password_hash(user["password"], password):
                session["user_id"] = user["id"]
                session["name"] = user["name"]
                session["role"] = user["role"]
                return redirect(url_for("dashboard"))

            flash("Invalid login")

        return render_template("login.html")

    @app.route("/dashboard")
    @login_required
    def dashboard():
        conn = get_db()
        products = conn.execute("SELECT * FROM products").fetchall()
        conn.close()
        return render_template("dashboard.html", products=products)

    @app.route("/logout")
    def logout():
        session.clear()
        return redirect(url_for("login"))

    @app.route("/api/stats")
    @login_required
    def stats():
        conn = get_db()
        data = {
            "users": conn.execute("SELECT COUNT(*) FROM users").fetchone()[0],
            "products": conn.execute("SELECT COUNT(*) FROM products").fetchone()[0],
            "orders": conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0],
        }
        conn.close()
        return jsonify(data)

    return app


# ─────────────────────────────────────────────
# RENDER ENTRY POINT
# ─────────────────────────────────────────────
app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os
from functools import wraps
from datetime import datetime

# ─────────────────────────────────────────────
# App Factory (IMPORTANT FOR RENDER)
# ─────────────────────────────────────────────

def create_app():
    app = Flask(__name__)

    app.secret_key = os.environ.get("SECRET_KEY", "johnmark-secret")

    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DATABASE = os.path.join(BASE_DIR, "johnmark.db")

    # ── DB CONNECTION ──
    def get_db():
        conn = sqlite3.connect(DATABASE)
        conn.row_factory = sqlite3.Row
        return conn

    # ── INIT DB (SAFE) ──
    def init_db():
        conn = get_db()
        c = conn.cursor()

        c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            email TEXT UNIQUE,
            password TEXT,
            role TEXT DEFAULT 'user'
        )
        """)

        c.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            category TEXT,
            price REAL,
            stock INTEGER
        )
        """)

        c.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            product_id INTEGER,
            quantity INTEGER,
            total_price REAL
        )
        """)

        # seed admin
        admin = c.execute("SELECT * FROM users WHERE email='admin@example.com'").fetchone()
        if not admin:
            c.execute(
                "INSERT INTO users (name,email,password,role) VALUES (?,?,?,?)",
                ("Admin", "admin@example.com",
                 generate_password_hash("admin123"), "admin")
            )

        conn.commit()
        conn.close()

    # ── INIT DB ONCE ──
    with app.app_context():
        init_db()

    # ── DECORATORS ──
    def login_required(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if "user_id" not in session:
                return redirect(url_for("login"))
            return f(*args, **kwargs)
        return wrapper

    # ── ROUTES ──
    @app.route("/")
    def index():
        return redirect(url_for("login"))

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            email = request.form["email"]
            password = request.form["password"]

            conn = get_db()
            user = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
            conn.close()

            if user and check_password_hash(user["password"], password):
                session["user_id"] = user["id"]
                session["name"] = user["name"]
                session["role"] = user["role"]
                return redirect(url_for("dashboard"))

            flash("Invalid login")

        return render_template("login.html")

    @app.route("/dashboard")
    @login_required
    def dashboard():
        conn = get_db()
        products = conn.execute("SELECT * FROM products").fetchall()
        conn.close()
        return render_template("dashboard.html", products=products)

    @app.route("/logout")
    def logout():
        session.clear()
        return redirect(url_for("login"))

    @app.route("/api/stats")
    @login_required
    def stats():
        conn = get_db()
        data = {
            "users": conn.execute("SELECT COUNT(*) FROM users").fetchone()[0],
            "products": conn.execute("SELECT COUNT(*) FROM products").fetchone()[0],
            "orders": conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0],
        }
        conn.close()
        return jsonify(data)

    return app


# ─────────────────────────────────────────────
# RENDER ENTRY POINT
# ─────────────────────────────────────────────
app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True) John Mark Cloth - E-Commerce Flask Application (FIXED)
# ============================================================

from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash, jsonify
)
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os
from functools import wraps
from datetime import datetime, timedelta
import random

# ── App Configuration ────────────────────────────────────────
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'johnmark-cloth-secret-2024')

# ✅ FIXED: Absolute DB path for Render
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "johnmark.db")


# ── Database Helpers ─────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    c = conn.cursor()

    # Users table
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    ''')

    # Products table
    c.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            age_group TEXT NOT NULL,
            size TEXT NOT NULL,
            color TEXT NOT NULL,
            price REAL NOT NULL,
            stock INTEGER NOT NULL DEFAULT 0,
            description TEXT,
            added_by INTEGER,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    ''')

    # Orders table
    c.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 1,
            total_price REAL NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            ordered_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    ''')

    # Seed admin
    admin = c.execute("SELECT id FROM users WHERE email='admin@example.com'").fetchone()
    if not admin:
        c.execute(
            "INSERT INTO users (name, email, password, role) VALUES (?, ?, ?, ?)",
            ('Admin', 'admin@example.com',
             generate_password_hash('admin123'), 'admin')
        )

    # Seed products
    count = c.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    if count == 0:
        products = [
            ('Floral Frock', 'Dress', '3-5 years', 'S', 'Pink', 599, 25, 'Nice frock'),
            ('Denim Dungaree', 'Dungaree', '6-8 years', 'M', 'Blue', 799, 18, 'Kids wear'),
            ('Cotton Kurta', 'Ethnic', '2-4 years', 'XS', 'Yellow', 449, 30, 'Soft cotton'),
        ]
        c.executemany(
            '''INSERT INTO products
            (name, category, age_group, size, color, price, stock, description, added_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)''',
            products
        )

    conn.commit()
    conn.close()


# ── Auth Decorators ──────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return wrapper


def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if session.get('role') != 'admin':
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return wrapper


# ── Routes ───────────────────────────────────────────────────
@app.route('/')
def index():
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        conn.close()

        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['name'] = user['name']
            session['role'] = user['role']
            return redirect(url_for('dashboard'))

        flash("Invalid credentials")

    return render_template('login.html')


@app.route('/dashboard')
@login_required
def dashboard():
    conn = get_db()

    products = conn.execute("SELECT * FROM products").fetchall()
    conn.close()

    return render_template('dashboard.html', products=products)


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# ── Product Add ──────────────────────────────────────────────
@app.route('/product/add', methods=['POST'])
@login_required
def add_product():
    name = request.form['name']
    category = request.form['category']
    price = float(request.form['price'])
    stock = int(request.form['stock'])

    conn = get_db()
    conn.execute(
        "INSERT INTO products (name, category, age_group, size, color, price, stock, description, added_by)"
        " VALUES (?, ?, '', '', '', ?, ?, '', ?)",
        (name, category, price, stock, session['user_id'])
    )
    conn.commit()
    conn.close()

    return redirect(url_for('dashboard'))


# ── Admin ───────────────────────────────────────────────────
@app.route('/admin')
@login_required
@admin_required
def admin_panel():
    conn = get_db()

    users = conn.execute("SELECT * FROM users").fetchall()
    products = conn.execute("SELECT * FROM products").fetchall()

    conn.close()

    return render_template('admin.html', users=users, products=products)


# ── API ──────────────────────────────────────────────────────
@app.route('/api/stats')
@login_required
def stats():
    conn = get_db()

    data = {
        "users": conn.execute("SELECT COUNT(*) FROM users").fetchone()[0],
        "products": conn.execute("SELECT COUNT(*) FROM products").fetchone()[0],
        "orders": conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    }

    conn.close()
    return jsonify(data)


# ── SAFE ENTRY POINT (IMPORTANT FOR RENDER) ─────────────────
if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True) ============================================================
# John Mark Cloth - E-Commerce Flask Application
# ============================================================
# A children's clothing e-commerce platform with:
# - Role-based authentication (Admin / User)
# - Product management (CRUD)
# - Analytics dashboard with Chart.js
# - SQLite database with auto-initialization
# ============================================================

from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash, jsonify
)
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os
from functools import wraps
from datetime import datetime, timedelta
import random

# ── App Configuration ────────────────────────────────────────
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'johnmark-cloth-secret-2024')

DATABASE = 'johnmark.db'

# ── Database Helpers ─────────────────────────────────────────

def get_db():
    """Open a new database connection."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row  # Access columns by name
    return conn


def init_db():
    """Create tables and seed default data if they don't exist."""
    conn = get_db()
    c = conn.cursor()

    # Users table
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            name      TEXT    NOT NULL,
            email     TEXT    UNIQUE NOT NULL,
            password  TEXT    NOT NULL,
            role      TEXT    NOT NULL DEFAULT 'user',
            created_at TEXT   NOT NULL DEFAULT (datetime('now'))
        )
    ''')

    # Products table
    c.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT    NOT NULL,
            category    TEXT    NOT NULL,
            age_group   TEXT    NOT NULL,
            size        TEXT    NOT NULL,
            color       TEXT    NOT NULL,
            price       REAL    NOT NULL,
            stock       INTEGER NOT NULL DEFAULT 0,
            description TEXT,
            added_by    INTEGER,
            created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (added_by) REFERENCES users(id)
        )
    ''')

    # Orders table (for analytics)
    c.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            product_id  INTEGER NOT NULL,
            quantity    INTEGER NOT NULL DEFAULT 1,
            total_price REAL    NOT NULL,
            status      TEXT    NOT NULL DEFAULT 'pending',
            ordered_at  TEXT    NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (user_id)    REFERENCES users(id),
            FOREIGN KEY (product_id) REFERENCES products(id)
        )
    ''')

    # ── Seed: Default Admin ──────────────────────────────────
    existing_admin = c.execute(
        "SELECT id FROM users WHERE email = 'admin@example.com'"
    ).fetchone()

    if not existing_admin:
        c.execute(
            "INSERT INTO users (name, email, password, role) VALUES (?, ?, ?, ?)",
            ('Admin', 'admin@example.com',
             generate_password_hash('admin123'), 'admin')
        )

    # ── Seed: Sample Products ────────────────────────────────
    product_count = c.execute("SELECT COUNT(*) FROM products").fetchone()[0]

    if product_count == 0:
        sample_products = [
            ('Floral Frock', 'Dress', '3-5 years', 'S', 'Pink', 599.00, 25,
             'Beautiful floral frock for little girls'),
            ('Denim Dungaree', 'Dungaree', '6-8 years', 'M', 'Blue', 799.00, 18,
             'Comfortable denim dungaree for active kids'),
            ('Cotton Kurta Set', 'Ethnic', '2-4 years', 'XS', 'Yellow', 449.00, 30,
             'Soft cotton kurta with matching pants'),
            ('Striped T-Shirt', 'Casual', '8-10 years', 'L', 'Red', 349.00, 40,
             'Colorful striped casual t-shirt'),
            ('Party Frock', 'Dress', '5-7 years', 'M', 'Purple', 999.00, 12,
             'Elegant party frock with lace trim'),
            ('Cargo Pants', 'Bottom', '9-12 years', 'XL', 'Khaki', 649.00, 22,
             'Durable cargo pants with multiple pockets'),
            ('Printed Onesie', 'Infant', '0-1 years', 'XS', 'White', 299.00, 50,
             'Soft printed onesie for newborns'),
            ('School Uniform Set', 'Uniform', '6-10 years', 'M', 'White/Blue', 549.00, 35,
             'Complete school uniform with shirt and trousers'),
        ]
        c.executemany(
            '''INSERT INTO products
               (name, category, age_group, size, color, price, stock, description, added_by)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)''',
            sample_products
        )

    # ── Seed: Sample Orders ──────────────────────────────────
    order_count = c.execute("SELECT COUNT(*) FROM orders").fetchone()[0]

    if order_count == 0:
        statuses = ['delivered', 'shipped', 'pending', 'cancelled']
        for i in range(30):
            days_ago = random.randint(0, 29)
            date_str = (datetime.now() - timedelta(days=days_ago)).strftime('%Y-%m-%d %H:%M:%S')
            prod_id  = random.randint(1, 8)
            qty      = random.randint(1, 3)
            price    = random.uniform(299, 999) * qty
            c.execute(
                '''INSERT INTO orders (user_id, product_id, quantity, total_price, status, ordered_at)
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (1, prod_id, qty, round(price, 2),
                 random.choice(statuses), date_str)
            )

    conn.commit()
    conn.close()


# ── Auth Decorators ──────────────────────────────────────────

def login_required(f):
    """Redirect to login if user is not authenticated."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to continue.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    """Restrict route to admin users only."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get('role') != 'admin':
            flash('Admin access required.', 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated


# ── Auth Routes ──────────────────────────────────────────────

@app.route('/')
def index():
    """Redirect root to dashboard or login."""
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Handle user login."""
    if 'user_id' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        # Validate inputs
        if not email or not password:
            flash('Please fill in all fields.', 'danger')
            return render_template('login.html')

        conn = get_db()
        user = conn.execute(
            "SELECT * FROM users WHERE email = ?", (email,)
        ).fetchone()
        conn.close()

        if user and check_password_hash(user['password'], password):
            # Set session variables
            session['user_id'] = user['id']
            session['name']    = user['name']
            session['email']   = user['email']
            session['role']    = user['role']
            flash(f"Welcome back, {user['name']}!", 'success')
            return redirect(url_for('admin_panel') if user['role'] == 'admin'
                            else url_for('dashboard'))

        flash('Invalid email or password.', 'danger')

    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    """Handle new user registration."""
    if 'user_id' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        name     = request.form.get('name', '').strip()
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm  = request.form.get('confirm_password', '')

        # Input validation
        errors = []
        if not name or len(name) < 2:
            errors.append('Name must be at least 2 characters.')
        if not email or '@' not in email:
            errors.append('Enter a valid email address.')
        if len(password) < 6:
            errors.append('Password must be at least 6 characters.')
        if password != confirm:
            errors.append('Passwords do not match.')

        if errors:
            for err in errors:
                flash(err, 'danger')
            return render_template('register.html')

        conn = get_db()
        existing = conn.execute(
            "SELECT id FROM users WHERE email = ?", (email,)
        ).fetchone()

        if existing:
            flash('Email already registered. Please login.', 'warning')
            conn.close()
            return render_template('register.html')

        conn.execute(
            "INSERT INTO users (name, email, password, role) VALUES (?, ?, ?, 'user')",
            (name, email, generate_password_hash(password))
        )
        conn.commit()
        conn.close()

        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/logout')
def logout():
    """Clear session and redirect to login."""
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))


# ── Dashboard (User) ─────────────────────────────────────────

@app.route('/dashboard')
@login_required
def dashboard():
    """User dashboard with product listing and stats."""
    conn = get_db()

    # Summary stats
    total_products = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    total_orders   = conn.execute(
        "SELECT COUNT(*) FROM orders WHERE user_id = ?", (session['user_id'],)
    ).fetchone()[0]
    total_spent    = conn.execute(
        "SELECT COALESCE(SUM(total_price), 0) FROM orders WHERE user_id = ? AND status != 'cancelled'",
        (session['user_id'],)
    ).fetchone()[0]
    in_stock       = conn.execute(
        "SELECT COUNT(*) FROM products WHERE stock > 0"
    ).fetchone()[0]

    # All products
    products = conn.execute(
        "SELECT * FROM products ORDER BY created_at DESC"
    ).fetchall()

    # Chart: category-wise product count
    category_data = conn.execute(
        "SELECT category, COUNT(*) as cnt FROM products GROUP BY category"
    ).fetchall()

    # Chart: monthly order trend (last 6 months)
    monthly_orders = conn.execute(
        '''SELECT strftime('%Y-%m', ordered_at) as month,
                  COUNT(*) as cnt,
                  COALESCE(SUM(total_price), 0) as revenue
           FROM orders
           WHERE ordered_at >= datetime('now', '-6 months')
           GROUP BY month ORDER BY month'''
    ).fetchall()

    conn.close()

    return render_template(
        'dashboard.html',
        products=products,
        total_products=total_products,
        total_orders=total_orders,
        total_spent=round(total_spent, 2),
        in_stock=in_stock,
        category_data=[dict(r) for r in category_data],
        monthly_orders=[dict(r) for r in monthly_orders],
    )


# ── Product CRUD ─────────────────────────────────────────────

@app.route('/product/add', methods=['GET', 'POST'])
@login_required
def add_product():
    """Add a new product (any logged-in user)."""
    if request.method == 'POST':
        fields = {
            'name':        request.form.get('name', '').strip(),
            'category':    request.form.get('category', '').strip(),
            'age_group':   request.form.get('age_group', '').strip(),
            'size':        request.form.get('size', '').strip(),
            'color':       request.form.get('color', '').strip(),
            'price':       request.form.get('price', 0),
            'stock':       request.form.get('stock', 0),
            'description': request.form.get('description', '').strip(),
        }

        # Basic validation
        if not all([fields['name'], fields['category'], fields['price']]):
            flash('Name, category, and price are required.', 'danger')
            return render_template('add_product.html')

        try:
            price = float(fields['price'])
            stock = int(fields['stock'])
        except ValueError:
            flash('Price and stock must be valid numbers.', 'danger')
            return render_template('add_product.html')

        conn = get_db()
        conn.execute(
            '''INSERT INTO products
               (name, category, age_group, size, color, price, stock, description, added_by)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (fields['name'], fields['category'], fields['age_group'],
             fields['size'], fields['color'], price, stock,
             fields['description'], session['user_id'])
        )
        conn.commit()
        conn.close()

        flash('Product added successfully!', 'success')
        return redirect(url_for('dashboard'))

    return render_template('add_product.html')


@app.route('/product/edit/<int:product_id>', methods=['GET', 'POST'])
@login_required
def edit_product(product_id):
    """Edit an existing product."""
    conn = get_db()
    product = conn.execute(
        "SELECT * FROM products WHERE id = ?", (product_id,)
    ).fetchone()

    if not product:
        flash('Product not found.', 'danger')
        conn.close()
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        name        = request.form.get('name', '').strip()
        category    = request.form.get('category', '').strip()
        age_group   = request.form.get('age_group', '').strip()
        size        = request.form.get('size', '').strip()
        color       = request.form.get('color', '').strip()
        description = request.form.get('description', '').strip()

        try:
            price = float(request.form.get('price', 0))
            stock = int(request.form.get('stock', 0))
        except ValueError:
            flash('Price and stock must be valid numbers.', 'danger')
            conn.close()
            return render_template('edit_product.html', product=product)

        conn.execute(
            '''UPDATE products
               SET name=?, category=?, age_group=?, size=?, color=?,
                   price=?, stock=?, description=?
               WHERE id=?''',
            (name, category, age_group, size, color,
             price, stock, description, product_id)
        )
        conn.commit()
        conn.close()

        flash('Product updated successfully!', 'success')
        return redirect(url_for('dashboard'))

    conn.close()
    return render_template('edit_product.html', product=product)


@app.route('/product/delete/<int:product_id>', methods=['POST'])
@login_required
def delete_product(product_id):
    """Delete a product."""
    conn = get_db()
    conn.execute("DELETE FROM products WHERE id = ?", (product_id,))
    conn.commit()
    conn.close()
    flash('Product deleted.', 'success')
    return redirect(url_for('dashboard'))


# ── Admin Panel ──────────────────────────────────────────────

@app.route('/admin')
@login_required
@admin_required
def admin_panel():
    """Admin dashboard with full system analytics."""
    conn = get_db()

    # Key metrics
    total_users    = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    total_products = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    total_orders   = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    total_revenue  = conn.execute(
        "SELECT COALESCE(SUM(total_price), 0) FROM orders WHERE status != 'cancelled'"
    ).fetchone()[0]

    # All users
    users = conn.execute(
        "SELECT id, name, email, role, created_at FROM users ORDER BY created_at DESC"
    ).fetchall()

    # All products with stock info
    products = conn.execute(
        "SELECT * FROM products ORDER BY created_at DESC"
    ).fetchall()

    # All orders (latest 20)
    orders = conn.execute(
        '''SELECT o.*, u.name as user_name, p.name as product_name
           FROM orders o
           JOIN users u ON o.user_id = u.id
           JOIN products p ON o.product_id = p.id
           ORDER BY o.ordered_at DESC LIMIT 20'''
    ).fetchall()

    # Chart: orders by status
    status_data = conn.execute(
        "SELECT status, COUNT(*) as cnt FROM orders GROUP BY status"
    ).fetchall()

    # Chart: top 5 products by revenue
    top_products = conn.execute(
        '''SELECT p.name, COALESCE(SUM(o.total_price), 0) as revenue
           FROM products p
           LEFT JOIN orders o ON p.id = o.product_id AND o.status != 'cancelled'
           GROUP BY p.id, p.name
           ORDER BY revenue DESC LIMIT 5'''
    ).fetchall()

    # Chart: daily revenue last 7 days
    daily_revenue = conn.execute(
        '''SELECT strftime('%d %b', ordered_at) as day,
                  COALESCE(SUM(total_price), 0) as revenue
           FROM orders
           WHERE ordered_at >= datetime('now', '-7 days')
             AND status != 'cancelled'
           GROUP BY strftime('%Y-%m-%d', ordered_at)
           ORDER BY ordered_at'''
    ).fetchall()

    # Chart: stock level by category
    stock_by_cat = conn.execute(
        "SELECT category, SUM(stock) as total_stock FROM products GROUP BY category"
    ).fetchall()

    conn.close()

    return render_template(
        'admin.html',
        total_users=total_users,
        total_products=total_products,
        total_orders=total_orders,
        total_revenue=round(total_revenue, 2),
        users=users,
        products=products,
        orders=orders,
        status_data=[dict(r) for r in status_data],
        top_products=[dict(r) for r in top_products],
        daily_revenue=[dict(r) for r in daily_revenue],
        stock_by_cat=[dict(r) for r in stock_by_cat],
    )


@app.route('/admin/delete_user/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    """Admin: delete a user account."""
    if user_id == session['user_id']:
        flash("You cannot delete your own account.", 'danger')
        return redirect(url_for('admin_panel'))
    conn = get_db()
    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    flash('User deleted.', 'success')
    return redirect(url_for('admin_panel'))


# ── API Endpoints (for AJAX) ─────────────────────────────────

@app.route('/api/stats')
@login_required
def api_stats():
    """Return live stats as JSON for dashboard refresh."""
    conn = get_db()
    data = {
        'total_products': conn.execute("SELECT COUNT(*) FROM products").fetchone()[0],
        'total_orders':   conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0],
        'total_revenue':  round(conn.execute(
            "SELECT COALESCE(SUM(total_price), 0) FROM orders WHERE status!='cancelled'"
        ).fetchone()[0], 2),
        'in_stock':       conn.execute(
            "SELECT COUNT(*) FROM products WHERE stock > 0"
        ).fetchone()[0],
    }
    conn.close()
    return jsonify(data)


# ── App Entry Point ──────────────────────────────────────────

if __name__ == '__main__':
    init_db()            # Ensure DB and tables exist
    app.run(debug=True)

# Auto-initialize DB when imported by gunicorn
with app.app_context():
    init_db()
