

import os
import secrets
import sqlite3
from functools import wraps

from flask import (
    Flask, render_template, request,
    redirect, url_for, session, abort, flash
)
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

    conn = get_db()

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
        WHERE a.asset_code LIKE ?
           OR a.asset_name LIKE ?
           OR COALESCE(a.serial_number, '') LIKE ?
        ORDER BY a.id DESC
    """, (f"%{search}%",) * 3).fetchall()

    conn.close()

    return render_template(
        "assets.html",
        assets=assets,
        search=search
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

    conn.close()

    return render_template(
        "add_asset.html",
        categories=categories,
        branches=branches,
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



if __name__ == "__main__":
    
    app.run(host="127.0.0.1", debug=True)
