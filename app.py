from flask import Flask, render_template, request, redirect, session, url_for, flash, jsonify
from pymongo import MongoClient
from bson import ObjectId
import qrcode
import io
import os
import random
from bson.objectid import ObjectId  # Asegúrate de importar esto
from werkzeug.security import check_password_hash, generate_password_hash
import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import json


app = Flask(__name__)
app.secret_key = os.urandom(24)

port = random.randint(1000,9999)

# Configura la conexión con MongoDB Atlas
client = MongoClient("mongodb+srv://carlosnieves:Uo7pzJh5iDvlS37M@cluster0.9t4o9.mongodb.net/")
db = client["dbqr"]
users_collection = db["dbqrcol"]
scraped_data_collection = db["scraped_data"]
medics_collection = db["medkeys"]

# Ruta principal (página de inicio)



@app.route("/home")
def home():
    return render_template("home.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        # Captura los datos del formulario
        username = request.form.get("full_name")  # Renombramos full_name como username
        health_card_number = request.form.get("health_card_number")  # Consideramos health_card_number como único identificador
        password = request.form.get("password")  # Agrega un campo de contraseña al formulario si falta

        # Información médica y personal
        medical_info = {
            "age": request.form.get("age"),
            "sex": request.form.get("sex"),
            "blood_type": request.form.get("blood_type"),
            "diseases": request.form.get("diseases"),
            "medications": request.form.get("medications"),
            "MPID": request.form.get("MPID"),
            "base_treatment": request.form.get("base_treatment"),
            "immunosuppression": request.form.get("immunosuppression"),
            "comorbidities": request.form.get("comorbidities"),
            "smoker": request.form.get("smoker"),
            "physical_activity": request.form.get("physical_activity"),
            "alcohol_consumption": request.form.get("alcohol_consumption"),
            "asma": request.form.get("asma"),
        }

        # Validar campos requeridos
        required_fields = [username, health_card_number, password]
        if not all(required_fields):
            return "Por favor completa todos los campos obligatorios", 400

        # Verifica si el usuario ya está registrado por health_card_number (email en tu lógica actual)
        if users_collection.find_one({"health_card_number": health_card_number}):
            return "El número de tarjeta sanitaria ya está registrado", 400

        # Hash de la contraseña para mayor seguridad
        hashed_password = generate_password_hash(password)

        # Inserta el usuario en la base de datos
        user = {
            "username": username,
            "health_card_number": health_card_number,
            "password": hashed_password,
            "medical_info": medical_info,
        }
        result = users_collection.insert_one(user)

        session["user_id"] = str(result.inserted_id)
        session["username"] = username

        # Genera el QR del usuario
        user_id = str(result.inserted_id)
        qr_code = qrcode.make(f"http://localhost:{port}/user/{user_id}")
        qr_io = io.BytesIO()
        qr_code.save(qr_io, "PNG")
        qr_io.seek(0)

        # Guarda el QR en un archivo
        with open(f"static/qrcodes/{user_id}.png", "wb") as qr_file:
            qr_file.write(qr_io.read())

        # Redirige al inicio de sesión después del registro
        return redirect(url_for("dashboard"))

    # Renderiza el formulario de registro
    return render_template("register.html")


# Ruta de login

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        login_as = request.form.get('login_as')

        # Login como usuario
        if login_as == 'user':
            health_card_number = request.form.get('health_card_number')
            password = request.form.get('password')

            user = users_collection.find_one({"health_card_number": health_card_number})

            if user and check_password_hash(user['password'], password):
                session['user_id'] = str(user['_id'])
                session["username"] = user["username"]
                return redirect(url_for('dashboard'))
            else:
                flash("Número de tarjeta sanitaria o contraseña incorrectos.", "error")
                return redirect(url_for("login"))

        # Login como médico
        elif login_as == 'medic':
            health_card_number = request.form.get('health_card_number_medic')
            medic_key = request.form.get('medic_key')

            medic = medics_collection.find_one({"medic_key": medic_key})

            if medic:
                user = users_collection.find_one({"health_card_number": health_card_number})

                if user:
                    session['medic_id'] = str(medic['_id'])
                    return redirect(url_for('home', user_id=str(user['_id'])))
                else:
                    flash("Pacient no trobat amb aquesta tarjeta sanitària.", "error")
            else:
                flash("Clau de metge incorrecta.", "error")

            return redirect(url_for("login"))
    return render_template('login.html')


# Ruta de dashboard (área privada)
@app.route('/dashboard')
def dashboard():
    user_id = session.get('user_id')  # Obtener el user_id de la sesión
    if not user_id:
        return redirect(url_for('login'))  # Redirigir al login si no hay sesión activa
    
    # Convertir el user_id de vuelta a ObjectId
    user = users_collection.find_one({"_id": ObjectId(user_id)})
    if not user:
        return "Usuario no encontrado."

    # Construir la ruta del código QR
    qr_code_path = f"qrcodes/{user_id}.png"

    # Lógica para mostrar el dashboard
    return render_template('dashboard.html', user=user, qr_code_path=qr_code_path)



# Ruta para mostrar la información del usuario a través del QR
@app.route('/user/<user_id>')
def user_profile(user_id):
    user = users_collection.find_one({"_id": ObjectId(user_id)})

    if not user:
        return "Usuari no trobat.", 404

    session['user_id'] = str(user['_id'])
    session['username'] = user['username']

    return render_template("user_info.html", user=user)

# Ruta para logout
@app.route("/logout")
def logout():
    session.pop("user_id", None)
    session.pop("username", None)
    return redirect(url_for("/"))

if __name__ == "__main__":
    # Crea el directorio para guardar los códigos QR si no existe
    if not os.path.exists("static/qrcodes"):
        os.makedirs("static/qrcodes")

    app.run(debug=True, port=port)
