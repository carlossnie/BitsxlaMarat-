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
from mapa_centres_medics import get_nearby_hospitals_osm, display_hospitals_on_map
import folium
from folium import plugins

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
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

# Authentication routes
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        login_as = request.form.get('login_as')

        if login_as == 'user':
            health_card_number = request.form.get('health_card_number')
            password = request.form.get('password')
            user = users_collection.find_one({"health_card_number": health_card_number})

            if user and check_password_hash(user['password'], password):
                session['user_id'] = str(user['_id'])
                session["username"] = user["username"]
                return redirect(url_for('main_page'))
            flash("Número de tarjeta sanitaria o contraseña incorrectos.", "error")

        elif login_as == 'medic':
            health_card_number = request.form.get('health_card_number_medic')
            medic_key = request.form.get('medic_key')
            medic = medics_collection.find_one({"medic_key": medic_key})

            if medic:
                user = users_collection.find_one({"health_card_number": health_card_number})
                if user:
                    session['medic_id'] = str(medic['_id'])
                    return redirect(url_for('main_page'))
                flash("Pacient no trobat amb aquesta tarjeta sanitària.", "error")
            else:
                flash("Clau de metge incorrecta.", "error")

    return render_template('login.html')

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("full_name")
        health_card_number = request.form.get("health_card_number")
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
            return "El número de tarjeta sanitaria ya está registrado", 400

        hashed_password = generate_password_hash(password)
        user = {
            "username": username,
            "health_card_number": health_card_number,
            "password": hashed_password,
            "medical_info": medical_info,
        }
        result = users_collection.insert_one(user)

        # Generate QR code with main URL including user_id
        user_id = str(result.inserted_id)
        qr_code = qrcode.make(f"http://localhost:{port}/main/{user_id}")
        
        # Save QR code
        qr_filename = f"{user_id}.png"
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
@app.route('/main/<user_id>')
@login_required
def main_page(user_id=None):
    if user_id:
        # If accessing through QR, load that user's data
        user = users_collection.find_one({"_id": ObjectId(user_id)})
        if not user:
            return "Usuario no encontrado.", 404
    else:
        # If accessing normally, load logged in user's data
        user = users_collection.find_one({"_id": ObjectId(session['user_id'])})
    
    if not user:
        return "Usuario no encontrado.", 404

    return render_template('main.html', user_data=user)

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
    return render_template('guia_urgencies.html', pruebas=local_db.pruebas)

@app.route('/historial')
@login_required
def historial():
    return render_template('historial_proves.html', pruebas=local_db.pruebas)

@app.route('/centros')
@login_required
def centros():
    try:
        # Default coordinates (Barcelona)
        latitude = 41.4036
        longitude = 2.1744
        
        # Get nearby hospitals
        hospitals = get_nearby_hospitals_osm(latitude, longitude)
        
        # Create map with better default zoom
        map_object = folium.Map(
            location=[latitude, longitude],
            zoom_start=13,
            tiles='OpenStreetMap'
        )
        
        # Add fullscreen option
        folium.plugins.Fullscreen().add_to(map_object)
        
        # Add locate control
        locate_control = """
            L.control.locate({
                position: 'topleft',
                strings: {
                    title: "Show my location"
                }
            }).addTo(map);
        """
        map_object.get_root().html.add_child(folium.Element(locate_control))
        
        # Add markers for hospitals
        for hospital in hospitals[:4]:
            folium.Marker(
                location=[hospital['latitude'], hospital['longitude']],
                popup=folium.Popup(hospital['name'], max_width=300),
                icon=folium.Icon(color='red', icon='info-sign')
            ).add_to(map_object)
        
        # Save map to string
        map_html = map_object.get_root().render()
        
        return render_template('centres_medics.html', map_html=map_html, hospitals=hospitals[:4])
    except Exception as e:
        print(f"Error loading map: {e}")
        return render_template('centres_medics.html', error="Error carregant el mapa")

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
        user_id = request.args.get('user_id', session.get('user_id'))
        user = users_collection.find_one({"_id": ObjectId(user_id)})
        
        if not user:
            return jsonify({"status": "error", "message": "Usuario no encontrado"})

        datos = {
            "status": "success",
            "data": {
                "factores_riesgo": {
                    "fumador": user['medical_info'].get('smoker'),
                    "esports": user['medical_info'].get('physical_activity'),
                    "alcohol": user['medical_info'].get('alcohol_consumption'),
                    "asma": user['medical_info'].get('asma')
                },
                "datos_clinicos": {
                    "mpid": user['medical_info'].get('MPID'),
                    "tractament_base": user['medical_info'].get('base_treatment'),
                    "immunosupressions": user['medical_info'].get('immunosuppression'),
                    "comorbiditats": user['medical_info'].get('comorbidities'),
                    "antecedents": user['medical_info'].get('diseases'),
                    "medicacio": user['medical_info'].get('medications')
                },
                "datos_personales": {
                    "nom": user['username'],
                    "edat": user['medical_info'].get('age'),
                    "sexe": user['medical_info'].get('sex'),
                    "targeta_sanitaria": user['health_card_number'],
                    "grup_sanguini": user['medical_info'].get('blood_type')
                }
            }
        }
        return jsonify(datos)
    except Exception as e:
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

@app.route('/api/get_nearby_hospitals')
def get_nearby_hospitals():
    try:
        latitude = float(request.args.get('lat'))
        longitude = float(request.args.get('lon'))
        
        hospitals = get_nearby_hospitals_osm(latitude, longitude)
        display_hospitals_on_map(hospitals, latitude, longitude)
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/dashboard')
@login_required
def dashboard():
    user_id = session.get('user_id')
    qr_filename = f"{user_id}.png"
    return render_template('dashboard.html', qr_code_path=f"qrcodes/{qr_filename}", codi_qr=f"qrcodes/{qr_filename}")

if __name__ == '__main__':
    os.makedirs('data', exist_ok=True)
    os.makedirs('static/qrcodes', exist_ok=True)
    
    print(f"Server started at http://localhost:{port}")
    app.run(host='0.0.0.0', port=port, debug=True)