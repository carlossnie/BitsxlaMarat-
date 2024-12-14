def scrape_health_data_to_json():
    """
    Función para scrapear datos de un sitio web, capturarlos y guardarlos en un archivo JSON.
    """
    scraped_results = []

    # URL del sitio a scrapear
    url = "https://pmc.ncbi.nlm.nih.gov/articles/PMC10218114/"  # Cambiar según el objetivo

    try:
        # Realizar la solicitud HTTP
        response = requests.get(url)
        response.raise_for_status()  # Lanza un error si la solicitud falla

        # Analizar el contenido HTML
        soup = BeautifulSoup(response.text, 'html.parser')

        # Extraer encabezados, párrafos y enlaces
        for section in soup.find_all(['h1', 'h2', 'h3', 'p', 'a']):
            text = section.text.strip() if section.text else "No content"
            link = section.get('href') if section.name == 'a' else None

            scraped_item = {
                "source_url": url,
                "tag": section.name,
                "content": text,
                "link": link,
                "scraped_at": datetime.now().isoformat()  # Formato ISO para fechas
            }
            scraped_results.append(scraped_item)

        # Guardar los resultados en un archivo JSON
        json_file_path = "scraped_data.json"
        with open(json_file_path, "w", encoding="utf-8") as json_file:
            json.dump(scraped_results, json_file, ensure_ascii=False, indent=4)

        print(f"Datos scrapeados guardados en {json_file_path}")

        return json_file_path  # Devuelve la ruta del archivo para confirmar

    except Exception as e:
        print(f"Error al scrapear la página: {e}")
        return None

@app.route('/scrape_to_json', methods=['GET'])
def scrape_and_save_to_json():
    """
    Ruta para realizar el scraping y guardar los datos en un archivo JSON.
    """
    if 'user_id' not in session:
        return jsonify({"error": "Acceso no autorizado"}), 403

    try:
        json_file_path = scrape_health_data_to_json()

        if json_file_path:
            return jsonify({
                "message": "Datos scrapeados y guardados en JSON",
                "file_path": json_file_path
            })
        else:
            return jsonify({"message": "No se pudieron scrapear datos"}), 500

    except Exception as e:
        return jsonify({"error": str(e)}), 500