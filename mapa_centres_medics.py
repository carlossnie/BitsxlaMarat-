import requests

def get_nearby_hospitals_osm(latitude, longitude, radius=5000):
    """
    Busca hospitales cerca de una ubicación utilizando Overpass API.
    
    Args:
        latitude (float): Latitud de la ubicación.
        longitude (float): Longitud de la ubicación.
        radius (int): Radio de búsqueda en metros.
    
    Returns:
        list: Lista de hospitales con nombres y coordenadas.
    """
    # Define la consulta Overpass
    overpass_url = "http://overpass-api.de/api/interpreter"
    overpass_query = f"""
    [out:json];
    (
      node["amenity"="hospital"](around:{radius},{latitude},{longitude});
      way["amenity"="hospital"](around:{radius},{latitude},{longitude});
      relation["amenity"="hospital"](around:{radius},{latitude},{longitude});
    );
    out center;
    """
    
    try:
        response = requests.get(overpass_url, params={'data': overpass_query})
        response.raise_for_status()
        data = response.json()

        hospitals = []
        for element in data.get("elements", []):
            if "tags" in element:
                hospitals.append({
                    "name": element["tags"].get("name", "Hospital sin nombre"),
                    "latitude": element.get("lat") or element["center"]["lat"],
                    "longitude": element.get("lon") or element["center"]["lon"]
                })
        return hospitals

    except requests.exceptions.RequestException as e:
        print(f"Error al consultar Overpass API: {e}")
        return []

# Ejemplo de uso
latitude = 41.4036  # Latitud de ejemplo (Barcelona)
longitude = 2.1744  # Longitud de ejemplo (Barcelona)

hospitals = get_nearby_hospitals_osm(latitude, longitude)
if hospitals:
    print("Centros médicos cercanos:")
    for i, hospital in enumerate(hospitals, start=1):
        print(f"{i}. {hospital['name']} - Ubicación: ({hospital['latitude']}, {hospital['longitude']})")
else:
    print("No se encontraron hospitales en el área especificada.")


import folium

def display_hospitals_on_map(hospitals, latitude, longitude):
    """Muestra los hospitales en un mapa interactivo usando Folium."""
    # Crea el mapa centrado en la ubicación del usuario
    map_ = folium.Map(location=[latitude, longitude], zoom_start=14)

    # Añade un marcador para cada hospital
    for hospital in hospitals:
        folium.Marker(
            [hospital['latitude'], hospital['longitude']],
            popup=hospital['name'],
            icon=folium.Icon(color="red", icon="info-sign")
        ).add_to(map_)

    # Guarda el mapa en un archivo HTML
    map_.save("hospitales_cercanos.html")
    print("Mapa guardado como 'hospitales_cercanos.html'. Ábrelo en tu navegador para visualizarlo.")

# Visualizar en un mapa
if hospitals:
    display_hospitals_on_map(hospitals, latitude, longitude)
