# ============================================================
# John Mark Cloth - E-Commerce Flask Application
# ============================================================
# A children's clothing e-commerce platform with:
# - Role-based authentication (Admin / User)
# - Product management (CRUD)
# - Analytics dashboard with Chart.js
# - SQLite database with auto-initialization
# ============================================================

fromflaskimport (
    Flask, render_template, request, redirect,
    url_for, session, flash, jsonify
)
fromwerkzeug.security importgenerate_password_hash, check_password_hash
importlsqlite3
importos
fromfunctools importwraps
fromdatetime importdatetime, timedelta
importrandom

# ── App Configuration ────────────────────────────────────────
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'johnmark-cloth-secret-2024')

DATABASE = 'johnmark.db'

# ── Database Helpers ─────────────────────────────────────────

defget_db():
    """Open a new database connection."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row  # Access columns by name
    returnconn


definit_db():
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

    ifnotexisting_admin:
        c.execute(
            "INSERT INTO users (name, email, password, role) VALUES (?, ?, ?, ?)",
            ('Admin', 'admin@example.com',
             generate_password_hash('admin123'), 'admin')
        )

    # ── Seed: Sample Products ────────────────────────────────
    product_count = c.execute("SELECT COUNT(*) FROM products").fetchone()[0]

    ifproduct_count == 0:
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

    iforder_count == 0:
        statuses = ['delivered', 'shipped', 'pending', 'cancelled']
        foriin range(30):
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

deflogin_required(f):
    """Redirect to login if user is not authenticated."""
    @wraps(f)
    defdecorated(args,kwargs):
        'user_id' notin session:
            flash('Please login to continue.', 'warning')
            returnredirect(url_for('login'))
        returnf(args,kwargs)
    returndecorated


defadmin_required(f):
    """Restrict route to admin users only."""
    @wraps(f)
    defdecorated(args,kwargs):
        ifsession.get('role') != 'admin':
            flash('Admin access required.', 'danger')
            returnredirect(url_for('dashboard'))
        returnf(args,kwargs)
    returndecorated


# ── DB Init on First Request ─────────────────────────────────
# Uses before_request so it works safely with both `python app.py`
# and WSGI servers like gunicorn — no module-level app context needed.

@app.before_request
definitialize_db_once():
    """Initialize DB on the very first request, then deregister itself."""
    app.before_request_funcs.remove(initialize_db_once)
    init_db()


# ── Auth Routes ──────────────────────────────────────────────

@app.route('/')
defindex():
    """Redirect root to dashboard or login."""
     'user_id' insession:
        returnredirect(url_for('dashboard'))
    returnredirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
deflogin():
    """Handle user login."""
    'user_id' insession:
        returnredirect(url_for('dashboard'))

    ifrequest.method == 'POST':
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        ifnot email ornot password:
            flash('Please fill in all fields.', 'danger')
            returnrender_template('login.html')

        conn = get_db()
        user = conn.execute(
            "SELECT * FROM users WHERE email = ?", (email,)
        ).fetchone()
        conn.close()

        ifuser andcheck_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['name']    = user['name']
            session['email']   = user['email']
            session['role']    = user['role']
            flash(f"Welcome back, {user['name']}!", 'success')
            returnredirect(url_for('admin_panel') ifuser['role'] == 'admin'
                            elseurl_for('dashboard'))

        flash('Invalid email or password.', 'danger')

    returnrender_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
defregister():
    """Handle new user registration."""
    'user_id'. in session:
        returnredirect(url_for('dashboard'))

    ifrequest.method == 'POST':
        name     = request.form.get('name', '').strip()
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm  = request.form.get('confirm_password', '')

        errors = []
        ifnotname orlen(name) < 2:
            errors.append('Name must be at least 2 characters.')
        ifnot emailor '@' notin email:
            errors.append('Enter a valid email address.')
        iflen(password) < 6:
            errors.append('Password must be at least 6 characters.')
        ifpassword != confirm:
            errors.append('Passwords do not match.')

        iferrors:
            forerr inerrors:
                flash(err, 'danger')
            returnrender_template('register.html')

        conn = get_db()
        existing = conn.execute(
            "SELECT id FROM users WHERE email = ?", (email,)
        ).fetchone()

        ifexisting:
            flash('Email already registered. Please login.', 'warning')
            conn.close()
            returnrender_template('register.html')

        conn.execute(
            "INSERT INTO users (name, email, password, role) VALUES (?, ?, ?, 'user')",
            (name, email, generate_password_hash(password))
        )
        conn.commit()
        conn.close()

        flash('Registration successful! Please login.', 'success')
        returnredirect(url_for('login'))

    returnrender_template('register.html')


@app.route('/logout')
deflogout():
    """Clear session and redirect to login."""
    session.clear()
    flash('You have been logged out.', 'info')
    returnredirect(url_for('login'))


# ── Dashboard (User) ─────────────────────────────────────────

@app.route('/dashboard')
@login_required
defdashboard():
    """User dashboard with product listing and stats."""
    conn = get_db()

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

    products = conn.execute(
        "SELECT * FROM products ORDER BY created_at DESC"
    ).fetchall()

    category_data = conn.execute(
        "SELECT category, COUNT(*) as cnt FROM products GROUP BY category"
    ).fetchall()

    monthly_orders = conn.execute(
        '''SELECT strftime('%Y-%m', ordered_at) as month,
                  COUNT(*) as cnt,
                  COALESCE(SUM(total_price), 0) as revenue
           FROM orders
           WHERE ordered_at >= datetime('now', '-6 months')
           GROUP BY month ORDER BY month'''
    ).fetchall()

    conn.close()

    returnrender_template(
        'dashboard.html',
        products=products,
        total_products=total_products,
        total_orders=total_orders,
        total_spent=round(total_spent, 2),
        in_stock=in_stock,
        category_data=[dict(r) forrin category_data],
        monthly_orders=[dict(r) forrin monthly_orders],
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

        ifnotall([fields['name'], fields['category'], fields['price']]):
            flash('Name, category, and price are required.', 'danger')
            returnrender_template('add_product.html')

        Try:
            price = float(fields['price'])
            stock = int(fields['stock'])
        exceptValueError:
            flash('Price and stock must be valid numbers.', 'danger')
            returnrender_template('add_product.html')

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
        returnredirect(url_for('dashboard'))

    returnrender_template('add_product.html')


@app.route('/product/edit/<int:product_id>', methods=['GET', 'POST'])
@login_required
defedit_product(product_id):
    """Edit an existing product."""
    conn = get_db()
    product = conn.execute(
        "SELECT * FROM products WHERE id = ?", (product_id,)
    ).fetchone()

    ifnotproduct:
        flash('Product not found.', 'danger')
        conn.close()
        returnredirect(url_for('dashboard'))

    ifrequest.method == 'POST':
        name        = request.form.get('name', '').strip()
        category    = request.form.get('category', '').strip()
        age_group   = request.form.get('age_group', '').strip()
        size        = request.form.get('size', '').strip()
        color       = request.form.get('color', '').strip()
        description = request.form.get('description', '').strip()
       
        Try:
            price = float(request.form.get('price', 0))
            stock = int(request.form.get('stock', 0))
        exceptValueError:
            flash('Price and stock must be valid numbers.', 'danger')
            conn.close()
            returnrender_template('edit_product.html', product=product)

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
        returnredirect(url_for('dashboard'))

    conn.close()
    returnrender_template('edit_product.html', product=product)


@app.route('/product/delete/<int:product_id>', methods=['POST'])
@login_required
defdelete_product(product_id):
    """Delete a product."""
    conn = get_db()
    conn.execute("DELETE FROM products WHERE id = ?", (product_id,))
    conn.commit()
    conn.close()
    flash('Product deleted.', 'success')
    returnredirect(url_for('dashboard'))


# ── Admin Panel ──────────────────────────────────────────────

@app.route('/admin')
@login_required
@admin_required
defadmin_panel():
    """Admin dashboard with full system analytics."""
    conn = get_db()

    total_users    = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    total_products = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    total_orders   = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    total_revenue  = conn.execute(
        "SELECT COALESCE(SUM(total_price), 0) FROM orders WHERE status != 'cancelled'"
    ).fetchone()[0]

    users = conn.execute(
        "SELECT id, name, email, role, created_at FROM users ORDER BY created_at DESC"
    ).fetchall()

    products = conn.execute(
        "SELECT * FROM products ORDER BY created_at DESC"
    ).fetchall()

    orders = conn.execute(
        '''SELECT o.*, u.name as user_name, p.name as product_name
           FROM orders o
           JOIN users u ON o.user_id = u.id
           JOIN products p ON o.product_id = p.id
           ORDER BY o.ordered_at DESC LIMIT 20'''
    ).fetchall()

    status_data = conn.execute(
        "SELECT status, COUNT(*) as cnt FROM orders GROUP BY status"
    ).fetchall()

    top_products = conn.execute(
        '''SELECT p.name, COALESCE(SUM(o.total_price), 0) as revenue
           FROM products p
           LEFT JOIN orders o ON p.id = o.product_id AND o.status != 'cancelled'
           GROUP BY p.id, p.name
           ORDER BY revenue DESC LIMIT 5'''
    ).fetchall()

    daily_revenue = conn.execute(
        '''SELECT strftime('%d %b', ordered_at) as day,
                  COALESCE(SUM(total_price), 0) as revenue
           FROM orders
           WHERE ordered_at >= datetime('now', '-7 days')
             AND status != 'cancelled'
           GROUP BY strftime('%Y-%m-%d', ordered_at)
           ORDER BY ordered_at'''
    ).fetchall()

    stock_by_cat = conn.execute(
        "SELECT category, SUM(stock) as total_stock FROM products GROUP BY category"
    ).fetchall()

    conn.close()

    returnrender_template(
        'admin.html',
        total_users=total_users,
        total_products=total_products,
        total_orders=total_orders,
        total_revenue=round(total_revenue, 2),
        users=users,
        products=products,
        orders=orders,
        status_data=[dict(r) forrin status_data],
        top_products=[dict(r) forrin top_products],
        daily_revenue=[dict(r) forrin daily_revenue],
        stock_by_cat=[dict(r) forrin stock_by_cat],
    )


@app.route('/admin/delete_user/<int:user_id>', methods=['POST'])
@login_required
@admin_required
defdelete_user(user_id):
    """Admin: delete a user account."""
    ifuser_id == session['user_id']:
        flash("You cannot delete your own account.", 'danger')
        returnredirect(url_for('admin_panel'))
    conn = get_db()
    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    flash('User deleted.', 'success')
    returnredirect(url_for('admin_panel'))


# ── API Endpoints (for AJAX) ─────────────────────────────────

@app.route('/api/stats')
@login_required
defapi_stats():
    """Return live stats as JSON for dashboard refresh."""
    conn = get_db()
    data = {
        'total_products': conn.execute(
            "SELECT COUNT(*) FROM products"
        ).fetchone()[0],
        'total_orders': conn.execute(
            "SELECT COUNT(*) FROM orders"
        ).fetchone()[0],
        'total_revenue': round(conn.execute(
            "SELECT COALESCE(SUM(total_price), 0) FROM orders WHERE status != 'cancelled'"
        ).fetchone()[0], 2),
        'in_stock': conn.execute(
            "SELECT COUNT(*) FROM products WHERE stock > 0"
        ).fetchone()[0],
    }
    conn.close()
    returnjsonify(data)


# ── App Entry Point ──────────────────────────────────────────

if__name__ == '__main__':
    init_db()
    app.run(debug=True)
