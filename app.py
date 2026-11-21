

import csv
import io
import os
import secrets
import sqlite3

# Lesson 5B - Step 3H: Excel Export

from openpyxl import Workbook

from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from functools import wraps

from flask import (
    Flask, render_template, request,
    redirect, url_for, session, abort, flash,
    Response, send_file)

from werkzeug.security import check_password_hash

from database import DB_PATH

app = Flask(__name__)

# Development secret stored outside source code
secret_file = DB_PATH.parent / ".flask_secret"

if not secret_file.exists():
    secret_file.write_text(secrets.token_hex(32))
    secret_file.chmod(0o600)

app.secret_key = secret_file.read_text().strip()

app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    PERMANENT_SESSION_LIFETIME=1800
)


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))

        conn = get_db()
        user = conn.execute(
            "SELECT id FROM users "
            "WHERE id = ? AND is_active = 1",
            (session["user_id"],)
        ).fetchone()
        conn.close()

        if user is None:
            session.clear()
            return redirect(url_for("login"))

        return view(*args, **kwargs)
    return wrapped


@app.route("/")
@login_required
def home():
    return render_template("index.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None

    if request.method == "POST":
        username = request.form.get(
            "username", ""
        ).strip()
        password = request.form.get(
            "password", ""
        )

        if request.form.get("csrf_token") != session.get(
            "csrf_token"
        ):
            abort(400)

        conn = get_db()
        user = conn.execute(
            "SELECT * FROM users WHERE username = ? "
            "AND is_active = 1",
            (username,)
        ).fetchone()
        conn.close()

        # if user and check_password_hash(
        #     user["password_hash"], password
        # ):
        #     session.clear()
        #     session["user_id"] = user["id"]
        #     session["username"] = user["username"]
        #     session["role"] = user["role"]
        #     session.permanent = True

        #     return redirect(url_for("home"))


        if user and check_password_hash(
            user["password_hash"], password
        ):
            session.clear()

    # Store authenticated user information
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["role"] = user["role"]

    # Generate a new CSRF token after login
            session["csrf_token"] = secrets.token_hex(32)

            session.permanent = True

            return redirect(url_for("home"))
            error = "Invalid username or password."
 
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(32)

    return render_template(
        "login.html",
        error=error,
        csrf_token=session["csrf_token"]
    )


@app.route("/logout", methods=["POST"])
@login_required
def logout():
    if request.form.get("csrf_token") != session.get(
        "csrf_token"
    ):
        abort(400)

    session.clear()
    return redirect(url_for("login"))

# IT Asset Register

@app.route("/assets")
@login_required

def asset_list():
    search = request.args.get("search", "").strip()
    status_filter = request.args.get("status", "").strip()
    branch_filter = request.args.get("branch", "").strip()

    conn = get_db()

    # Load statuses from Asset Status Master
    statuses = conn.execute("""
        SELECT status_name
        FROM asset_statuses
        WHERE is_active = 1
        ORDER BY status_name
    """).fetchall()

    # Existing asset search plus status filtering
    assets = conn.execute("""
        SELECT
            a.id,
            a.asset_code,
            a.asset_name,
            a.serial_number,
            a.brand,
            a.model,
            a.status,
            b.branch_name,
            c.category_name
        FROM assets a
        JOIN branches b ON a.branch_id = b.id
        JOIN asset_categories c ON a.category_id = c.id
        WHERE (
            a.asset_code LIKE ?
            OR a.asset_name LIKE ?
            OR COALESCE(a.serial_number, '') LIKE ?
        )
        AND (? = '' OR a.status = ?)
        AND (? = '' OR a.branch_id = ?)
        ORDER BY a.id DESC
    """, (
        f"%{search}%",
        f"%{search}%",
        f"%{search}%",
        status_filter,
        status_filter,
        branch_filter,
        branch_filter        
    )).fetchall()

    # Lesson 5B - Step 3F-4: Load branches for filter
    branches = conn.execute("""
        SELECT id, branch_name
        FROM branches
        ORDER BY branch_name
        """).fetchall()

    conn.close()

    return render_template(
        "assets.html",
        assets=assets,
        search=search,
        statuses=statuses,
        status_filter=status_filter,
        branches=branches,
        branch_filter=branch_filter
    )

# ==========================================
# LESSON 5B - STEP 3G: EXPORT ASSETS TO CSV
# ==========================================

@app.route("/assets/export")
@login_required
def export_assets_csv():
    search = request.args.get("search", "").strip()
    status_filter = request.args.get("status", "").strip()
    branch_filter = request.args.get("branch", "").strip()

    conn = get_db()

    assets = conn.execute("""
        SELECT
            a.asset_code,
            a.asset_name,
            c.category_name,
            a.brand,
            a.model,
            a.serial_number,
            b.branch_name,
            a.status
        FROM assets a
        JOIN branches b ON a.branch_id = b.id
        JOIN asset_categories c ON a.category_id = c.id
        WHERE (
            a.asset_code LIKE ?
            OR a.asset_name LIKE ?
            OR COALESCE(a.serial_number, '') LIKE ?
        )
        AND (? = '' OR a.status = ?)
        AND (? = '' OR a.branch_id = ?)
        ORDER BY a.id DESC
    """, (
        f"%{search}%",
        f"%{search}%",
        f"%{search}%",
        status_filter,
        status_filter,
        branch_filter,
        branch_filter
    )).fetchall()

    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "Asset Code", "Asset Name", "Category",
        "Brand", "Model", "Serial Number",
        "Branch", "Status"
    ])

    for asset in assets:
        writer.writerow(list(asset))

    return Response(
        "\ufeff" + output.getvalue(),
        mimetype="text/csv; charset=utf-8",
        headers={
            "Content-Disposition":
                "attachment; filename=IT_Asset_Register.csv"
        }
    )

# ============================================
# LESSON 5B - STEP 3H: EXPORT ASSETS TO EXCEL
# ============================================

@app.route("/assets/export-excel")
@login_required
def export_assets_excel():
    search = request.args.get("search", "").strip()
    status_filter = request.args.get("status", "").strip()
    branch_filter = request.args.get("branch", "").strip()

    # Step 3H-4: Retrieve filtered IT assets
    conn = get_db()

    assets = conn.execute("""
        SELECT
            a.asset_code,
            a.asset_name,
            c.category_name,
            a.brand,
            a.model,
            a.serial_number,
            b.branch_name,
            a.status
        FROM assets a
        JOIN branches b ON a.branch_id = b.id
        JOIN asset_categories c ON a.category_id = c.id
        WHERE (
            a.asset_code LIKE ?
            OR a.asset_name LIKE ?
            OR COALESCE(a.serial_number, '') LIKE ?
        )
        AND (? = '' OR a.status = ?)
        AND (? = '' OR a.branch_id = ?)
        ORDER BY a.id DESC
    """, (
        f"%{search}%",
        f"%{search}%",
        f"%{search}%",
        status_filter,
        status_filter,
        branch_filter,
        branch_filter
    )).fetchall()

    conn.close()


    # Lesson 5B - Step 3H-5: Create Excel Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "IT Asset Register"

    # Create column headings
    headers = [
        "Asset Code",
        "Asset Name",
        "Category",
        "Brand",
        "Model",
        "Serial Number",
        "Branch",
        "Status"
    ]

    ws.append(headers)

    # Lesson 5B - Step 3H-6: Format Excel Headings

    header_fill = PatternFill(
        start_color="194D80",
        end_color="194D80",
        fill_type="solid"
    )

    header_font = Font(
        bold=True,
        color="FFFFFF",
        size=11
    )

    for cell in ws[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(
            horizontal="center",
            vertical="center"
        )

    # Set heading row height
    ws.row_dimensions[1].height = 25

# Lesson 5B - Step 3H-7: Excel Column Widths

    column_widths = {
        "A": 16,  # Asset Code
        "B": 30,  # Asset Name
        "C": 22,  # Category
        "D": 22,  # Brand
        "E": 22,  # Model
        "F": 24,  # Serial Number
        "G": 22,  # Branch
        "H": 18   # Status
    }

    for column, width in column_widths.items():
        ws.column_dimensions[column].width = width

    # Keep the heading row visible while scrolling
    ws.freeze_panes = "A2"


    # Lesson 5B - Step 3I-3A: Excel Print Settings
    ws.page_setup.orientation = "landscape"
    ws.page_setup.paperSize = ws.PAPERSIZE_A4

    # Lesson 5B - Step 3I-3B: Fit Columns to Page Width
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0

    # Lesson 5B - Step 3I-3C
    # Repeat column headings on every printed page
    ws.print_title_rows = "1:1"


    # Add asset records from SQLite
    for asset in assets:
        ws.append(list(asset))

    
    # Lesson 5B - Step 3I-1: Enable Excel AutoFilter
    ws.auto_filter.ref = ws.dimensions


# Lesson 5B - Step 3I-2B: Row Colors and Borders

    light_blue_fill = PatternFill(
        start_color="EAF3F8",
        end_color="EAF3F8",
        fill_type="solid"
    )

    thin_border = Border(
        left=Side(style="thin", color="D9E2F3"),
        right=Side(style="thin", color="D9E2F3"),
        top=Side(style="thin", color="D9E2F3"),
        bottom=Side(style="thin", color="D9E2F3")
    )

    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.border = thin_border

            if cell.row % 2 == 0:
                cell.fill = light_blue_fill
  
   
# Lesson 5B - Step 3H-8: Download Excel Workbook

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    return send_file(
        output,
        as_attachment=True,
        download_name="IT_Asset_Register.xlsx",
        mimetype=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        )
    )


@app.route("/assets/add", methods=["GET", "POST"])
@login_required
def add_asset():
    conn = get_db()
    conn.execute("PRAGMA foreign_keys = ON")

    if request.method == "POST":
        if request.form.get("csrf_token") != session.get(
            "csrf_token"
        ):
            conn.close()
            abort(400)

        asset_code = request.form.get(
            "asset_code", ""
        ).strip()

        asset_name = request.form.get(
            "asset_name", ""
        ).strip()

        serial_number = request.form.get(
            "serial_number", ""
        ).strip() or None

        brand = request.form.get("brand", "").strip()
        model = request.form.get("model", "").strip()

        try:
            category_id = int(request.form["category_id"])
            branch_id = int(request.form["branch_id"])
        except (ValueError, KeyError):
            conn.close()
            abort(400)

        status = request.form.get("status", "Active")

        if not asset_code or not asset_name:
            conn.close()
            abort(400)

        if status not in (
            "Active", "Repair", "Spare", "Obsolete"
        ):
            conn.close()
            abort(400)

        try:
            conn.execute("""
                INSERT INTO assets (
                    asset_code, asset_name,
                    serial_number, brand, model,
                    category_id, branch_id, status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                asset_code, asset_name,
                serial_number, brand, model,
                category_id, branch_id, status
            ))

            conn.commit()
            flash("Asset added successfully!", "success")

            return redirect(url_for("asset_list"))

        except sqlite3.IntegrityError:
            conn.rollback()
            flash(
                "Asset code or serial number already exists, "
                "or the selected branch/category is invalid.",
                "error"
            )

    categories = conn.execute(
        "SELECT * FROM asset_categories ORDER BY category_name"
    ).fetchall()

    branches = conn.execute(
        "SELECT * FROM branches ORDER BY branch_name"
    ).fetchall()

# Lesson 5B - Step 3D: Load enabled asset statuses
    statuses = conn.execute(
        """
        SELECT id, status_name
        FROM asset_statuses
        WHERE is_active = 1
    ORDER BY status_name
    """
).fetchall()
# Lesson 5B - Step 3F-4: Load branches for filter
        
    conn.close()

    return render_template(
        "add_asset.html",
        categories=categories,
        branches=branches,
        statuses=statuses,
        csrf_token=session.get("csrf_token")
    )

# ==========================================
# LESSON 5A - CATEGORY MASTER MANAGEMENT
# ==========================================

@app.route("/categories")
@login_required
def category_list():

    conn = get_db()

    categories = conn.execute("""
        SELECT id, category_name
        FROM asset_categories
        ORDER BY category_name
    """).fetchall()

    conn.close()

    return render_template(
        "categories.html",
        categories=categories
    )


# ADD NEW CATEGORY
@app.route("/categories/add", methods=["POST"])
@login_required
def add_category():

    # Only Admin can add categories
    if session.get("role") != "Admin":
        abort(403)

    # Verify CSRF token
    if not secrets.compare_digest(
        request.form.get("csrf_token", ""),
        session.get("csrf_token", "")
    ):
        abort(400)

    category_name = request.form.get(
        "category_name", ""
    ).strip()

    if not category_name:
        flash("Category name is required.", "error")
        return redirect(url_for("category_list"))

    if len(category_name) > 100:
        flash("Category name is too long.", "error")
        return redirect(url_for("category_list"))

    conn = get_db()

    try:
        # Check duplicate names ignoring case
        existing = conn.execute("""
            SELECT id
            FROM asset_categories
            WHERE LOWER(category_name) = LOWER(?)
        """, (category_name,)).fetchone()

        if existing:
            flash("Category already exists.", "error")
        else:
            conn.execute("""
                INSERT INTO asset_categories (category_name)
                VALUES (?)
            """, (category_name,))

            conn.commit()
            flash("Category added successfully!", "success")

    except sqlite3.IntegrityError:
        conn.rollback()
        flash("Unable to add category.", "error")

    finally:
        conn.close()

    return redirect(url_for("category_list"))


# EDIT CATEGORY
@app.route("/categories/edit/<int:category_id>",
           methods=["GET", "POST"])
@login_required
def edit_category(category_id):

    if session.get("role") != "Admin":
        abort(403)

    conn = get_db()

    category = conn.execute("""
        SELECT id, category_name
        FROM asset_categories
        WHERE id = ?
    """, (category_id,)).fetchone()

    if category is None:
        conn.close()
        abort(404)

    if request.method == "POST":

        if not secrets.compare_digest(
            request.form.get("csrf_token", ""),
            session.get("csrf_token", "")
        ):
            conn.close()
            abort(400)

        new_name = request.form.get(
            "category_name", ""
        ).strip()

        if not new_name or len(new_name) > 100:
            flash("Enter a valid category name.", "error")

        else:
            existing = conn.execute("""
                SELECT id
                FROM asset_categories
                WHERE LOWER(category_name) = LOWER(?)
                  AND id != ?
            """, (new_name, category_id)).fetchone()

            if existing:
                flash("Category already exists.", "error")
            else:
                try:
                    conn.execute("""
                        UPDATE asset_categories
                        SET category_name = ?
                        WHERE id = ?
                    """, (new_name, category_id))

                    conn.commit()
                    conn.close()

                    flash(
                        "Category updated successfully!",
                        "success"
                    )
                    return redirect(url_for("category_list"))

                except sqlite3.IntegrityError:
                    conn.rollback()
                    flash("Unable to update category.", "error")

    conn.close()

    return render_template(
        "edit_category.html",
        category=category
    )

# =====================================
# LESSON 5B - STEP 1: VIEW ASSET DETAILS
# =====================================

@app.route("/assets/view/<int:asset_id>")
@login_required
def view_asset(asset_id):

    conn = get_db()

    asset = conn.execute("""
        SELECT
            a.*,
            c.category_name,
            b.branch_name
        FROM assets a
        LEFT JOIN asset_categories c
            ON a.category_id = c.id
        LEFT JOIN branches b
            ON a.branch_id = b.id
        WHERE a.id = ?
    """, (asset_id,)).fetchone()

    conn.close()

    if asset is None:
        abort(404)

    return render_template(
        "view_asset.html",
        asset=asset
    )


# ==========================================
# LESSON 5B - STEP 2: EDIT AND UPDATE ASSET
# ==========================================

@app.route("/assets/edit/<int:asset_id>",
           methods=["GET", "POST"])
@login_required
def edit_asset(asset_id):

    # Only administrators can edit assets
    if session.get("role") != "Admin":
        abort(403)

    conn = get_db()

    asset = conn.execute(
        "SELECT * FROM assets WHERE id = ?",
        (asset_id,)
    ).fetchone()

    if asset is None:
        conn.close()
        abort(404)

    categories = conn.execute(
        "SELECT * FROM asset_categories ORDER BY category_name"
    ).fetchall()

    branches = conn.execute(
        "SELECT * FROM branches ORDER BY branch_name"
    ).fetchall()

    if request.method == "POST":
            
        if request.form.get("csrf_token") != session.get("csrf_token"):
            abort(400, description="Invalid CSRF token")

        asset_name = request.form.get(
            "asset_name", ""
        ).strip()

        serial_number = request.form.get(
            "serial_number", ""
        ).strip()

        brand = request.form.get(
            "brand", ""
        ).strip()

        model = request.form.get(
            "model", ""
        ).strip()

        category_id = request.form.get(
            "category_id", type=int
        )

        branch_id = request.form.get(
            "branch_id", type=int
        )

        status = request.form.get(
            "status", ""
        ).strip()
        
        valid_statuses = {
            row["status_name"]
            for row in conn.execute("""
                SELECT status_name
                FROM asset_statuses
                WHERE is_active = 1
            """).fetchall()
        }
        
        valid_category_ids = {
            row["id"] for row in categories
        }

        valid_branch_ids = {
            row["id"] for row in branches
        }

        if (
            not asset_name
            or category_id not in valid_category_ids
            or branch_id not in valid_branch_ids
            or status not in valid_statuses
        ):
            conn.close()
            abort(400, description="Invalid asset details.")

        conn.execute("""
            UPDATE assets
            SET
                asset_name = ?,
                serial_number = ?,
                brand = ?,
                model = ?,
                category_id = ?,
                branch_id = ?,
                status = ?
            WHERE id = ?
        """, (
            asset_name,
            serial_number,
            brand,
            model,
            category_id,
            branch_id,
            status,
            asset_id
        ))

        conn.commit()
        conn.close()

        return redirect(
            url_for("view_asset", asset_id=asset_id)
        )
    
    # # Fetch enabled statuses for Edit Asset dropdown
    # statuses = conn.execute("""
    #         SELECT status_name
    #         FROM asset_statuses
    #         WHERE is_active = 1
    #         ORDER BY status_name
    #     """).fetchall()

    # conn.close()

    # return render_template(
    #     "edit_asset.html",
    #     asset=asset,
    #     categories=categories,
    #     branches=branches,
    #     statuses=statuses
    # )


    # Fetch enabled statuses for Edit Asset dropdown
    statuses = conn.execute("""
        SELECT status_name
        FROM asset_statuses
        WHERE is_active = 1
        ORDER BY status_name
    """).fetchall()

    conn.close()

    return render_template(
        "edit_asset.html",
        asset=asset,
        categories=categories,
        branches=branches,
        statuses=statuses
    )


    


# ==========================================
# LESSON 5B - STEP 3C
# ASSET STATUS MASTER MANAGEMENT
# ==========================================

@app.route("/statuses", methods=["GET", "POST"])
@login_required
def status_list():

    # Only administrators can manage statuses
    if session.get("role") != "Admin":
        abort(403)

    conn = get_db()

    if request.method == "POST":

        # Verify CSRF token
        if (
            not session.get("csrf_token")
            or request.form.get("csrf_token")
            != session.get("csrf_token")
        ):
            conn.close()
            abort(400, description="Invalid CSRF token")

        status_name = request.form.get(
            "status_name", ""
        ).strip()

        if not status_name:
            conn.close()
            return redirect(url_for("status_list"))

        if len(status_name) > 50:
            conn.close()
            abort(400, description="Status name too long")

        try:
            conn.execute("""
                INSERT INTO asset_statuses
                (status_name, is_active)
                VALUES (?, 1)
            """, (status_name,))

            conn.commit()

        except sqlite3.IntegrityError:
            # Duplicate status name
            conn.rollback()

        finally:
            conn.close()

        return redirect(url_for("status_list"))

    statuses = conn.execute("""
        SELECT id, status_name, is_active
        FROM asset_statuses
        ORDER BY id
    """).fetchall()

    conn.close()

    return render_template(
        "statuses.html",
        statuses=statuses
    )



if __name__ == "__main__":
    
    app.run(host="127.0.0.1", debug=True)
