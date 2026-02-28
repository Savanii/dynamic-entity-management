from flask import Flask, render_template, request, redirect
from db import get_db_connection
from datetime import datetime

app = Flask(__name__)

# =====================================================
# HELPER: VALIDATION BASED ON DATA TYPE
# =====================================================
def validate_value(value, data_type):
    try:
        if data_type == "integer":
            int(value)
        elif data_type == "float":
            float(value)
        elif data_type == "boolean":
            if value not in ["true", "false"]:
                return False
        elif data_type == "date":
            datetime.strptime(value, "%Y-%m-%d")
        return True
    except:
        return False


# =====================================================
# HOME
# =====================================================
@app.route("/")
def home():
    return redirect("/entity-types")


# =====================================================
# ENTITY TYPES
# =====================================================
@app.route("/entity-types", methods=["GET", "POST"])
def entity_types():

    conn = get_db_connection()
    cur = conn.cursor()
    error = None

    if request.method == "POST":
        name = request.form.get("name", "").strip()

        if name:
            try:
                cur.execute(
                    "INSERT INTO entity_types (name) VALUES (%s) RETURNING id)",
                    (name,)
                )
                new_id = cur.fetchone()[0]
                conn.commit()
                return redirect(f"/attributes/{new_id}")
            except Exception:
                conn.rollback()
                error = "Entity type already exists."

    cur.execute("SELECT * FROM entity_types ORDER BY id")
    types = cur.fetchall()

    cur.close()
    conn.close()

    return render_template("entity_types.html", types=types, error=error)


@app.route("/delete-entity-type/<int:id>")
def delete_entity_type(id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM entity_types WHERE id = %s", (id,))
    conn.commit()
    cur.close()
    conn.close()
    return redirect("/entity-types")


# =====================================================
# ATTRIBUTES
# =====================================================
@app.route("/attributes/<int:entity_type_id>", methods=["GET", "POST"])
def manage_attributes(entity_type_id):

    conn = get_db_connection()
    cur = conn.cursor()

    if request.method == "POST":
        name = request.form.get("name").strip()
        data_type = request.form.get("data_type")

        cur.execute("""
            INSERT INTO attributes (entity_type_id, name, data_type)
            VALUES (%s, %s, %s)
        """, (entity_type_id, name, data_type))
        conn.commit()
        return redirect(f"/attributes/{entity_type_id}")

    cur.execute("SELECT name FROM entity_types WHERE id = %s", (entity_type_id,))
    entity = cur.fetchone()

    cur.execute("""
        SELECT id, name, data_type
        FROM attributes
        WHERE entity_type_id = %s
        ORDER BY id
    """, (entity_type_id,))
    attributes = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        "attributes.html",
        entity=entity,
        attributes=attributes,
        entity_type_id=entity_type_id
    )


@app.route("/delete-attribute/<int:id>/<int:entity_type_id>")
def delete_attribute(id, entity_type_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM attributes WHERE id = %s", (id,))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(f"/attributes/{entity_type_id}")


# =====================================================
# CREATE RECORD (WITH VALIDATION)
# =====================================================
@app.route("/records/<int:entity_type_id>", methods=["GET", "POST"])
def create_record(entity_type_id):

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT name FROM entity_types WHERE id = %s", (entity_type_id,))
    entity = cur.fetchone()

    cur.execute("""
        SELECT id, name, data_type
        FROM attributes
        WHERE entity_type_id = %s
        ORDER BY id
    """, (entity_type_id,))
    attributes = cur.fetchall()

    error = None

    if request.method == "POST":

        # VALIDATION
        for attr_id, attr_name, data_type in attributes:
            value = request.form.get(str(attr_id))
            if not validate_value(value, data_type):
                error = f"Invalid value for {attr_name}"
                break

        if not error:
            cur.execute(
                "INSERT INTO entities (entity_type_id) VALUES (%s) RETURNING id",
                (entity_type_id,)
            )
            entity_id = cur.fetchone()[0]

            for attr_id, _, _ in attributes:
                value = request.form.get(str(attr_id))
                cur.execute("""
                    INSERT INTO entity_values (entity_id, attribute_id, value)
                    VALUES (%s, %s, %s)
                """, (entity_id, attr_id, value))

            conn.commit()
            return redirect(f"/records-list/{entity_type_id}")

    cur.close()
    conn.close()

    return render_template(
        "create_record.html",
        entity=entity,
        attributes=attributes,
        entity_type_id=entity_type_id,
        error=error
    )


# =====================================================
# LIST RECORDS + FILTERING (FIXED)
# =====================================================
@app.route("/records-list/<int:entity_type_id>", methods=["GET", "POST"])
def list_records(entity_type_id):

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT name FROM entity_types WHERE id = %s", (entity_type_id,))
    entity = cur.fetchone()

    cur.execute("""
        SELECT id, name
        FROM attributes
        WHERE entity_type_id = %s
        ORDER BY id
    """, (entity_type_id,))
    attributes = cur.fetchall()

    filter_clause = ""
    params = [entity_type_id]

    if request.method == "POST":
        attribute_id = request.form.get("attribute_id")
        operator = request.form.get("operator")
        value = request.form.get("value")

        if attribute_id and value:
            if operator == "LIKE":
                value = f"%{value}%"

            filter_clause = f"""
                AND e.id IN (
                    SELECT entity_id
                    FROM entity_values
                    WHERE attribute_id = %s
                    AND value {operator} %s
                )
            """
            params.extend([attribute_id, value])

    query = f"""
        SELECT e.id, a.name, ev.value
        FROM entities e
        JOIN entity_values ev ON e.id = ev.entity_id
        JOIN attributes a ON ev.attribute_id = a.id
        WHERE e.entity_type_id = %s
        {filter_clause}
        ORDER BY e.id
    """

    cur.execute(query, params)
    rows = cur.fetchall()

    records = {}
    for entity_id, attr_name, value in rows:
        records.setdefault(entity_id, {})
        records[entity_id][attr_name] = value

    cur.close()
    conn.close()

    return render_template(
        "records_list.html",
        entity=entity,
        attributes=attributes,
        records=records,
        entity_type_id=entity_type_id
    )


# =====================================================
# RUN
# =====================================================
if __name__ == "__main__":
    app.run(debug=True)