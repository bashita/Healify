import os
from flask import Flask, flash, render_template, request, redirect, session, url_for,jsonify
import requests
import pymysql
from werkzeug.security import generate_password_hash, check_password_hash
from plyer import notification
from datetime import datetime
import pymysql.cursors
import json
from pywebpush import webpush
from openai import OpenAI
from apscheduler.schedulers.background import BackgroundScheduler
import winsound
from flask_cors import CORS
import random
user_name=None

app = Flask(__name__,template_folder='templates')
app.secret_key = 'healify'
"""client=OpenAI(api_key="")
CORS(app,origins=["https://127.0.0.1:5000"])"""


def db_connection():
    return pymysql.connect(host='localhost',
                           user='root',
                           password='mysql',
                           db='healify',
                           charset='utf8mb4',
                           cursorclass=pymysql.cursors.DictCursor)

# Home page
@app.route('/')
def home():
    return render_template('home.html')


# Sign In page
@app.route('/signin', methods=['GET', 'POST'])
def signin():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        db=db_connection()
        cursor=db.cursor()
        cursor.execute("SELECT * FROM user WHERE username = %s", (username,))
        user = cursor.fetchone()
        db.close()
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            return redirect(url_for('dashboard'))
        else:
            return "Invalid credentials!"
    return render_template('signin.html')


# Sign Up page
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        hashed_password = generate_password_hash(password)
        db=db_connection()
        cursor=db.cursor()
        cursor.execute("INSERT INTO user (username, password) VALUES (%s, %s)", (username, hashed_password))
        db.commit()
        db.close()
        return redirect(url_for('signin'))
    return render_template('signup.html')


# Dashboard after login
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('signin'))
    return render_template('index.html')

@app.route('/chatbot')
def chatbot():
    return render_template('chatbot.html')  

@app.route('/chat', methods=['POST'])
def chat():
    data = request.get_json()
    user_message = data.get("message")

    """
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are Healify, a helpful healthcare assistant. Give safe general health advice only."},
                {"role": "user", "content": user_message}
            ]
        )

        ai_reply = response.choices[0].message.content
        # Save to chat history
        db=db_connection()
        cursor=db.cursor()
        user_id = session.get('user_id',1)
        cursor.execute("INSERT INTO chat_history (user_id, message, bot_reply) VALUES (%s, %s, %s)", (user_id, user_message, ai_reply))
        db.commit()
        # Also save care plan if user asks for it
        if "care plan" in ai_reply.lower():
            cursor.execute("INSERT INTO care_plan (user_id, bot_reply) VALUES (%s, %s)", (user_id, ai_reply))
            db.commit()
        cursor.close()
        db.close()

        return jsonify({"reply": ai_reply})"""
    bot_reply=generate_reply(user_message)
    db=db_connection()
    cursor=db.cursor()
    user_id = session.get('user_id',1)
    cursor.execute("INSERT INTO chat_history (user_id, message, bot_reply) VALUES (%s, %s, %s)", (user_id, user_message, bot_reply))
    db.commit()
    # Also save care plan if user asks for it
    if "care plan" in bot_reply.lower():
        cursor.execute("INSERT INTO care_plan (user_id, bot_reply) VALUES (%s, %s)", (user_id, bot_reply))
        db.commit()
    cursor.close()
    db.close()

    """except Exception as e:
        print("Error:", e)"""
    return jsonify({"reply": bot_reply})

#history page to show past conversations
@app.route('/history')
def history():
    if 'user_id' not in session:
        flash("Please log in first.", "warning")
        return redirect(url_for('dashboard'))
    db=db_connection()
    cursor=db.cursor()
    cursor.execute("SELECT message, bot_reply, timestamp FROM chat_history WHERE user_id = %s ORDER BY timestamp ASC", (session['user_id'],))
    customers = cursor.fetchall()
    return render_template('history.html', customers=customers)

# About Us page
@app.route('/about')
def about():
    return render_template('about.html')

def extract_name(user_message):
    # Simple heuristic to extract name (you can improve this with NLP techniques)
    words = user_message.lower().split()
    if "my name is" in user_message.lower():
        return user_message.lower().split("my name is")[-1].strip().split()[0].capitalize()
    elif "i am" in user_message.lower():
        return user_message.lower().split("i am")[-1].strip().split()[0].capitalize()
    return None

# sample AI response generator
def generate_reply(user_input):
    global user_name, care_plan

    text = user_input.lower()

    # --- Name Detection ---
    if "i am" in text:
        user_name = user_input.split("i am")[-1].strip().capitalize()
        return f"Nice to meet you, {user_name}! 😊 I'm here to support your recovery."

    if "my name is" in text:
        user_name = user_input.split("my name is")[-1].strip().capitalize()
        return f"Nice to meet you, {user_name}! 😊 I'm here to support your recovery."

    # --- Greeting ---
    greetings = ["Hi", "Hello", "Hey"]

    if user_name:
        response = f"{random.choice(greetings)}, {user_name}! "
    else:
        response = f"{random.choice(greetings)}! "

    #----Thanks detection---
    if "thank" in text:
        if user_name:
            return f"You're welcome, {user_name}! If you have any more questions or need assistance, feel free to ask. 😊"
        else:
            return "You're welcome! If you have any more questions or need assistance, feel free to ask. 😊"

    # --- Care Plan Trigger ---
    if "care plan" in text or "what should i do" in text:
        
        if "surgery" in text:
            care_plan = [
                "Take proper rest and avoid heavy movement",
                "Keep the wound clean and dry",
                "Take prescribed medicines on time",
                "Attend follow-up appointments"
            ]
        elif "fever" in text:
            care_plan = [
                "Monitor temperature regularly",
                "Stay hydrated",
                "Take medication if prescribed",
                "Consult doctor if fever persists"
            ]
        elif "pain" in text:
            care_plan = [
                "Take pain relief medication as prescribed",
                "Avoid strain on affected area",
                "Apply hot/cold compress if advised",
                "Get enough rest"
            ]
        else:
            care_plan = [
                "Maintain a healthy diet",
                "Stay hydrated",
                "Sleep well",
                "Follow doctor's advice"
            ]

        response += "\nHere’s your recommended care plan:\n"
        for i, step in enumerate(care_plan, 1):
            response += f"{i}. {step}\n"

        return response

    # --- Normal Responses ---
    if "pain" in text:
        response += "It's normal to experience some pain during recovery."
    elif "fever" in text:
        response += "Keep track of your temperature and stay hydrated."
    elif "tired" in text or "weak" in text:
        response += "Feeling tired is common during recovery. Get enough rest."
    else:
        response += "Make sure you're getting enough rest and proper nutrition."

    return response

scheduler = BackgroundScheduler()
scheduler.start()

def trigger_alarm(medicine):

    notification.notify(
        title="💊 Medicine Reminder",
        message=f"Time to take: {medicine}",
        timeout=20
    )

    try:
        winsound.Beep(1000, 3000)
    except:
        pass


# ---------------------------
# LOAD EXISTING REMINDERS
# ---------------------------

def load_existing_reminders():

    db = db_connection()
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT medicine, reminder_time FROM reminder")
    reminders = cursor.fetchall()

    for row in reminders:

        medicine = row["medicine"]
        reminder_time = str(row["reminder_time"])

        hour, minute, *_ = map(int, reminder_time.split(":"))

        scheduler.add_job(
            trigger_alarm,
            trigger='cron',
            hour=hour,
            minute=minute,
            args=[medicine],
            id=f"{medicine}-{hour}-{minute}",
            replace_existing=True
        )

    db.close()

# ---------------------------
# HOME PAGE
# ---------------------------


# ---------------------------
# ADD REMINDER
# ---------------------------

@app.route('/prescription')
def prescription():
    if 'user_id' not in session:
        return redirect(url_for('signin'))
    return render_template('prescription.html')

@app.route('/add', methods=['POST'])
def add_reminder():

    data = request.json
    medicine = data["medicine"]
    time_str = data["time"]

    db = db_connection()
    cursor = db.cursor()

    cursor.execute(
        "INSERT INTO reminder (medicine, reminder_time) VALUES (%s,%s)",
        (medicine, time_str)
    )

    db.commit()
    db.close()

    hour, minute = map(int, time_str.split(":"))

    scheduler.add_job(
        trigger_alarm,
        trigger='cron',
        hour=hour,
        minute=minute,
        args=[medicine],
        id=f"{medicine}-{hour}-{minute}",
        replace_existing=True
    )

    return jsonify({"status": "Reminder Added Successfully"})


# ---------------------------
# GET REMINDERS
# ---------------------------

@app.route('/get')
def get_reminders():

    db = db_connection()
    cursor = db.cursor()

    cursor.execute("SELECT medicine, reminder_time FROM reminder")
    reminders = cursor.fetchall()

    db.close()

    result = []

    for row in reminders:
        result.append({
            "medicine": row["medicine"],
            "time": str(row["reminder_time"])
        })

    return jsonify(result)
# Care Plan page to show AI-generated care plans
@app.route('/careplan')
def careplan():
    if 'user_id' not in session:
        flash("Please log in first.", "warning")
        return redirect(url_for('dashboard'))
    db=db_connection()
    cursor=db.cursor()
    cursor.execute("SELECT bot_reply FROM care_plan WHERE user_id = %s", (session['user_id'],))
    customers = cursor.fetchall()
    return render_template('careplan.html', customers=customers)

# Endpoint to receive push subscription from frontend
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))



if __name__ == '__main__':
    app.run(debug=True)

