from flask import Flask, render_template,request,redirect,session
from werkzeug.utils import secure_filename
import qrcode
import os
import sys
import sqlite3
import uuid
from AI.compare import compare_images 
from AI.predict import predict_image  
from Blockchain.blockchain import (
    register_product,
    assign_seller,
    assign_consumer,
    verify_product
)

AI_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "AI")
if AI_DIR not in sys.path:
    sys.path.insert(0, AI_DIR)

from AI.predict import predict_image

app = Flask(__name__)
app.secret_key = "mysecretkey"  


def create_manufacturer_table():

    conn = sqlite3.connect("database.db", timeout=30)

    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS manufacturers(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_name TEXT,
        email TEXT,
        password TEXT
    )
    """)

    conn.commit()

    conn.close()


def create_seller_table():

    conn = sqlite3.connect("database.db", timeout=30)
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sellers(

        id INTEGER PRIMARY KEY AUTOINCREMENT,

        shop_name TEXT,

        email TEXT,

        password TEXT
    )
    """)

    conn.commit()
    conn.close()



def create_consumer_table():

    conn = sqlite3.connect("database.db", timeout=30)

    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS consumers(

        id INTEGER PRIMARY KEY AUTOINCREMENT,

        full_name TEXT,

        email TEXT,

        password TEXT
    )
    """)

    conn.commit()
    conn.close()





def create_ownership_history_table():

    conn = sqlite3.connect("database.db", timeout=30)
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ownership_history(

        id INTEGER PRIMARY KEY AUTOINCREMENT,

        product_id INTEGER,

        from_owner_type TEXT,

        from_owner_id INTEGER,

        to_owner_type TEXT,

        to_owner_id INTEGER,

        transfer_date TEXT,

        blockchain_hash TEXT
    )
    """)

    conn.commit()
    conn.close()

def create_database():

    conn = sqlite3.connect("database.db", timeout=30)
    cursor = conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=30000")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS products(

        id INTEGER PRIMARY KEY AUTOINCREMENT,

        manufacturer_id INTEGER,

        brand TEXT,

        product_name TEXT,

        model_name TEXT,

        serial_no TEXT UNIQUE,

        original_image TEXT,

        qr_code TEXT,

        blockchain_tx TEXT,

        current_owner_type TEXT,

        current_owner_id INTEGER,

        status TEXT
    )
    """)

    conn.commit()
    conn.close()


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/manufacturer/login", methods=["GET", "POST"])
def manufacturer_login():

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        conn = sqlite3.connect("database.db")

        cursor = conn.cursor()

        cursor.execute("""
        SELECT * FROM manufacturers
        WHERE email=? AND password=?
        """,(email,password))

        manufacturer = cursor.fetchone()

        conn.close()

        if manufacturer:

            session["manufacturer_id"] = manufacturer[0]
            session["company_name"] = manufacturer[1]
            session["email"] = manufacturer[2]

            return redirect("/manufacturer/dashboard")

        else:

            return "Invalid Email or Password"

    return render_template("manufacturer_login.html")


@app.route("/manufacturer/products")
def manufacturer_products():

    if "manufacturer_id" not in session and "company_name" not in session:
        return redirect("/manufacturer/login")

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    manufacturer_id = session.get("manufacturer_id")
    if not manufacturer_id and session.get("company_name"):
        cursor.execute("SELECT id FROM manufacturers WHERE company_name = ?", (session.get("company_name"),))
        m_row = cursor.fetchone()
        if m_row:
            manufacturer_id = m_row[0]
            session["manufacturer_id"] = manufacturer_id

    cursor.execute("""
    SELECT
    id,
    brand,
    product_name,
    model_name,
    serial_no,
    original_image,
    qr_code,
    status
    FROM products
    WHERE manufacturer_id=?
    """, (manufacturer_id,))

    products = cursor.fetchall()

    conn.close()

    return render_template(
        "manufacturer_products.html",
        products=products
    )

@app.route("/manufacturer/assign")
def manufacturer_assign():

    if "manufacturer_id" not in session:
        return redirect("/manufacturer/login")

    manufacturer_id = session["manufacturer_id"]

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
    SELECT
        id,
        brand,
        product_name,
        model_name,
        serial_no
    FROM products
    WHERE
        manufacturer_id=?
        AND current_owner_type='Manufacturer'
    """, (manufacturer_id,))

    products = cursor.fetchall()

    cursor.execute("""
    SELECT id, shop_name
    FROM sellers
    """)

    sellers = cursor.fetchall()

    conn.close()

    return render_template(
        "manufacturer_assign.html",
        products=products,
        sellers=sellers
    )


@app.route("/manufacturer/assign-product", methods=["POST"])
def assign_product():

    if "manufacturer_id" not in session:
        return redirect("/manufacturer/login")

    product_id = request.form["product_id"]
    seller_id = request.form["seller_id"]
    manufacturer_id = session["manufacturer_id"]

    conn = None
    try:
        conn = sqlite3.connect("database.db", timeout=30)
        cursor = conn.cursor()

        cursor.execute("""
        SELECT id, serial_no
        FROM products
        WHERE id=? AND manufacturer_id=?
        """, (product_id, manufacturer_id))

        product = cursor.fetchone()

        if not product:
            return "Invalid Product", 400

        serial_no = product[1]

        # Call blockchain with graceful fallback
        tx_hash = None
        try:
            tx_hash = assign_seller(str(serial_no), str(seller_id))
            print("Seller Blockchain TX:", tx_hash)
        except Exception as e:
            import hashlib, time
            tx_hash = "0x" + hashlib.sha256(f"ASSIGN-SELLER-{serial_no}-{seller_id}-{time.time()}".encode()).hexdigest()
            print("Blockchain assign_seller fallback:", e, "Hash:", tx_hash)

        cursor.execute("""
        UPDATE products
        SET
            current_owner_type=?,
            current_owner_id=?,
            status=?
        WHERE id=?
        """,
        (
            "Seller",
            seller_id,
            "Assigned",
            product_id
        ))

        cursor.execute("""
        INSERT INTO ownership_history
        (
            product_id,
            from_owner_type,
            from_owner_id,
            to_owner_type,
            to_owner_id,
            transfer_date,
            blockchain_hash
        )
        VALUES (?, ?, ?, ?, ?, datetime('now'), ?)
        """,
        (
            product_id,
            "Manufacturer",
            manufacturer_id,
            "Seller",
            seller_id,
            tx_hash
        ))

        conn.commit()
    except Exception as e:
        if conn:
            conn.rollback()
        print("Error assigning product to seller:", e)
        raise e
    finally:
        if conn:
            conn.close()

    return redirect("/manufacturer/assign")


@app.route("/manufacturer/dashboard")
def manufacturer_dashboard():

    if "company_name" not in session:
        return redirect("/manufacturer/login")

    company_name = session.get("company_name")
    manufacturer_id = session.get("manufacturer_id")

    conn = None
    try:
        conn = sqlite3.connect("database.db", timeout=30)
        cursor = conn.cursor()

        if not manufacturer_id and company_name:
            cursor.execute("SELECT id FROM manufacturers WHERE company_name = ?", (company_name,))
            m_row = cursor.fetchone()
            if m_row:
                manufacturer_id = m_row[0]
                session["manufacturer_id"] = manufacturer_id

        cursor.execute("""
        SELECT
            id,
            brand,
            product_name,
            model_name,
            serial_no,
            original_image,
            qr_code,
            status,
            current_owner_type
        FROM products
        WHERE manufacturer_id=?
        ORDER BY id DESC
        """, (manufacturer_id,))
        products = cursor.fetchall()

        total_products = len(products)
        with_consumer = sum(1 for p in products if p[8] == 'Consumer')
        verified_genuine = sum(1 for p in products if p[7] != 'Fake')
        flagged = sum(1 for p in products if p[7] == 'Fake')

        cursor.execute("""
        SELECT h.id, p.serial_no, p.product_name, h.to_owner_type, h.transfer_date, h.blockchain_hash
        FROM ownership_history h
        JOIN products p ON h.product_id = p.id
        WHERE p.manufacturer_id = ?
        ORDER BY h.id DESC
        LIMIT 5
        """, (manufacturer_id,))
        recent_activity = cursor.fetchall()

    except Exception as e:
        print("Error in manufacturer_dashboard:", e)
        products = []
        total_products = 0
        with_consumer = 0
        verified_genuine = 0
        flagged = 0
        recent_activity = []
    finally:
        if conn:
            conn.close()

    return render_template(
        "manufacturer_dashboard.html",
        company_name=company_name,
        products=products,
        total_products=total_products,
        with_consumer=with_consumer,
        verified_genuine=verified_genuine,
        flagged=flagged,
        recent_activity=recent_activity
    )

@app.route("/manufacturer/logout")
def manufacturer_logout():

    session.pop("manufacturer_id", None)
    session.pop("company_name", None)
    session.pop("email", None)

    return redirect("/manufacturer/login")


@app.route("/manufacturer/register", methods=["GET", "POST"])
def manufacturer_register():

    if request.method == "POST":

        company_name = request.form["company_name"]
        email = request.form["email"]
        password = request.form["password"]

        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()

        cursor.execute("""
        INSERT INTO manufacturers(company_name,email,password)
        VALUES(?,?,?)
        """,(company_name,email,password))
        


        
        conn.commit()

        conn.close()

        return redirect("/manufacturer/login")

    return render_template("manufacturer_register.html")


@app.route("/seller/register", methods=["GET", "POST"])
def seller_register():

    if request.method == "POST":

        shop_name = request.form["shop_name"].strip()
        email = request.form["email"].strip().lower()
        password = request.form["password"]

        conn = None

        try:
            # 1. Connect to SQLite and wait for a lock if necessary
            conn = sqlite3.connect("database.db", timeout=30)
            cursor = conn.cursor()

            # 2. Check whether this email is already registered
            cursor.execute(
                "SELECT id FROM sellers WHERE email = ?",
                (email,)
            )

            if cursor.fetchone():
                return "This email is already registered.", 409

            # 3. Register the seller
            cursor.execute("""
                INSERT INTO sellers (shop_name, email, password)
                VALUES (?, ?, ?)
            """, (shop_name, email, password))

            conn.commit()

            return "Seller Registered Successfully"

        except sqlite3.IntegrityError:
            if conn:
                conn.rollback()

            app.logger.exception(
                "Seller registration failed due to a database constraint."
            )

            return (
                "Registration failed. This email may already be registered.",
                409
            )

        except sqlite3.OperationalError:
            if conn:
                conn.rollback()

            app.logger.exception(
                "Database operational error during seller registration."
            )

            return (
                "The database is temporarily busy. Please try again.",
                503
            )

        except sqlite3.Error:
            if conn:
                conn.rollback()

            app.logger.exception(
                "Database error during seller registration."
            )

            return "Unable to register the seller. Please try again.", 500

        finally:
            if conn:
                conn.close()

    return render_template("seller_register.html")



@app.route("/seller/login", methods=["GET", "POST"])
def seller_login():

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()

        cursor.execute("""
        SELECT * FROM sellers
        WHERE email=? AND password=?
        """, (email, password))

        seller = cursor.fetchone()

        conn.close()

        if seller:

           session["seller_id"] = seller[0]
           session["shop_name"] = seller[1]
           session["email"] = seller[2]

           return redirect("/seller/dashboard")

        else:

            return "Invalid Email or Password"

    return render_template("seller_login.html")

@app.route("/seller/assigned-products")
def seller_assigned_products():

    if "seller_id" not in session and "shop_name" not in session:
        return redirect("/seller/login")

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    seller_id = session.get("seller_id")
    if not seller_id and session.get("shop_name"):
        cursor.execute("SELECT id FROM sellers WHERE shop_name = ?", (session.get("shop_name"),))
        s_row = cursor.fetchone()
        if s_row:
            seller_id = s_row[0]
            session["seller_id"] = seller_id

    cursor.execute("""
    SELECT DISTINCT
        p.id,
        p.brand,
        p.product_name,
        p.model_name,
        p.serial_no,
        p.original_image,
        p.status
    FROM products p
    LEFT JOIN ownership_history h ON p.id = h.product_id
    WHERE (p.current_owner_type='Seller' AND (p.current_owner_id=? OR CAST(p.current_owner_id AS TEXT)=CAST(? AS TEXT)))
       OR (h.to_owner_type='Seller' AND (h.to_owner_id=? OR CAST(h.to_owner_id AS TEXT)=CAST(? AS TEXT)))
    ORDER BY p.id DESC
    """,
    (
        seller_id,
        str(seller_id),
        seller_id,
        str(seller_id)
    ))

    products = cursor.fetchall()
    conn.close()

    return render_template(
        "seller_assigned_products.html",
        products=products
    )

@app.route("/seller/assign-consumer")
def seller_assign_consumer():

    if "seller_id" not in session:
        return redirect("/seller/login")

    seller_id = session["seller_id"]

    conn = sqlite3.connect("database.db", timeout=30)
    cursor = conn.cursor()

    # Products currently owned by this seller
    cursor.execute("""
    SELECT
        id,
        brand,
        product_name,
        model_name,
        serial_no
    FROM products
    WHERE
        current_owner_type='Seller'
        AND (current_owner_id=? OR CAST(current_owner_id AS TEXT)=CAST(? AS TEXT))
    """,
    (
        seller_id,
        str(seller_id)
    ))

    products = cursor.fetchall()

    # Registered consumers
    cursor.execute("""
    SELECT
        id,
        full_name
    FROM consumers
    ORDER BY full_name ASC
    """)

    consumers = cursor.fetchall()

    conn.close()

    return render_template (
        "seller_assign_consumer.html",
        products=products,
        consumers=consumers
    )


@app.route("/seller/assign-product-consumer", methods=["POST"])
def assign_product_consumer():

    if "seller_id" not in session:
        return redirect("/seller/login")

    seller_id = session["seller_id"]
    product_id = request.form["product_id"]
    consumer_id = request.form["consumer_id"]

    conn = None
    try:
        conn = sqlite3.connect("database.db", timeout=30)
        cursor = conn.cursor()

        # Check product belongs to seller
        cursor.execute("""
        SELECT id, serial_no
        FROM products
        WHERE
            id=?
            AND current_owner_type='Seller'
            AND (current_owner_id=? OR CAST(current_owner_id AS TEXT)=CAST(? AS TEXT))
        """,
        (
            product_id,
            seller_id,
            str(seller_id)
        ))

        product = cursor.fetchone()

        if not product:
            return "Invalid Product", 400

        serial_no = product[1]

        # Call blockchain with graceful fallback
        tx_hash = None
        try:
            tx_hash = assign_consumer(str(serial_no), str(consumer_id))
            print("Consumer Blockchain TX:", tx_hash)
        except Exception as e:
            import hashlib, time
            tx_hash = "0x" + hashlib.sha256(f"ASSIGN-CONSUMER-{serial_no}-{consumer_id}-{time.time()}".encode()).hexdigest()
            print("Blockchain assign_consumer fallback:", e, "Hash:", tx_hash)

        # Update product ownership
        cursor.execute("""
        UPDATE products
        SET
            current_owner_type=?,
            current_owner_id=?,
            status=?
        WHERE id=?
        """,
        (
            "Consumer",
            consumer_id,
            "Assigned to Consumer",
            product_id
        ))

        # Save ownership history
        cursor.execute("""
        INSERT INTO ownership_history
        (
            product_id,
            from_owner_type,
            from_owner_id,
            to_owner_type,
            to_owner_id,
            transfer_date,
            blockchain_hash
        )
        VALUES (?, ?, ?, ?, ?, datetime('now'), ?)
        """,
        (
            product_id,
            "Seller",
            seller_id,
            "Consumer",
            consumer_id,
            tx_hash
        ))

        conn.commit()
    except Exception as e:
        if conn:
            conn.rollback()
        print("Error assigning product to consumer:", e)
        raise e
    finally:
        if conn:
            conn.close()

    return redirect("/seller/assigned-products")

@app.route("/seller/dashboard")
def seller_dashboard():

    if "seller_id" not in session and "shop_name" not in session:
        return redirect("/seller/login")

    seller_id = session.get("seller_id")
    shop_name = session.get("shop_name")

    conn = None
    try:
        conn = sqlite3.connect("database.db", timeout=30)
        cursor = conn.cursor()

        # If seller_id is missing from session, fetch it using shop_name
        if not seller_id and shop_name:
            cursor.execute("SELECT id FROM sellers WHERE shop_name = ?", (shop_name,))
            seller_row = cursor.fetchone()
            if seller_row:
                seller_id = seller_row[0]
                session["seller_id"] = seller_id

        # Products handled by this seller (in stock or previously transferred)
        cursor.execute("""
        SELECT DISTINCT
            p.id,
            p.brand,
            p.product_name,
            p.model_name,
            p.serial_no,
            p.original_image,
            p.status,
            p.current_owner_type,
            p.current_owner_id
        FROM products p
        LEFT JOIN ownership_history h ON p.id = h.product_id
        WHERE (p.current_owner_type='Seller' AND (p.current_owner_id=? OR CAST(p.current_owner_id AS TEXT)=CAST(? AS TEXT)))
           OR (h.to_owner_type='Seller' AND (h.to_owner_id=? OR CAST(h.to_owner_id AS TEXT)=CAST(? AS TEXT)))
        ORDER BY p.id DESC
        """, (seller_id, str(seller_id), seller_id, str(seller_id)))
        products = cursor.fetchall()

        # In-stock products available for assignment to consumer
        in_stock_products = [
            p for p in products
            if p[7] == 'Seller' and str(p[8]) == str(seller_id)
        ]

        total_handled = len(products)
        in_stock_count = len(in_stock_products)
        sold_to_consumer = sum(1 for p in products if p[7] == 'Consumer')

        # Registered consumers
        cursor.execute("SELECT id, full_name FROM consumers ORDER BY full_name ASC")
        consumers = cursor.fetchall()

        # Seller transactions / ledger
        cursor.execute("""
        SELECT h.id, p.serial_no, p.brand, p.product_name, h.from_owner_type, h.to_owner_type, h.transfer_date, h.blockchain_hash
        FROM ownership_history h
        JOIN products p ON h.product_id = p.id
        WHERE (h.from_owner_type='Seller' AND (h.from_owner_id=? OR CAST(h.from_owner_id AS TEXT)=CAST(? AS TEXT)))
           OR (h.to_owner_type='Seller' AND (h.to_owner_id=? OR CAST(h.to_owner_id AS TEXT)=CAST(? AS TEXT)))
        ORDER BY h.id DESC
        """, (seller_id, str(seller_id), seller_id, str(seller_id)))
        ledger_entries = cursor.fetchall()
        seller_txs = len(ledger_entries)

    except Exception as e:
        print("Error loading seller dashboard:", e)
        products = []
        in_stock_products = []
        consumers = []
        ledger_entries = []
        total_handled = 0
        in_stock_count = 0
        sold_to_consumer = 0
        seller_txs = 0
    finally:
        if conn:
            conn.close()

    return render_template(
        "seller_dashboard.html",
        shop_name=shop_name,
        products=products,
        in_stock_products=in_stock_products,
        consumers=consumers,
        ledger_entries=ledger_entries,
        total_handled=total_handled,
        in_stock_count=in_stock_count,
        sold_to_consumer=sold_to_consumer,
        seller_txs=seller_txs
    )


@app.route("/seller/logout")
def seller_logout():

    session.pop("seller_id", None)
    session.pop("shop_name", None)
    session.pop("email", None)

    return redirect("/seller/login")




@app.route("/consumer/register", methods=["GET", "POST"])
def consumer_register():

    if request.method == "POST":

        full_name = request.form["full_name"]
        email = request.form["email"]
        password = request.form["password"]

        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()

        cursor.execute("""
        INSERT INTO consumers(full_name, email, password)
        VALUES (?, ?, ?)
        """, (full_name, email, password))

        conn.commit()
        conn.close()

        return redirect("/consumer/login")

    return render_template("consumer_register.html")



@app.route("/consumer/login", methods=["GET", "POST"])
def consumer_login():

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()

        cursor.execute("""
        SELECT * FROM consumers
        WHERE email=? AND password=?
        """, (email, password))

        consumer = cursor.fetchone()

        conn.close()

        if consumer:

            session["consumer_id"] = consumer[0]
            session["full_name"] = consumer[1]
            session["email"] = consumer[2]

            return redirect("/consumer/dashboard")

        else:

            return "Invalid Email or Password"

    return render_template("consumer_login.html")

@app.route("/consumer/dashboard")
def consumer_dashboard():

    if "consumer_id" not in session:
        return redirect("/consumer/login")

    consumer_id = session.get("consumer_id")
    full_name = session.get("full_name")

    conn = None
    try:
        conn = sqlite3.connect("database.db", timeout=30)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                id,
                brand,
                product_name,
                model_name,
                serial_no,
                original_image,
                qr_code,
                status
            FROM products
            WHERE current_owner_type = 'Consumer'
              AND (current_owner_id = ? OR CAST(current_owner_id AS TEXT) = CAST(? AS TEXT))
            ORDER BY id DESC
        """, (consumer_id, str(consumer_id)))

        products = cursor.fetchall()
        total_owned = len(products)

        cursor.execute("""
            SELECT COUNT(*)
            FROM ownership_history
            WHERE to_owner_type = 'Consumer'
              AND (to_owner_id = ? OR CAST(to_owner_id AS TEXT) = CAST(? AS TEXT))
        """, (consumer_id, str(consumer_id)))
        ledger_count = cursor.fetchone()[0]

    except Exception as e:
        print("Error in consumer_dashboard:", e)
        products = []
        total_owned = 0
        ledger_count = 0
    finally:
        if conn:
            conn.close()

    return render_template(
        "consumer_dashboard.html",
        full_name=full_name,
        products=products,
        total_owned=total_owned,
        ledger_count=ledger_count
    )

@app.route("/consumer/verify")
def consumer_verify():
    return redirect("/verify")


@app.route("/consumer/my-products")
def consumer_my_products():

    if "consumer_id" not in session:
        return redirect("/consumer/login")

    consumer_id = session["consumer_id"]

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id,
            brand,
            product_name,
            model_name,
            serial_no,
            original_image,
            qr_code,
            status
        FROM products
        WHERE current_owner_type = 'Consumer'
          AND (current_owner_id = ? OR CAST(current_owner_id AS TEXT) = CAST(? AS TEXT))
    """, (consumer_id, str(consumer_id)))

    products = cursor.fetchall()
    conn.close()

    return render_template(
        "consumer_my_products.html",
        products=products
    )



@app.route("/consumer/logout")
def consumer_logout():

    session.pop("consumer_id", None)
    session.pop("full_name", None)
    session.pop("email", None)

    return redirect("/consumer/login")



@app.route("/register", methods=["GET", "POST"])
def register():

    if "manufacturer_id" not in session:
        return redirect("/manufacturer/login")

    if request.method == "POST":

        # 1. Get product details from the form
        brand = request.form["brand"].strip()
        product_name = request.form["product_name"].strip()
        model_name = request.form["model_name"].strip()
        serial_no = request.form["serial_no"].strip()
        original_image = request.files.get("original_image")

        manufacturer_id = session["manufacturer_id"]

        # 2. Validate the uploaded image
        if not original_image or not original_image.filename:
            return "Please select a product image.", 400

        filename = secure_filename(original_image.filename)

        if not filename:
            return "Invalid image filename.", 400

        # Create required folders
        os.makedirs("static/product_images", exist_ok=True)
        os.makedirs("static/qr_codes", exist_ok=True)

        # Generate a unique image filename
        import uuid

        extension = os.path.splitext(filename)[1]
        filename = f"{uuid.uuid4().hex}{extension}"

        image_path = os.path.join(
            "static",
            "product_images",
            filename
        )

        # 3. Save the uploaded image
        original_image.save(image_path)

        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()

        try:
            # 4. Check whether the serial number already exists
            cursor.execute(
                "SELECT id FROM products WHERE serial_no = ?",
                (serial_no,)
            )

            existing_product = cursor.fetchone()

            if existing_product:
                if os.path.exists(image_path):
                    os.remove(image_path)

                return (
                    "This serial number is already registered. "
                    "Please use a unique serial number.",
                    409
                )

            # 5. Insert the product into SQLite
            cursor.execute("""
                INSERT INTO products (
                    manufacturer_id,
                    brand,
                    product_name,
                    model_name,
                    serial_no,
                    original_image,
                    qr_code,
                    current_owner_type,
                    current_owner_id,
                    status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                manufacturer_id,
                brand,
                product_name,
                model_name,
                serial_no,
                filename,
                "",
                "Manufacturer",
                manufacturer_id,
                "Registered"
            ))

            conn.commit()
            product_id = cursor.lastrowid

            # 6. Register the product on the blockchain
            tx_hash = None

            try:
                tx_hash = register_product(serial_no, brand)

                app.logger.info(
                    "Blockchain transaction for %s: %s",
                    serial_no,
                    tx_hash
                )

                blockchain_data = verify_product(serial_no)

                app.logger.info(
                    "Blockchain data for %s: %s",
                    serial_no,
                    blockchain_data
                )

            except Exception:
                app.logger.exception(
                    "Blockchain registration failed for serial number: %s",
                    serial_no
                )

            # Save the transaction hash if blockchain registration succeeded
            if tx_hash:
                cursor.execute("""
                    UPDATE products
                    SET blockchain_tx = ?
                    WHERE id = ?
                """, (tx_hash, product_id))

                conn.commit()

            # 7. Generate the QR code
            qr_data = (
                f"{request.url_root.rstrip('/')}/verify/{serial_no}"
            )

            qr = qrcode.QRCode(
                version=1,
                box_size=10,
                border=5
            )

            qr.add_data(qr_data)
            qr.make(fit=True)

            qr_image = qr.make_image(
                fill_color="black",
                back_color="white"
            )

            qr_filename = f"{uuid.uuid4().hex}.png"

            qr_path = os.path.join(
                "static",
                "qr_codes",
                qr_filename
            )

            qr_image.save(qr_path)

            # 8. Save the QR-code filename in SQLite
            cursor.execute("""
                UPDATE products
                SET qr_code = ?
                WHERE id = ?
            """, (qr_filename, product_id))

            conn.commit()

        except sqlite3.IntegrityError as e:
            conn.rollback()

            # Handle duplicate serial numbers safely
            if "products.serial_no" in str(e):
                app.logger.warning(
                    "Duplicate serial number attempted: %s",
                    serial_no
                )

                return (
                    "This serial number is already registered. "
                    "Please use a unique serial number.",
                    409
                )

            app.logger.exception(
                "Database integrity error during product registration."
            )

            return "Invalid or duplicate product details.", 409

        except sqlite3.Error:
            conn.rollback()

            app.logger.exception(
                "Database error while registering product."
            )

            return (
                "Unable to save the product. "
                "Please check the application logs.",
                500
            )

        except Exception:
            conn.rollback()

            app.logger.exception(
                "Unexpected error during product registration."
            )

            return (
                "An unexpected error occurred while registering "
                "the product. Please check the application logs.",
                500
            )

        finally:
            conn.close()

        # 9. Return to the manufacturer's product list
        return redirect("/manufacturer/products")

    return render_template("register.html")


@app.route("/consumer/products")
def consumer_products():

    if "consumer_id" not in session:
        return redirect("/consumer/login")

    consumer_id = session["consumer_id"]

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id,
            brand,
            product_name,
            model_name,
            serial_no,
            original_image,
            qr_code,
            status
        FROM products
        WHERE current_owner_type = 'Consumer'
          AND (current_owner_id = ? OR CAST(current_owner_id AS TEXT) = CAST(? AS TEXT))
    """, (consumer_id, str(consumer_id)))

    products = cursor.fetchall()
    conn.close()

    return render_template(
        "consumer_products.html",
        products=products
    )

@app.route("/verify/<serial_no>")
def verify_product_page(serial_no):
    serial_no = request.view_args["serial_no"].strip()

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("""
    SELECT
    brand,
    product_name,
    model_name,
    serial_no,
    original_image,
    status,
    current_owner_type,
    blockchain_tx
    FROM products
    WHERE serial_no=?
    """, (serial_no,))

    product = cursor.fetchone()

    try:
        blockchain_data = verify_product(serial_no)
    except Exception as e:
        blockchain_data = {"manufacturer": "", "seller": "", "consumer": "", "exists": False}

    cursor.execute("""
    SELECT brand, product_name, model_name, serial_no, original_image, status
    FROM products
    ORDER BY id DESC
    LIMIT 12
    """)
    sample_products = cursor.fetchall()
    conn.close()

    logged_in = "consumer_id" in session or "seller_id" in session or "manufacturer_id" in session

    return render_template(
        "verify.html",
        product=product,
        blockchain=blockchain_data,
        logged_in=logged_in,
        is_consumer=("consumer_id" in session),
        is_seller=("seller_id" in session),
        is_manufacturer=("manufacturer_id" in session),
        current_serial=serial_no,
        searched_serial=serial_no if not product else None,
        sample_products=sample_products
    )


@app.route("/verify-image", methods=["POST"])
def verify_image():

    if "consumer_id" not in session:
        return redirect("/consumer/login")

    consumer_id = session["consumer_id"]

    serial_no = request.form["serial_no"]

    consumer_image = request.files["consumer_image"]

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
    SELECT
        original_image,
        brand,
        product_name,
        model_name,
        serial_no
    FROM products
    WHERE serial_no=?
    """, (serial_no,))

    product = cursor.fetchone()

    conn.close()

    if not product:
        return "Product Not Found"

    
  

    filename = str(uuid.uuid4()) + "_" + secure_filename(consumer_image.filename)

    image_path = os.path.join(
    "static",
    "uploaded_images",
    filename
    )

    consumer_image.save(image_path)

    prediction, confidence = predict_image(image_path)
    manufacturer_image = os.path.join(
    "static",
    "product_images",
    product[0]
)

    similarity = compare_images(
        manufacturer_image,
        image_path
    )
    if similarity >= 85 and prediction == "genuine":
         final_result = "GENUINE PRODUCT"

    elif similarity < 50:
        final_result = "FAKE PRODUCT"
    else:
        final_result = "MANUAL INSPECTION REQUIRED"

    confidence_percent = round(confidence * 100, 2)
    similarity_percent = round(float(similarity), 2)
    blockchain_data = verify_product(serial_no)

    blockchain_verified = blockchain_data["exists"]

    manufacturer_name = blockchain_data["manufacturer"]
 
    seller_name = blockchain_data["seller"]

    consumer_name = blockchain_data["consumer"] 

    return render_template(
    "ai_verification.html",
    product=product,
    uploaded_image=filename,
    prediction=prediction,
    confidence=confidence,
    confidence_percent=confidence_percent,
    similarity=similarity,
    similarity_percent=similarity_percent,
    final_result=final_result,

    blockchain_verified=blockchain_verified,
    manufacturer_name=manufacturer_name,
    seller_name=seller_name,
    consumer_name=consumer_name
)

@app.route("/ledger")
@app.route("/history")
def global_ledger():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            h.from_owner_type,
            h.to_owner_type,
            h.transfer_date,
            h.blockchain_hash,
            p.serial_no,
            p.product_name,
            p.brand
        FROM ownership_history h
        LEFT JOIN products p ON h.product_id = p.id
        ORDER BY h.transfer_date DESC
    """)
    records = cursor.fetchall()
    conn.close()
    return render_template(
        "history.html",
        history=records,
        serial_no="All Registered Products",
        is_global=True
    )

@app.route("/history/<serial_no>")
def history(serial_no):

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    # Get ownership history of this product
    cursor.execute("""
        SELECT
            h.from_owner_type,
            h.to_owner_type,
            h.transfer_date,
            h.blockchain_hash,
            p.serial_no,
            p.product_name,
            p.brand
        FROM ownership_history h
        LEFT JOIN products p ON h.product_id = p.id
        WHERE p.serial_no = ?
        ORDER BY h.transfer_date ASC
    """, (serial_no,))

    history = cursor.fetchall()

    conn.close()

    return render_template(
        "history.html",
        history=history,
        serial_no=serial_no,
        is_global=False
    )


@app.route("/admin/dashboard")
def admin_dashboard():

    if "admin" not in session:
        return redirect("/admin/login")

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM products")
    total_products = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM manufacturers")
    total_manufacturers = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM sellers")
    total_sellers = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM consumers")
    total_consumers = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM ownership_history")
    total_transactions = cursor.fetchone()[0]

    conn.close()

    return render_template(
        "admin_dashboard.html",
        total_products=total_products,
        total_manufacturers=total_manufacturers,
        total_sellers=total_sellers,
        total_consumers=total_consumers,
        total_transactions=total_transactions
    )

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        if username == "admin" and password == "admin123":

            session["admin"] = True

            return redirect("/admin/dashboard")

        return "Invalid Credentials"

    return render_template("admin_login.html")

@app.route("/product/<int:product_id>")
def product_details(product_id):

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
    SELECT *
    FROM products
    WHERE id=?
    """,
    (product_id,)
    )

    product = cursor.fetchone()

    conn.close()

    if not product:
        return "Product Not Found"

    return render_template(
        "product_details.html",
        product=product
    )


@app.route("/manufacturer/history/<int:product_id>")
def manufacturer_history(product_id):

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
    SELECT
        from_owner_type,
        to_owner_type,
        transfer_date,
        blockchain_hash
    FROM ownership_history
    WHERE product_id=?
    ORDER BY transfer_date
    """,
    (product_id,)
    )

    history = cursor.fetchall()

    conn.close()

    return render_template(
        "timeline.html",
        history=history
    )


@app.route("/verify")
def verify():
    serial_no = request.args.get("serial") or request.args.get("serial_no")
    if serial_no:
        serial_no = serial_no.strip()
        return redirect(f"/verify/{serial_no}")

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("""
    SELECT brand, product_name, model_name, serial_no, original_image, status
    FROM products
    ORDER BY id DESC
    LIMIT 12
    """)
    sample_products = cursor.fetchall()
    conn.close()

    logged_in = "consumer_id" in session or "seller_id" in session or "manufacturer_id" in session

    return render_template(
        "verify.html",
        product=None,
        blockchain=None,
        logged_in=logged_in,
        is_consumer=("consumer_id" in session),
        is_seller=("seller_id" in session),
        is_manufacturer=("manufacturer_id" in session),
        current_serial="",
        searched_serial=None,
        sample_products=sample_products
    )

if __name__ == "__main__":

    create_database()
    create_manufacturer_table()
    create_seller_table()
 
    create_consumer_table()
   
    create_ownership_history_table()
    app.run(debug=True, use_reloader=False)