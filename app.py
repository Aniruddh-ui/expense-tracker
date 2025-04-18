import os
import sqlite3
import requests
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# Function to establish database connection
def create_db_connection():
    try:
        conn = sqlite3.connect("expense_tracker.db")
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as err:
        print(f"Error connecting to database: {err}")
        return None

# Function to generate AI suggestion
def generate_ai_suggestion(user_id):
    db = create_db_connection()
    if not db:
        return "Could not connect to DB for AI suggestion."

    cursor = db.cursor()
    try:
        cursor.execute("SELECT category, amount, description FROM expenses WHERE user_id = ?", (user_id,))
        rows = cursor.fetchall()

        if not rows:
            return "No expenses to analyze."

        expense_summary = "\n".join(
            [f"{row[0]} - ₹{row[1]} for {row[2]}" for row in rows]
        )

        prompt = f"""Here are the weekly expenses of a user:
{expense_summary}
Give a short financial suggestion to the user in bullet points:
- Is spending okay?
- Should they save more?
- Suggest smart ways to invest or reduce spending."""

        headers = {
            "Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY')}",
            "Content-Type": "application/json"
        }

        data = {
            "model": "meta-llama/llama-3-8b-instruct",
            "messages": [
                {"role": "user", "content": prompt}
            ]
        }

        response = requests.post("https://openrouter.ai/api/v1/chat/completions", json=data, headers=headers)
        result = response.json()
        suggestion = result['choices'][0]['message']['content']

        return "\n".join([line.strip() for line in suggestion.strip().split("\n") if line.strip()])

    except Exception as e:
        print(f"AI generation error: {e}")
        return "AI suggestion not available."

    finally:
        cursor.close()
        db.close()

# Serve index.html
@app.route("/")
def home():
    return render_template("index.html")

# API to add expenses
@app.route('/add_expense', methods=['POST'])
def add_expense():
    data = request.json
    db = create_db_connection()
    if not db:
        return jsonify({"error": "Database connection failed"}), 500

    cursor = db.cursor()
    try:
        query = """
            INSERT INTO expenses (user_id, category, amount, description, expense_date)
            VALUES (?, ?, ?, ?, ?)
        """
        values = (data['user_id'], data['category'], data['amount'], data['description'], data['expense_date'])
        cursor.execute(query, values)
        db.commit()
        return jsonify({"message": "Expense added successfully!"})

    except sqlite3.Error as err:
        print(f"Error adding expense: {err}")
        return jsonify({"error": "Failed to add expense"}), 500

    finally:
        cursor.close()
        db.close()

# API to get expenses and total
@app.route('/get_expenses/<int:user_id>', methods=['GET'])
def get_expenses(user_id):
    db = create_db_connection()
    if not db:
        return jsonify({"error": "Database connection failed"}), 500

    cursor = db.cursor()
    try:
        cursor.execute("SELECT id, category, amount, description, expense_date FROM expenses WHERE user_id = ?", (user_id,))
        expenses = [dict(row) for row in cursor.fetchall()]

        cursor.execute("SELECT SUM(amount) AS total_expense FROM expenses WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        total_expense = row[0] if row[0] is not None else 0

        return jsonify({
            "expenses": expenses,
            "total_expense": total_expense
        })

    except sqlite3.Error as err:
        print(f"Error fetching expenses: {err}")
        return jsonify({"error": "Failed to fetch expenses"}), 500

    finally:
        cursor.close()
        db.close()

# New: Delete an expense
@app.route('/delete_expense/<int:expense_id>', methods=['DELETE'])
def delete_expense(expense_id):
    db = create_db_connection()
    if not db:
        return jsonify({"error": "Database connection failed"}), 500

    cursor = db.cursor()
    try:
        cursor.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
        db.commit()
        return jsonify({"message": "Expense deleted successfully."})

    except sqlite3.Error as err:
        print(f"Error deleting expense: {err}")
        return jsonify({"error": "Failed to delete expense."}), 500

    finally:
        cursor.close()
        db.close()

# New: Endpoint to get chart data by category
@app.route('/chart_data/<int:user_id>', methods=['GET'])
def chart_data(user_id):
    db = create_db_connection()
    if not db:
        return jsonify({"error": "Database connection failed"}), 500

    cursor = db.cursor()
    try:
        cursor.execute("""
            SELECT category, SUM(amount) as total
            FROM expenses
            WHERE user_id = ?
            GROUP BY category
        """, (user_id,))

        chart_data = cursor.fetchall()
        result = {row[0]: row[1] for row in chart_data}

        return jsonify(result)

    except sqlite3.Error as err:
        print(f"Error fetching chart data: {err}")
        return jsonify({"error": "Failed to fetch chart data."}), 500

    finally:
        cursor.close()
        db.close()

# AI suggestion only
@app.route('/ai_suggestion/<int:user_id>', methods=['GET'])
def ai_suggestion(user_id):
    suggestion = generate_ai_suggestion(user_id)
    return jsonify({"ai_suggestion": suggestion})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000, debug=True)
