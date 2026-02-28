from flask import Flask, render_template, request, redirect
from db import get_db_connection
from datetime import datetime

app = Flask(__name__)


# =====================================================
# VALIDATION FUNCTION
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
# CALCULATION FUNCTION
# =====================================================
def calculate_formula(formula, values_dict):
    try:
        expression = formula
        for key, val in values_dict.items():
            expression = expression.replace(key, str(val))
        return eval(expression)
    except:
        return None


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
        name = request.form.get("name").strip()

        try:
            cur.execute(
                "INSERT INTO entity_types (name) VALUES (%s)",
                (name,)
            )
            conn.commit()
        except:
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

        name = request.form.get("name")
        data_type = request.form.get("data_type")
        is_calculated = True if request.form.get("is_calculated") else False
        formula = request.form.get("formula") if is_calculated else None

        cur.execute("""
            INSERT INTO attributes
            (entity_type_id, name, data_type, is_calculated, formula)
            VALUES (%s, %s, %s, %s, %s)
        """, (entity_type_id, name, data_type, is_calculated, formula))

        conn.commit()

    cur.execute("SELECT name FROM entity_types WHERE id = %s", (entity_type_id,))
    entity = cur.fetchone()

    cur.execute("""
        SELECT id, name, data_type, is_calculated, formula
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
# CREATE RECORD
# =====================================================
@app.route("/records/<int:entity_type_id>", methods=["GET", "POST"])
def create_record(entity_type_id):

    conn = get_db_connection()
    cur = conn.cursor()
    error = None

    # Fetch entity name
    cur.execute("SELECT name FROM entity_types WHERE id = %s", (entity_type_id,))
    entity = cur.fetchone()

    # Fetch attributes
    cur.execute("""
        SELECT id, name, data_type, is_calculated, formula
        FROM attributes
        WHERE entity_type_id = %s
        ORDER BY id
    """, (entity_type_id,))
    attributes = cur.fetchall()

    if request.method == "POST":

        values_dict = {}

        # Validate normal fields
        for attr_id, attr_name, data_type, is_calc, formula in attributes:
            if not is_calc:
                value = request.form.get(str(attr_id))

                if not validate_value(value, data_type):
                    error = f"Invalid value for {attr_name}"
                    break

                values_dict[attr_name] = value

        if not error:

            cur.execute(
                "INSERT INTO entities (entity_type_id) VALUES (%s) RETURNING id",
                (entity_type_id,)
            )
            entity_id = cur.fetchone()[0]

            # Calculate calculated fields
            for attr_id, attr_name, data_type, is_calc, formula in attributes:
                if is_calc and formula:
                    result = calculate_formula(formula, values_dict)
                    values_dict[attr_name] = result

            # Insert values
            for attr_id, attr_name, _, _, _ in attributes:
                value = values_dict.get(attr_name)

                cur.execute("""
                    INSERT INTO entity_values
                    (entity_id, attribute_id, value)
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

#EDIT

@app.route("/edit-record/<int:entity_id>/<int:entity_type_id>", methods=["GET", "POST"])
def edit_record(entity_id, entity_type_id):

    conn = get_db_connection()
    cur = conn.cursor()
    error = None

    # Fetch entity name
    cur.execute("SELECT name FROM entity_types WHERE id = %s", (entity_type_id,))
    entity = cur.fetchone()

    # Fetch attributes
    cur.execute("""
        SELECT id, name, data_type, is_calculated, formula
        FROM attributes
        WHERE entity_type_id = %s
        ORDER BY id
    """, (entity_type_id,))
    attributes = cur.fetchall()

    if request.method == "POST":

        values_dict = {}

        # Validate normal fields
        for attr_id, attr_name, data_type, is_calc, formula in attributes:
            if not is_calc:
                value = request.form.get(str(attr_id))

                if not validate_value(value, data_type):
                    error = f"Invalid value for {attr_name}"
                    break

                values_dict[attr_name] = value

        if not error:

            # Recalculate calculated fields
            for attr_id, attr_name, data_type, is_calc, formula in attributes:
                if is_calc and formula:
                    result = calculate_formula(formula, values_dict)
                    values_dict[attr_name] = result

            # Update values
            for attr_id, attr_name, _, _, _ in attributes:
                value = values_dict.get(attr_name)

                cur.execute("""
                    UPDATE entity_values
                    SET value = %s
                    WHERE entity_id = %s AND attribute_id = %s
                """, (value, entity_id, attr_id))

            conn.commit()
            return redirect(f"/records-list/{entity_type_id}")

    # Load existing values
    cur.execute("""
        SELECT attribute_id, value
        FROM entity_values
        WHERE entity_id = %s
    """, (entity_id,))
    existing = cur.fetchall()

    values = {row[0]: row[1] for row in existing}

    cur.close()
    conn.close()

    return render_template(
        "edit_record.html",
        entity=entity,
        attributes=attributes,
        values=values,
        entity_id=entity_id,
        entity_type_id=entity_type_id,
        error=error
    )


# =====================================================
# LIST RECORDS (MANUAL FILTER)
# =====================================================
@app.route("/records-list/<int:entity_type_id>", methods=["GET", "POST"])
def list_records(entity_type_id):

    conn = get_db_connection()
    cur = conn.cursor()

    # Get entity name
    cur.execute("SELECT name FROM entity_types WHERE id = %s", (entity_type_id,))
    entity = cur.fetchone()

    # Get attributes
    cur.execute("""
        SELECT id, name, data_type
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

        if attribute_id and operator and value:

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
        if entity_id not in records:
            records[entity_id] = {}
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
# DELETE RECORD
# =====================================================
@app.route("/delete-record/<int:entity_id>/<int:entity_type_id>")
def delete_record(entity_id, entity_type_id):

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("DELETE FROM entities WHERE id = %s", (entity_id,))
    conn.commit()

    cur.close()
    conn.close()

    return redirect(f"/records-list/{entity_type_id}")


if __name__ == "__main__":
    app.run(debug=True)