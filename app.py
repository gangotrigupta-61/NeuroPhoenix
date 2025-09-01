import os
import secrets
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import  mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash
from authlib.integrations.flask_client import OAuth
from urllib.parse import urljoin
from dotenv import load_dotenv


# Generate a random key if not found in .env
secret_key = os.getenv("FLASK_SECRET_KEY")
if not secret_key:
    secret_key = secrets.token_hex(32)  # generates a secure random key
    print(f"[INFO] Generated secret key: {secret_key}")  # shows in terminal

# --- Gemini AI ---
import google.generativeai as genai

# Load .env values
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev_secret_change_me")


# ---- MySQL Config ----
mydb = mysql.connector.connect(
    host=os.environ.get("DB_HOST"),
    user=os.environ.get("DB_USER"),
    password=os.environ.get("DB_PASSWORD"),
    database=os.environ.get("DB_NAME"),
    port=int(os.environ.get("DB_PORT"))
)




# ---- Google OAuth Config ----
oauth = OAuth(app)
google = oauth.register(
    name='google',
    client_id=os.getenv("GOOGLE_CLIENT_ID", ""),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET", ""),
    access_token_url='https://oauth2.googleapis.com/token',
    authorize_url='https://accounts.google.com/o/oauth2/v2/auth',
    api_base_url='https://www.googleapis.com/oauth2/v2/',
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'}
)

def _abs_url(endpoint):
    return urljoin(request.url_root, url_for(endpoint))

# ---- Gemini Setup ----
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

model = genai.GenerativeModel("gemini-1.5-flash")

# ---- Routes ----

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/auth", methods=["GET","POST"])
def auth():
    if request.method == "POST":
        action = request.form.get("action")
        email = request.form["email"].lower()
        password = request.form["password"]

        cursor = mydb.cursor()

        if action == "signup":
            cursor.execute("SELECT * FROM users WHERE email=%s", (email,))
            if cursor.fetchone():
                flash("Email already registered. Please login.")
                cursor.close()
                return redirect(url_for("auth"))

            hashed_pw = generate_password_hash(password)
            cursor.execute("INSERT INTO users (email, password, auth_provider) VALUES (%s,%s,%s)", 
                        (email, hashed_pw, "password"))
            mydb.commit()
            cursor.close()
            flash("Signup successful. Please login!")
            return redirect(url_for("auth"))

        elif action == "login":
            cursor.execute("SELECT * FROM users WHERE email=%s", (email,))
            user = cursor.fetchone()
            cursor.close()
            if user and user[2] and check_password_hash(user[2], password):
                session["user_id"] = user[0]
                session["email"] = user[1]
                flash("Login successful!")
                return redirect(url_for("home"))
            else:
                flash("Invalid login credentials.")
                return redirect(url_for("auth"))

    return render_template("auth.html")

@app.route("/login/google")
def login_google():
    redirect_uri = _abs_url("auth_google_callback")
    return google.authorize_redirect(redirect_uri)

@app.route("/auth/google/callback")
def auth_google_callback():
    token = google.authorize_access_token()
    resp = google.get("userinfo")
    info = resp.json()
    email = info.get("email")
    name = info.get("name")

    cursor = mydb.connect.cursor()
    cursor.execute("SELECT * FROM users WHERE email=%s", (email,))
    user = cursor.fetchone()
    if not user:
        cursor.execute("INSERT INTO users (email, name, auth_provider) VALUES (%s,%s,%s)", 
                    (email, name, "google"))
        mydb.commit()
        user_id = cursor.lastrowid
    else:
        user_id = user[0]
    cursor.close()

    session["user_id"] = user_id
    session["email"] = email
    session["name"] = name
    flash("Signed in with Google!")
    return redirect(url_for("home"))

@app.route("/home")
def home():
    if "user_id" not in session:
        return redirect(url_for("auth"))
    return render_template("home.html", name=session.get("name"), email=session.get("email"))

@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/explore")
def explore():
    return render_template("explore.html")

@app.route("/game")
def game():
    return render_template("game.html")

@app.route("/habbit")
def habbit():
    return render_template("habbit.html")

@app.route("/massage")
def massage():
    return render_template("massage.html")

@app.route("/relax")
def relax():
    return render_template("relax.html")

@app.route("/journal")
def journal():
    return render_template("journal.html")

@app.route("/chatbot")
def chatbot():
    return render_template("chatbot.html")

@app.route("/resources")
def resources():
    return render_template("resources.html")

@app.route("/neuroPhoenix")
def neuroPhoenix():
    return render_template("neuroPhoenix.html")

# ---- Gemini Chat API Route ----
@app.route("/ask_gemini", methods=["POST"])
def ask_gemini():
    user_input = request.json.get("message", "")
    if not user_input:
        return jsonify({"error": "No message provided"}), 400
    
    try:
        response = model.generate_content(user_input)
        return jsonify({"reply": response.text})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.")
    return redirect(url_for("auth"))

if __name__ == "__main__":
    app.run(debug=True)