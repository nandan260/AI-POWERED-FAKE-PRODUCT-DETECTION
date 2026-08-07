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

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

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

    if "manufacturer_id" not in session:
        return redirect("/manufacturer/login")

    manufacturer_id = session.get("manufacturer_id")

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

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    
    cursor.execute("""
    SELECT id
    FROM products
    WHERE id=? AND manufacturer_id=?
    """, (product_id, manufacturer_id))

    product = cursor.fetchone()

    if not product:
        conn.close()
        return "Invalid Product"

   
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

    cursor.execute(
    "SELECT serial_no FROM products WHERE id=?",
    (product_id,)
)

    serial_no = cursor.fetchone()[0]

    tx_hash = assign_seller(
    serial_no,
    seller_id
)

    print("Seller Blockchain TX:", tx_hash)

    print("Rows Updated:", cursor.rowcount)
    print("Product ID:", product_id)
    print("Seller ID:", seller_id)

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
    cursor.execute("""
    SELECT
    id,
    current_owner_type,
    current_owner_id,
    status
    FROM products
    WHERE id=?
    """, (product_id,))

    print("After Update:", cursor.fetchone())
    conn.commit()
    conn.close()

    return redirect("/manufacturer/assign")


@app.route("/manufacturer/dashboard")
def manufacturer_dashboard():

    if "company_name" not in session:
        return redirect("/manufacturer/login")

    company_name = session.get("company_name")

    return render_template("manufacturer_dashboard.html", company_name=company_name)

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

        shop_name = request.form["shop_name"]
        email = request.form["email"]
        password = request.form["password"]

        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()

        cursor.execute("""
        INSERT INTO sellers(shop_name, email, password)
        VALUES (?, ?, ?)
        """, (shop_name, email, password))

        conn.commit()
        conn.close()

        return "Seller Registered Successfully"

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

    if "seller_id" not in session:
        return redirect("/seller/login")

    seller_id = session["seller_id"]

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
    SELECT
        id,
        brand,
        product_name,
        model_name,
        serial_no,
        status
    FROM products
    WHERE
        current_owner_type=?
        AND current_owner_id=?
    """,
    (
        "Seller",
        seller_id
    ))

    products = cursor.fetchall()

    print("\n========== DEBUG ==========")
    print("Logged Seller ID :", seller_id)
    print("Products Found   :", products)
    print("===========================\n")

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

    conn = sqlite3.connect("database.db")
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
        current_owner_type=?
        AND current_owner_id=?
    """,
    (
        "Seller",
        seller_id
    ))

    products = cursor.fetchall()

    # Registered consumers
    cursor.execute("""
    SELECT
        id,
        full_name
    FROM consumers
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

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    # Check product belongs to seller
    cursor.execute("""
    SELECT id
    FROM products
    WHERE
        id=?
        AND current_owner_type=?
        AND current_owner_id=?
    """,
    (
        product_id,
        "Seller",
        seller_id
    ))

    product = cursor.fetchone()

    if not product:
        conn.close()
        return "Invalid Product"

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

    # Get serial number
    cursor.execute("""
    SELECT serial_no
    FROM products
    WHERE id=?
    """,
    (product_id,))

    serial_no = cursor.fetchone()[0]

    # Store on Blockchain
    tx_hash = assign_consumer(
        serial_no,
        str(consumer_id)
    )

    print("Consumer Blockchain TX:", tx_hash)

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
    conn.close()

    return redirect("/seller/assigned-products")

@app.route("/seller/dashboard")
def seller_dashboard():

    if "shop_name" not in session:

        return redirect("/seller/login")

    shop_name = session.get("shop_name")

    return render_template("seller_dashboard.html",shop_name=shop_name)


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

    full_name = session.get("full_name")

    return render_template(
        "consumer_dashboard.html",
        full_name=full_name
    )

@app.route("/consumer/verify")
def consumer_verify():

    if "consumer_id" not in session:
        return redirect("/consumer/login")

    return render_template("consumer_verify.html")

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
     status
    FROM products
    WHERE
    current_owner_type=?
    AND current_owner_id=?
""",
(
    "Consumer",
    consumer_id
))

    products = cursor.fetchall()

    conn.close()

    return render_template(
        "consumer_my_product.html",
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

        brand = request.form["brand"]
        product_name = request.form["product_name"]
        model_name = request.form["model_name"]
        serial_no = request.form["serial_no"]
        original_image = request.files["original_image"]


        
        manufacturer_id = session["manufacturer_id"]
        
        filename = secure_filename(original_image.filename)

        image_path = os.path.join(
        "static",
        "product_images",
        filename
    )
        original_image.save(image_path)

        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()

        
        cursor.execute("""
       INSERT INTO products
        (
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
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?,?)
        """,
        (
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
        tx_hash = register_product(
        serial_no,
        brand
    )
        print("Blockchain TX:", tx_hash)
        print("Blockchain Data:", verify_product(serial_no))


        cursor.execute("""
        UPDATE products
        SET blockchain_tx=?
        WHERE id=?
        """,
        (
        tx_hash,
        product_id
    ))

        conn.commit()
    
        qr_data = f"http://127.0.0.1:5000/verify/{serial_no}"

  
        qr = qrcode.QRCode(
            version=1,
            box_size=10,
            border=5
        )

        qr.add_data(qr_data)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")

  
        qr_filename = f"{serial_no}.png"

    
        qr_path = os.path.join("static", "qr_codes", qr_filename)
        img.save(qr_path)

     
        cursor.execute("""
        UPDATE products
        SET qr_code=?
        WHERE id=?
        """,
        (
            qr_filename,
            product_id
        ))

        conn.commit()
        conn.close()

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
    status
FROM products
WHERE
    current_owner_type=?
    AND current_owner_id=?
""",
(
    "Consumer",
    consumer_id
))

    products = cursor.fetchall()

    conn.close()

    return render_template(
        "consumer_products.html",
        products=products
    )

@app.route("/verify/<serial_no>")
def verify_product_page(serial_no):

    serial_no = request.view_args["serial_no"]

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("""
    SELECT
    brand,
    product_name,
    model_name,
    serial_no,
    original_image,
    status
    FROM products
    WHERE serial_no=?
    """, (serial_no,))

    product = cursor.fetchone()
    blockchain_data = verify_product(serial_no)

    print(blockchain_data)
    conn.close()

    if not product:
        return "Product Not Found"

    logged_in = "consumer_id" in session

    return render_template(
    "verify_product.html",
    product=product,
    blockchain=blockchain_data,
     logged_in=("consumer_id" in session)
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
    WHERE
        serial_no=?
        AND current_owner_type=?
        AND current_owner_id=?
    """,
    (
     serial_no,
    "Consumer",
    consumer_id
))

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
@app.route("/history/<serial_no>")
def history(serial_no):

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    # Get ownership history of this product
    cursor.execute("""
        SELECT
            from_owner_type,
            to_owner_type,
            transfer_date,
            blockchain_hash
        FROM ownership_history
        WHERE product_id = (
            SELECT id
            FROM products
            WHERE serial_no = ?
        )
        ORDER BY transfer_date ASC
    """, (serial_no,))

    history = cursor.fetchall()

    conn.close()

    return render_template(
        "history.html",
        history=history,
        serial_no=serial_no
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
    return render_template("verify.html")

if __name__ == "__main__":

    create_database()
    create_manufacturer_table()
    create_seller_table()
 
    create_consumer_table()
   
    create_ownership_history_table()
    app.run(debug=True, use_reloader=False)