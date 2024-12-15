from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
from pymongo import MongoClient
from bson import ObjectId
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime
import json
import os
import qrcode
import io
import random

app = Flask(__name__)
app.secret_key = 'clave_segura_2024'
port = random.randint(1000,9999)

# MongoDB configuration
client = MongoClient("mongodb+srv://carlosnieves:Uo7pzJh5iDvlS37M@cluster0.9t4o9.mongodb.net/", tls=True, tlsAllowInvalidCertificates=True)
db = client["dbqr"]
users_collection = db["dbqrcol"]
medics_collection = db["medkeys"]

# DataStore class for local data
class DataStore:
    def __init__(self):
        self.data_dir = 'data'
        os.makedirs(self.data_dir, exist_ok=True)
        self.perfil = self.cargar_datos('perfil.json')
        self.sintomas = self.cargar_datos('sintomas.json')
        self.pruebas = self.cargar_datos('pruebas.json')

    def cargar_datos(self, archivo):
        try:
            with open(f'{self.data_dir}/{archivo}', 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            return {}

    def guardar_datos(self, datos, archivo):
        with open(f'{self.data_dir}/{archivo}', 'w', encoding='utf-8') as f:
            json.dump(datos, f, ensure_ascii=False, indent=4)

    def actualizar_perfil(self, datos):
        try:
            self.perfil = datos
            self.guardar_datos(self.perfil, 'perfil.json')
            return True
        except Exception as e:
            print(f"Error al actualizar perfil: {str(e)}")
            return False

local_db = DataStore()

# Login required decorator
def login_required(f):
    def decorated_function(*args, **kwargs):
        # Verificar si estamos accediendo por número de tarjeta sanitaria
        if request.path.startswith('/main/'):
            health_card_number = request.path.split('/')[-1]
            user = users_collection.find_one({"health_card_number": health_card_number})
            if user:
                # Si encontramos el usuario, permitir el acceso
                session['temp_access'] = True
                session['viewing_card_number'] = health_card_number
                return f(*args, **kwargs)
        
        # Verificación normal de login para otras rutas
        if 'user_id' not in session and 'temp_access' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

def validate_health_card(number):
    return bool(number and isinstance(number, str) and len(number) == 14 and 
                number.startswith('08') and number.isdigit())

def validate_medic_key(key):
    return bool(key and isinstance(key, str) and len(key) == 6 and key.isdigit())

# Authentication routes
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        login_as = request.form.get('login_as')

        if login_as == 'user':
            health_card_number = request.form.get('health_card_number')
            if not validate_health_card(health_card_number):
                flash("Format de targeta sanitària invàlid.", "error")
                return render_template('login.html')
            password = request.form.get('password')
            user = users_collection.find_one({"health_card_number": health_card_number})

            if user and check_password_hash(user['password'], password):
                session['user_id'] = str(user['_id'])
                session["username"] = user["username"]
                return redirect(url_for('main_page'))
            flash("Número de targeta sanitària o contrasenya incorrectes.", "error")

        elif login_as == 'medic':
            health_card_number = request.form.get('health_card_number_medic')
            medic_key = request.form.get('medic_key')
            
            if not validate_health_card(health_card_number):
                flash("Format de targeta sanitària invàlid.", "error")
                return render_template('login.html')
                
            if not validate_medic_key(medic_key):
                flash("Format de clau de metge invàlid.", "error")
                return render_template('login.html')
                
            medic = medics_collection.find_one({"medic_key": medic_key})
            user = users_collection.find_one({"health_card_number": health_card_number})

            if medic and user:
                session['medic_id'] = str(medic['_id'])
                session['user_id'] = str(user['_id'])  # Store the patient's user ID
                session['viewing_card_number'] = health_card_number
                session['is_medic'] = True
                return redirect(url_for('main_page'))
            else:
                if not medic:
                    flash("Clau de metge incorrecta.", "error")
                if not user:
                    flash("Pacient no trobat amb aquesta targeta sanitària.", "error")

    return render_template('login.html')

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        health_card_number = request.form.get("health_card_number")
        
        if not validate_health_card(health_card_number):
            flash("Format de targeta sanitària invàlid.", "error")
            return render_template('register.html')
            
        username = request.form.get("full_name")
        password = request.form.get("password")

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

        if users_collection.find_one({"health_card_number": health_card_number}):
            return "El número de targeta sanitària ja està registrat", 400

        hashed_password = generate_password_hash(password)
        user = {
            "username": username,
            "health_card_number": health_card_number,
            "password": hashed_password,
            "medical_info": medical_info,
        }
        result = users_collection.insert_one(user)

        # Store the new user's ID right after insertion
        user_id = str(result.inserted_id)

        # Generate QR code with health_card_number instead of user_id
        qr_code = qrcode.make(f"http://localhost:{port}/main/{health_card_number}")
        
        # Save QR code using health_card_number as filename
        qr_filename = f"{health_card_number}.png"
        os.makedirs("static/qrcodes", exist_ok=True)
        qr_path = os.path.join("static/qrcodes", qr_filename)
        qr_code.save(qr_path)

        session["user_id"] = user_id
        session["username"] = username
        return render_template("dashboard.html", qr_code_path=f"qrcodes/{qr_filename}", codi_qr=f"qrcodes/{qr_filename}")

    return render_template("register.html")

# User profile routes
@app.route('/user/<user_id>')
def user_profile(user_id):
    user = users_collection.find_one({"_id": ObjectId(user_id)})
    if not user:
        return "Usuario no encontrado.", 404
    return render_template("user_info.html", user=user)

# Main application routes - Renamed to avoid conflicts
@app.route('/main')
@app.route('/main/<health_card_number>')
@login_required
def main_page(health_card_number=None):
    try:
        # Si viene con health_card_number en la URL
        if health_card_number:
            user = users_collection.find_one({"health_card_number": health_card_number})
            if user:
                # Guardar en sesión y redirigir limpiando la URL
                session['viewing_card_number'] = health_card_number
                session['temp_access'] = True
                return redirect(url_for('main_page'))
            else:
                flash("Usuario no encontrado", "error")
                return redirect(url_for('login'))
        
        # Para la ruta /main normal
        if session.get('viewing_card_number'):
            # Si hay un número de tarjeta en la sesión, usarlo
            user = users_collection.find_one({"health_card_number": session['viewing_card_number']})
            if not user:
                session.pop('viewing_card_number', None)
                return "Usuario no encontrado.", 404
        else:
            # Usuario normal logueado
            user = users_collection.find_one({"_id": ObjectId(session['user_id'])})
            if not user:
                return "Usuario no encontrado.", 404

        is_medic = session.get('is_medic', False)
        return render_template('main.html', user_data=user, is_medic=is_medic)

    except Exception as e:
        print(f"Error: {str(e)}")
        return redirect(url_for('login'))

@app.route('/perfil')
@login_required
def perfil():
    section = request.args.get('section', '')
    return render_template('editar_perfil.html', section=section)

@app.route('/estado')
@login_required
def estado_actual():
    return render_template('estado.html', sintomas=local_db.sintomas)

@app.route('/urgencias')
@login_required
def urgencias():
    # Check if user is a medic
    is_medic = session.get('is_medic', False)
    return render_template('guia_urgencies.html', pruebas=local_db.pruebas, is_medic=is_medic)

@app.route('/historial')
@login_required
def historial():
    return render_template('historial_proves.html', pruebas=local_db.pruebas)

@app.route('/centros')
@login_required
def centros():
    return render_template('centres_medics.html')

@app.route('/noticias')
@login_required
def noticias():
    return render_template('novetats.html')

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for('login'))

# API endpoints
@app.route('/api/actualizar_perfil', methods=['POST'])
@login_required
def actualizar_perfil():
    try:
        datos = request.get_json()
        
        # Prepare the update document for MongoDB
        update_data = {
            "medical_info.smoker": datos["factores_riesgo"]["fumador"],
            "medical_info.physical_activity": datos["factores_riesgo"]["esports"],
            "medical_info.alcohol_consumption": datos["factores_riesgo"]["alcohol"],
            "medical_info.asma": datos["factores_riesgo"]["asma"],
            "medical_info.MPID": datos["datos_clinicos"]["mpid"],
            "medical_info.diseases": datos["datos_clinicos"]["malalties_croniques"],
            "medical_info.base_treatment": datos["datos_clinicos"]["tractament_base"],
            "medical_info.immunosuppression": datos["datos_clinicos"]["immunosupressions"],
            "medical_info.comorbidities": datos["datos_clinicos"]["comorbiditats"],
            "medical_info.medications": datos["datos_clinicos"]["medicacio"],
            "username": datos["datos_personales"]["nom"],
            "medical_info.age": datos["datos_personales"]["edat"],
            "medical_info.sex": datos["datos_personales"]["sexe"],
            "health_card_number": datos["datos_personales"]["targeta_sanitaria"],
            "medical_info.blood_type": datos["datos_personales"]["grup_sanguini"]
        }
        
        # Update MongoDB
        result = users_collection.update_one(
            {"_id": ObjectId(session["user_id"])},
            {"$set": update_data}
        )

        if result.modified_count > 0:
            # Also update local storage
            if local_db.actualizar_perfil(datos):
                return jsonify({"status": "success"})
            return jsonify({"status": "error", "message": "Error updating local database"})
        return jsonify({"status": "error", "message": "No changes were made"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/guardar_sintomas', methods=['POST'])
@login_required
def guardar_sintomas():
    try:
        datos = request.get_json()
        fecha = datetime.now().strftime("%Y-%m-%d")
        local_db.sintomas[fecha] = {
            'estado_general': datos.get('estado_general'),
            'sintomas_especificos': datos.get('sintomas_especificos'),
            'temperatura': datos.get('temperatura'),
            'nivel_dolor': datos.get('nivel_dolor'),
            'notas': datos.get('notas'),
            'fecha_registro': fecha
        }
        local_db.guardar_datos(local_db.sintomas, 'sintomas.json')
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/cargar_perfil')
@login_required
def cargar_perfil():
    try:
        # Usar viewing_card_number de la sesión si existe
        if session.get('viewing_card_number'):
            user = users_collection.find_one({"health_card_number": session['viewing_card_number']})
        else:
            # Si no, usar el user_id
            user = users_collection.find_one({"_id": ObjectId(session.get('user_id'))})
        
        if not user:
            print("Usuario no encontrado")  # Para debug
            return jsonify({"status": "error", "message": "Usuario no encontrado"})

        print("Usuario encontrado:", user)  # Para debug
        
        datos = {
            "status": "success",
            "data": {
                "factores_riesgo": {
                    "fumador": "Sí" if user['medical_info'].get('smoker') == "Yes" else "No" if user['medical_info'].get('smoker') == "No" else "Ex-fumador",
                    "esports": "Sí" if user['medical_info'].get('physical_activity') == "Yes" else "No",
                    "alcohol": "Sí" if user['medical_info'].get('alcohol_consumption') == "Yes" else "No",
                    "asma": "Sí" if user['medical_info'].get('asma') == "Yes" else "No"
                },
                "datos_clinicos": {
                    "mpid": user['medical_info'].get('MPID', 'Sense dades'),
                    "tractament_base": user['medical_info'].get('base_treatment', 'Sense dades'),
                    "immunosupressions": "Sí" if user['medical_info'].get('immunosuppression') == "yes" else "No",
                    "comorbiditats": user['medical_info'].get('comorbidities', 'Sense dades'),
                    "antecedents": user['medical_info'].get('diseases', 'Sense dades'),
                    "medicacio": user['medical_info'].get('medications', 'Sense dades')
                },
                "datos_personales": {
                    "nom": user['username'],
                    "edat": user['medical_info'].get('age', 'Sense dades'),
                    "sexe": "Home" if user['medical_info'].get('sex') == "Male" else "Dona",
                    "targeta_sanitaria": user['health_card_number'],
                    "grup_sanguini": user['medical_info'].get('blood_type', 'Sense dades')
                }
            }
        }
        print("Datos enviados:", datos)  # Para debug
        return jsonify(datos)
    except Exception as e:
        print("Error en cargar_perfil:", str(e))
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/verificar_clave_medico', methods=['POST'])
def verificar_clave_medico():
    try:
        data = request.get_json()
        medic_key = data.get('medic_key')
        
        # Check if the key exists in the medics collection
        medic = medics_collection.find_one({"medic_key": medic_key})
        
        if medic:
            return jsonify({"status": "success"})
        else:
            return jsonify({"status": "error", "message": "Invalid medical key"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/dashboard')
@login_required
def dashboard():
    # Primero intentar obtener el usuario por el health_card_number de la sesión
    if 'viewing_card_number' in session:
        health_card_number = session['viewing_card_number']
    else:
        # Si no hay viewing_card_number, usar el user_id normal
        user = users_collection.find_one({"_id": ObjectId(session['user_id'])})
        if not user:
            return "Usuario no encontrado.", 404
        health_card_number = user['health_card_number']
    
    qr_filename = f"{health_card_number}.png"
    return render_template('dashboard.html', qr_code_path=f"qrcodes/{qr_filename}", codi_qr=f"qrcodes/{qr_filename}")

if __name__ == '__main__':
    os.makedirs('data', exist_ok=True)
    os.makedirs('static/qrcodes', exist_ok=True)
    
    print(f"Server started at http://localhost:{port}")
    app.run(host='0.0.0.0', port=port, debug=True)

#a