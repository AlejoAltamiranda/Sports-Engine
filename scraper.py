import json
import urllib.request
import re
import base64
from datetime import datetime, timedelta
from collections import defaultdict

# ============================================
# CONFIGURACIÓN GLOBAL
# ============================================
SOURCES = {
    'pltvhd':  'https://pltvhd.com/diaries.json',
    'github':  'https://raw.githubusercontent.com/AlejoAltamiranda/stream/refs/heads/main/events.json',
    'github2': 'https://raw.githubusercontent.com/AlejoAltamiranda/sports-stream-finder/refs/heads/main/events_clean.json',
    'eventos': 'https://streamtpday1.xyz/eventos.json'
}
OUTPUT_FILE = 'scraper_output.json'

# ============================================
# CARGAR BASE DE DATOS DE EQUIPOS
# ============================================

def load_teams_db():
    """Carga la base de datos de equipos desde teams.json"""
    teams_db = {}
    
    try:
        with open('teams.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, list):
                for team in data:
                    if 'name' in team:
                        slug = team['name'].lower().replace(' ', '_')
                        teams_db[slug] = team
            elif isinstance(data, dict):
                teams_db.update(data)
        print(f"✅ Cargados {len(teams_db)} equipos de teams.json")
    except FileNotFoundError:
        print("⚠️ No se encuentra teams.json - La detección de ligas por equipo no estará disponible")
    except Exception as e:
        print(f"⚠️ Error cargando teams.json: {e}")
    
    return teams_db

TEAMS_DB = load_teams_db()

def load_nba_teams():
    """Carga la lista de nombres y alias de equipos NBA desde nba_teams.json"""
    nba_teams = []
    nba_aliases = {}
    
    try:
        with open('nba_teams.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, dict) and 'nba_teams' in data:
                for team in data['nba_teams']:
                    nombre = team.get('name', '')
                    if nombre:
                        nba_teams.append(nombre.lower())
                        aliases = team.get('aliases', [])
                        for alias in aliases:
                            nba_aliases[alias.lower()] = nombre
        print(f"✅ Cargados {len(nba_teams)} equipos NBA con {len(nba_aliases)} alias")
    except FileNotFoundError:
        print("⚠️ No se encuentra nba_teams.json")
    except Exception as e:
        print(f"⚠️ Error cargando nba_teams.json: {e}")
    
    return nba_teams, nba_aliases

NBA_TEAMS, NBA_ALIASES = load_nba_teams()

def normalizar_texto(texto):
    """Normaliza texto eliminando acentos y convirtiendo a minúsculas"""
    if not texto:
        return texto
    
    texto = texto.lower()
    
    reemplazos = {
        'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u',
        'à': 'a', 'è': 'e', 'ì': 'i', 'ò': 'o', 'ù': 'u',
        'â': 'a', 'ê': 'e', 'î': 'i', 'ô': 'o', 'û': 'u',
        'ã': 'a', 'õ': 'o', 'ñ': 'n', 'ç': 'c',
        'ä': 'a', 'ë': 'e', 'ï': 'i', 'ö': 'o', 'ü': 'u',
        'Á': 'a', 'É': 'e', 'Í': 'i', 'Ó': 'o', 'Ú': 'u',
        'À': 'a', 'È': 'e', 'Ì': 'i', 'Ò': 'o', 'Ù': 'u',
        'Â': 'a', 'Ê': 'e', 'Î': 'i', 'Ô': 'o', 'Û': 'u',
        'Ã': 'a', 'Õ': 'o', 'Ñ': 'n', 'Ç': 'c',
        'Ä': 'a', 'Ë': 'e', 'Ï': 'i', 'Ö': 'o', 'Ü': 'u'
    }
    
    for acentuado, sin_acento in reemplazos.items():
        texto = texto.replace(acentuado, sin_acento)
    
    texto = re.sub(r'[^a-z0-9\s-]', '', texto)
    
    return texto.strip()

def detectar_evento_motor(equipos_texto, liga_original):
    """Detecta si el evento es de automovilismo (F1, F2, etc.)"""
    if not equipos_texto:
        return liga_original, None, None
    
    texto_lower = equipos_texto.lower()
    
    palabras_f1 = ['f1', 'formula 1', 'formula uno']
    palabras_f2 = ['f2', 'formula 2', 'formula dos']
    palabras_automovilismo = ['grand prix', 'gp', 'race', 'carrera', 'qualifying', 
                              'clasificacion', 'sprint', 'practice', 'practica', 
                              'premio', 'prix', 'automovilismo', 'indycar', 'motogp']
    
    es_f1 = any(p in texto_lower for p in palabras_f1)
    es_f2 = any(p in texto_lower for p in palabras_f2)
    es_automovilismo = any(p in texto_lower for p in palabras_automovilismo)
    
    if not (es_f1 or es_f2 or es_automovilismo):
        return liga_original, None, None
    
    if es_f1:
        sport = 'f1'
        liga = 'Formula 1'
    elif es_f2:
        sport = 'f2'
        liga = 'Formula 2'
    else:
        sport = 'f1'
        liga = 'Formula 1'
    
    sesion = None
    
    if any(p in texto_lower for p in ['qualifying', 'clasificación', 'clasificacion', 'qualy', 'qual']):
        sesion = 'Qualifying'
    elif 'sprint' in texto_lower:
        sesion = 'Sprint'
    elif any(p in texto_lower for p in ['practice', 'práctica', 'practica', 'fp']):
        if '3' in texto_lower or 'fp3' in texto_lower:
            sesion = 'Practice 3'
        elif '2' in texto_lower or 'fp2' in texto_lower:
            sesion = 'Practice 2'
        else:
            sesion = 'Practice 1'
    elif any(p in texto_lower for p in ['grand prix', 'race', 'carrera', 'gp']):
        sesion = 'Grand Prix'
    else:
        sesion = 'Grand Prix'
    
    gp_nombres = {
        'miami': 'Miami', 'mónaco': 'Monaco', 'monaco': 'Monaco',
        'singapur': 'Singapore', 'singapore': 'Singapore',
        'japón': 'Japan', 'japon': 'Japan', 'japan': 'Japan', 'suzuka': 'Japan',
        'españa': 'Spain', 'spain': 'Spain', 'barcelona': 'Spain',
        'italia': 'Italy', 'italy': 'Italy', 'monza': 'Italy',
        'inglaterra': 'Great Britain', 'england': 'Great Britain', 'silverstone': 'Great Britain',
        'austria': 'Austria', 'spielberg': 'Austria',
        'hungría': 'Hungary', 'hungary': 'Hungary', 'hungaroring': 'Hungary',
        'bélgica': 'Belgium', 'belgium': 'Belgium', 'spa': 'Belgium',
        'francia': 'France', 'france': 'France', 'paul ricard': 'France',
        'holanda': 'Netherlands', 'netherlands': 'Netherlands', 'zandvoort': 'Netherlands',
        'méxico': 'Mexico', 'mexico': 'Mexico', 'ciudad de méxico': 'Mexico',
        'brasil': 'Brazil', 'brazil': 'Brazil', 'interlagos': 'Brazil',
        'bahrein': 'Bahrain', 'bahrain': 'Bahrain',
        'qatar': 'Qatar',
        'abu dhabi': 'Abu Dhabi',
        'yeda': 'Saudi Arabia', 'jeddah': 'Saudi Arabia',
        'austin': 'USA', 'usa': 'USA', 'estados unidos': 'USA',
        'canadá': 'Canada', 'canada': 'Canada', 'montreal': 'Canada',
        'china': 'China', 'shanghai': 'China',
        'australia': 'Australia', 'melbourne': 'Australia',
        'azerbaijan': 'Azerbaijan', 'baku': 'Azerbaijan',
        'turkey': 'Turkey', 'istanbul': 'Turkey'
    }
    
    gp_nombre = None
    for key, value in gp_nombres.items():
        if key in texto_lower:
            gp_nombre = value
            break
    
    if not gp_nombre:
        gp_match = re.search(r'gp\s+([a-z]+)', texto_lower)
        if gp_match:
            gp_nombre = gp_match.group(1).capitalize()
    
    if not gp_nombre and 'grand prix' in texto_lower:
        match = re.search(r'([a-z\s]+?)\s+grand prix', texto_lower)
        if match:
            gp_nombre = match.group(1).strip().title()
    
    if not gp_nombre:
        match = re.search(r'([a-z\s]+?)\s+(?:race|carrera)', texto_lower)
        if match:
            gp_nombre = match.group(1).strip().title()
    
    if not gp_nombre:
        gp_nombre = 'GP'
    
    categoria = 'F1' if sport == 'f1' else 'F2'
    nombre_normalizado = f"{categoria} {gp_nombre} - {sesion}"
    
    return liga, sport, nombre_normalizado

def detectar_liga_por_equipo(equipos_texto, liga_original):
    """Detecta la liga correcta basada en los equipos mencionados."""
    if not equipos_texto:
        return liga_original if liga_original else 'Evento Deportivo'
    
    if 'liga mx femenil' in liga_original.lower():
        return 'Liga MX Femenil'
    
    equipos_texto_normalizado = normalizar_texto(equipos_texto)
    
    # DETECTAR NBA
    if NBA_TEAMS:
        for team in NBA_TEAMS:
            if team in equipos_texto_normalizado:
                return 'NBA'
    
    palabras_internacional = [
        'sudamericano', 'sub-17', 'sub 17', 'sub-20', 'sub 20', 'femenino',
        'selección', 'seleccion', 'amistoso', 'copa', 'torneo', 'mundial'
    ]
    
    for palabra in palabras_internacional:
        if palabra in equipos_texto_normalizado:
            return 'Evento Deportivo'
    
    deportes_excepcion = [
        'mlb', 'nba', 'wnba', 'nfl', 'nhl', 'wwe', 'ufc', 'boxeo', 'boxing',
        'tenis', 'tennis', 'f1', 'formula 1', 'golf', 'atp', 'wta'
    ]
    
    if liga_original.lower() in deportes_excepcion:
        return liga_original
    
    if ' vs ' not in equipos_texto:
        return liga_original if liga_original else 'Evento Deportivo'
    
    partes = equipos_texto.split(' vs ')
    if len(partes) != 2:
        return liga_original if liga_original else 'Evento Deportivo'
    
    nombre_equipo1 = partes[0].strip()
    nombre_equipo2 = partes[1].strip()
    norm_equipo1 = normalizar_texto(nombre_equipo1)
    norm_equipo2 = normalizar_texto(nombre_equipo2)
    
    equipos_encontrados = []
    
    for slug, team in TEAMS_DB.items():
        team_name = team.get('name', '')
        aliases = team.get('aliases', [])
        sport = team.get('sport', 'football')
        league = team.get('league', '')
        country = team.get('country', '')
        
        if sport != 'football' or not league:
            continue
        
        team_name_norm = normalizar_texto(team_name)
        
        if team_name_norm == norm_equipo1:
            equipos_encontrados.append(('equipo1', team_name_norm, country, league))
        else:
            for alias in aliases:
                alias_norm = normalizar_texto(alias)
                if alias_norm == norm_equipo1:
                    equipos_encontrados.append(('equipo1', alias_norm, country, league))
                    break
        
        if team_name_norm == norm_equipo2:
            equipos_encontrados.append(('equipo2', team_name_norm, country, league))
        else:
            for alias in aliases:
                alias_norm = normalizar_texto(alias)
                if alias_norm == norm_equipo2:
                    equipos_encontrados.append(('equipo2', alias_norm, country, league))
                    break
    
    encontro_equipo1 = any(e[0] == 'equipo1' for e in equipos_encontrados)
    encontro_equipo2 = any(e[0] == 'equipo2' for e in equipos_encontrados)
    
    if not (encontro_equipo1 and encontro_equipo2):
        return liga_original if liga_original else 'Evento Deportivo'
    
    if liga_original:
        equipos_en_liga_original = 0
        for e in equipos_encontrados:
            if e[3] == liga_original:
                equipos_en_liga_original += 1
        if equipos_en_liga_original == 2:
            return liga_original
    
    ligas_equipo1 = set([e[3] for e in equipos_encontrados if e[0] == 'equipo1'])
    ligas_equipo2 = set([e[3] for e in equipos_encontrados if e[0] == 'equipo2'])
    
    ligas_comunes = ligas_equipo1 & ligas_equipo2
    
    if ligas_comunes:
        if liga_original in ligas_comunes:
            return liga_original
        return list(ligas_comunes)[0]
    
    paises_equipo1 = set([e[2] for e in equipos_encontrados if e[0] == 'equipo1' and e[2]])
    paises_equipo2 = set([e[2] for e in equipos_encontrados if e[0] == 'equipo2' and e[2]])
    
    if paises_equipo1 and paises_equipo2 and paises_equipo1 == paises_equipo2:
        return liga_original if liga_original else 'Torneo Nacional'
    
    return liga_original if liga_original else 'Evento Deportivo'

def limpiar_saltos_linea(texto):
    """Elimina saltos de línea y espacios extras de un texto"""
    if not texto:
        return texto
    texto = texto.replace('\n', ' ').replace('\r', ' ')
    texto = re.sub(r'\s+', ' ', texto)
    return texto.strip()

# ============================================
# DETECCIÓN Y CONVERSIÓN DE HORAS
# ============================================

def detectar_tipo_hora(hora_str):
    if not hora_str:
        return 'desconocido'
    if hora_str.endswith('Z'):
        return 'utc'
    if 'T' in hora_str and not hora_str.endswith('Z'):
        return 'local'
    if ':' in hora_str and len(hora_str) <= 8:
        return 'local'
    return 'desconocido'

def convertir_local_a_utc(hora_str, fecha_referencia=None):
    if not hora_str:
        return None
    
    try:
        if 'T' in hora_str:
            hora_limpia = hora_str.replace('Z', '').replace('T', ' ')
        else:
            hora_limpia = hora_str
        
        if ':' in hora_limpia and len(hora_limpia) <= 8:
            if fecha_referencia:
                fecha_str = fecha_referencia.strftime('%Y-%m-%d')
            else:
                fecha_str = datetime.now().strftime('%Y-%m-%d')
            hora_completa = f"{fecha_str} {hora_limpia}"
        else:
            hora_completa = hora_limpia
        
        formatos = [
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%d %H:%M',
            '%Y-%m-%dT%H:%M:%S',
            '%Y-%m-%dT%H:%M'
        ]
        
        local_dt = None
        for fmt in formatos:
            try:
                local_dt = datetime.strptime(hora_completa, fmt)
                break
            except:
                continue
        
        if not local_dt:
            return hora_str
        
        utc_dt = local_dt + timedelta(hours=5)
        return utc_dt.strftime('%Y-%m-%dT%H:%M:%SZ')
    
    except Exception as e:
        print(f"  ⚠️ Error convirtiendo {hora_str}: {e}")
        return hora_str

def formatear_utc(hora_str):
    if not hora_str:
        return None
    
    try:
        if ' ' in hora_str:
            hora_str = hora_str.replace(' ', 'T')
        if not hora_str.endswith('Z'):
            hora_str = hora_str + 'Z'
        return hora_str
    except:
        return hora_str

def procesar_hora_segun_fuente(hora_str, fuente, fecha_ref=None):
    if not hora_str:
        return None
    
    if fuente == 'github':
        return formatear_utc(hora_str)
    
    if fuente == 'pltvhd':
        tipo = detectar_tipo_hora(hora_str)
        if tipo == 'utc':
            return formatear_utc(hora_str)
        else:
            return convertir_local_a_utc(hora_str, fecha_ref)
    
    return hora_str

# ============================================
# DECODIFICACIÓN DE URLs EMBED (Base64)
# ============================================

def decodificar_url_embed(embed_iframe):
    if not embed_iframe:
        return None
    
    match = re.search(r'[?&]r=([^&]+)', embed_iframe)
    if not match:
        return embed_iframe
    
    base64_string = match.group(1)
    
    try:
        decoded_bytes = base64.b64decode(base64_string)
        decoded_url = decoded_bytes.decode('utf-8')
        return decoded_url
    except Exception as e:
        print(f"  ⚠️ Error decodificando URL embed: {e}")
        return embed_iframe

# ============================================
# MAPEO DE LIGAS A PAÍSES (para logos)
# ============================================
TOURNAMENT_TO_COUNTRY = {
    'LaLiga': 'spain', 'LaLiga 2:': 'spain', 'LaLiga SmartBank': 'spain',
    'Bundesliga': 'germany', 'Bundesliga 2': 'germany', 'DFB Pokal': 'germany',
    'Premier League': 'england', 'Championship': 'england',
    'Eredivisie': 'netherlands',
    'Serie A': 'italy', 'Serie A:': 'italy',
    'Ligue 1': 'france', 'Ligue 2': 'france',
    'Copa de Portugal': 'portugal', 'Taça de Portugal': 'portugal', 'Primeira Liga': 'portugal',
    'Liga1': 'peru', 'Primera Division': 'peru',
    'Liga MX': 'mexico', 'Liga de Expansión MX': 'mexico', 'Liga MX Femenil': 'mexico',
    'Copa do Brasil': 'brazil', 'Brasilerao': 'brazil', 'Brasileirao Serie B' : 'brazil',
    'Brasileirão': 'brazil', '2. Bundesliga': 'germany',
    'Liga Profesional': 'argentina', 'Primera División': 'argentina', 'Futbol Argentino': 'argentina',
    'Liga BetPlay': 'colombia', 'Copa colombia': 'colombia', 'Primera A': 'colombia',
    'Liga de Primera': 'chile', 'Futbol Chileno': 'chile',
    'Liga Pro': 'ecuador',
    'Turkish Cup': 'turkey', 'Süper Lig': 'turkey',
    'Pro League': 'arabia', 'Saudi Pro League': 'arabia',
    'Primera División': 'bolivia',
    'Primera División Uruguay': 'uruguay', 'Liga Uruguaya': 'uruguay','Liga AUF Uruguaya': 'uruguay',
    'Torneo Apertura Uruguay': 'uruguay','Torneo Clausura Uruguay': 'uruguay',
    'Champions League': 'champions', 'Champions': 'champions', 'UEFA Champions League': 'champions',
    'UEFA Europa League': 'europaleague', 'UEFA Conference League': 'conference',
    'MLS': 'usa', 'MLB': 'mlb', 'NBA': 'nba','WNBA': 'nba','WWE': 'wwe','UFC': 'ufc','Boxing': 'box',
    'Copa del Mundo': 'Copa del Mundo',
    'NFL': 'nfl','NHL': 'nhl','Formula 1': 'f1', 'Tenis': 'tenis', 'default': 'evento deportivo'
}

COUNTRY_LOGO = {
    'spain': 'img/es.png', 'germany': 'img/de.png', 'netherlands': 'img/nl.png',
    'portugal': 'img/pt.png', 'peru': 'img/pe.png', 'brazil': 'img/br.png',
    'argentina': 'img/ar.png', 'colombia': 'img/col.png', 'chile': 'img/cl.png',
    'ecuador': 'img/ec.png', 'turkey': 'img/tr.png', 'usa': 'img/usa.png', 
    'arabia': 'img/sa.png', 'paraguay': 'img/py.png', 'uruguay': 'img/uy.png',
    'mexico': 'img/mx.png', 'bolivia': 'img/bo.png', 'nba': 'img/nba.png', 
    'italy': 'img/it.png', 'france': 'img/fr.png', 'england': 'img/en.png',
    'mlb': 'img/mlb.png', 'wwe': 'img/wwe.png', 'champions':'img/champions.png', 
    'europaleague': 'img/europa_league.png', 'conference': 'img/conference_league.png',
    'sudamericana':'img/sud.png', 'libertadores':'img/lib.png', 
    'f1': 'img/formula1.png', 'ufc': 'img/ufc.png', 'box': 'img/box.png',
    'nhl': 'img/nhl.png', 'nfl': 'img/nfl.png', 'Copa del Mundo': 'img/world_cup.png', 'default': 'img/default.png'
}

# ============================================
# FUNCIONES COMUNES
# ============================================

def get_logo(liga, country_from_source=None):
    liga_lower = liga.lower()
    
    if liga_lower == 'evento deportivo':
        return '🏆'
    
    if 'champions league' in liga_lower or liga_lower == 'champions':
        return COUNTRY_LOGO['champions']
    
    if 'libertadores' in liga_lower or 'copa libertadores' in liga_lower:
        return COUNTRY_LOGO['libertadores']
    
    if 'sudamericana' in liga_lower or 'copa sudamericana' in liga_lower:
        return COUNTRY_LOGO['sudamericana']
    
    if 'formula 1' in liga_lower or liga_lower == 'f1':
        return COUNTRY_LOGO['f1']
    
    if country_from_source and country_from_source.lower() in COUNTRY_LOGO:
        return COUNTRY_LOGO[country_from_source.lower()]
    
    for key, country in TOURNAMENT_TO_COUNTRY.items():
        if key.lower() == liga_lower:
            return COUNTRY_LOGO.get(country, COUNTRY_LOGO['default'])
    
    for key, country in TOURNAMENT_TO_COUNTRY.items():
        if key.lower() in liga_lower or liga_lower in key.lower():
            return COUNTRY_LOGO.get(country, COUNTRY_LOGO['default'])
    
    return COUNTRY_LOGO['default']

def fetch_json(url):
    try:
        with urllib.request.urlopen(url, timeout=15) as response:
            return json.loads(response.read().decode('utf-8'))
    except Exception as e:
        print(f"  ⚠️ Error en {url}: {e}")
        return None

# ============================================
# PROCESADORES DE CADA FUENTE
# ============================================

def process_github_source(data):
    matches = []
    if not data:
        return matches
    
    if isinstance(data, list):
        for event in data:
            if 'title' not in event:
                continue
            equipos = event['title']
            liga = event.get('category', 'MLB')
            
            equipos = limpiar_saltos_linea(equipos)
            liga = limpiar_saltos_linea(liga)
            
            liga_nueva, sport, nombre_normalizado = detectar_evento_motor(equipos, liga)
            if nombre_normalizado:
                equipos = nombre_normalizado
                liga = liga_nueva
            else:
                liga_detectada = detectar_liga_por_equipo(equipos, liga)
                if liga_detectada != liga:
                    print(f"  🔍 Liga corregida: {liga} → {liga_detectada} ({equipos[:50]})")
                    liga = liga_detectada
            
            hora_raw = event.get('time', '')
            if hora_raw:
                hora_utc = hora_raw.replace(' UTC', 'Z').replace(' ', 'T')
            else:
                hora_utc = ''
            
            logo = get_logo(liga)
            matches.append({
                'hora_utc': hora_utc,
                'logo': logo,
                'liga': liga,
                'equipos': equipos,
                'status': 'pronto',
                'canales': [{'nombre': event.get('channel', 'Canal'), 'url': event.get('link', ''), 'calidad': 'HD'}],
                'fuente': 'github'
            })
        return matches
    
    if 'events' in data:
        for event in data['events']:
            if 'title' not in event:
                continue
            equipos = event['title']
            liga = event.get('category', 'MLB')
            
            equipos = limpiar_saltos_linea(equipos)
            liga = limpiar_saltos_linea(liga)
            
            liga_nueva, sport, nombre_normalizado = detectar_evento_motor(equipos, liga)
            if nombre_normalizado:
                equipos = nombre_normalizado
                liga = liga_nueva
            else:
                liga_detectada = detectar_liga_por_equipo(equipos, liga)
                if liga_detectada != liga:
                    print(f"  🔍 Liga corregida: {liga} → {liga_detectada} ({equipos[:50]})")
                    liga = liga_detectada
            
            hora_raw = event.get('time_utc', '')
            hora_utc = procesar_hora_segun_fuente(hora_raw, 'github')
            logo = get_logo(liga)
            matches.append({
                'hora_utc': hora_utc,
                'logo': logo,
                'liga': liga,
                'equipos': equipos,
                'status': 'pronto',
                'canales': [{'nombre': event.get('channel', 'Canal'), 'url': event.get('link', ''), 'calidad': 'HD'}],
                'fuente': 'github'
            })
    
    return matches

def process_pltvhd_source(data):
    """Procesador para PLTVHD con filtro de Rugby y decodificación de URLs"""
    matches = []
    if not data:
        return matches
    
    PALABRAS_RUGBY = [
        'rugby', 'rugbi', 'six nations', 'seis naciones', 'super rugby',
        'top 14', 'premiership rugby', 'champions cup', 'challenge cup',
        'uruguay rugby', 'chile rugby', 'argentina rugby', 'brasil rugby',
        'rugby championship', 'the rugby championship', 'CFL', 'test match'
    ]
    
    today = datetime.now()
    events_list = data.get('data', []) if isinstance(data, dict) else []
    eventos_filtrados = 0
    
    for item in events_list:
        attrs = item.get('attributes', {})
        diary_description = attrs.get('diary_description', '')
        
        diary_description = limpiar_saltos_linea(diary_description)
        
        desc_lower = diary_description.lower()
        es_rugby = False
        for palabra in PALABRAS_RUGBY:
            if palabra in desc_lower:
                es_rugby = True
                eventos_filtrados += 1
                print(f"  🏉 Filtrado Rugby: {diary_description[:60]}...")
                break
        if es_rugby:
            continue
        
        liga = ''
        equipos = ''
        
        if ': ' in diary_description:
            liga, equipos = diary_description.split(': ', 1)
        else:
            equipos = diary_description
            texto_inferior = diary_description.lower()
            
            if 'nba' in texto_inferior:
                liga = 'NBA'
            elif 'mlb' in texto_inferior:
                liga = 'MLB'
            elif 'wnba' in texto_inferior:
                liga = 'WNBA'
            elif 'nfl' in texto_inferior:
                liga = 'NFL'
            elif 'nhl' in texto_inferior:
                liga = 'NHL'
            elif 'wwe' in texto_inferior:
                liga = 'WWE'
            elif 'ufc' in texto_inferior:
                liga = 'UFC'
            elif 'boxing' in texto_inferior or 'boxeo' in texto_inferior:
                liga = 'Boxeo'
            elif 'futbol' in texto_inferior or 'fútbol' in texto_inferior:
                liga = 'Fútbol'
            else:
                liga = 'Deportes'
        
        liga = limpiar_saltos_linea(liga)
        equipos = limpiar_saltos_linea(equipos)
        
        liga_nueva, sport, nombre_normalizado = detectar_evento_motor(equipos, liga)
        if nombre_normalizado:
            equipos = nombre_normalizado
            liga = liga_nueva
            print(f"  🏎️ F1 normalizado: {nombre_normalizado}")
        else:
            if liga not in ['NBA', 'WNBA', 'MLB', 'NFL', 'NHL', 'WWE', 'UFC', 'Boxeo', 'Formula 1', 'F1', 'Formula 2', 'F2']:
                liga_detectada = detectar_liga_por_equipo(equipos, liga)
                if liga_detectada != liga:
                    print(f"  🔍 Liga corregida: {liga} → {liga_detectada} ({equipos[:50]})")
                    liga = liga_detectada
        
        date_diary = attrs.get('date_diary', '')
        diary_hour = attrs.get('diary_hour', '')
        if date_diary and diary_hour:
            hora_local = f"{date_diary} {diary_hour[:5]}"
        else:
            hora_local = ''
        hora_utc = procesar_hora_segun_fuente(hora_local, 'pltvhd', today)
        
        canales = []
        embeds = attrs.get('embeds', {})
        embeds_data = embeds.get('data', []) if isinstance(embeds, dict) else []
        
        for embed in embeds_data:
            embed_attrs = embed.get('attributes', {})
            embed_name = embed_attrs.get('embed_name', 'Canal')
            embed_iframe = embed_attrs.get('embed_iframe', '')
            
            if embed_iframe:
                if embed_iframe.startswith('/'):
                    full_url = f"https://pltvhd.com{embed_iframe}"
                else:
                    full_url = embed_iframe
                real_url = decodificar_url_embed(full_url)
                if real_url:
                    canales.append({
                        'nombre': embed_name,
                        'url': real_url,
                        'calidad': 'HD'
                    })
        
        if not canales:
            channels = attrs.get('channels', {})
            channels_data = channels.get('data', []) if isinstance(channels, dict) else []
            for channel in channels_data:
                channel_attrs = channel.get('attributes', {})
                channel_name = channel_attrs.get('channel_name', 'Canal')
                channel_url = channel_attrs.get('channel_url', '')
                canales.append({
                    'nombre': channel_name,
                    'url': channel_url,
                    'calidad': 'HD'
                })
        
        if not canales:
            canales = [{'nombre': 'Canal 1', 'url': '#', 'calidad': 'HD'}]
        
        logo = get_logo(liga)
        
        matches.append({
            'hora_utc': hora_utc,
            'logo': logo,
            'liga': liga,
            'equipos': equipos,
            'status': 'pronto',
            'canales': canales,
            'fuente': 'pltvhd'
        })
    
    if eventos_filtrados > 0:
        print(f"  🏉 TOTAL: {eventos_filtrados} eventos de Rugby filtrados y descartados")
    
    return matches

def process_eventos_source(data):
    """Procesador para la nueva fuente de eventos (lista de eventos)"""
    matches = []
    if not data:
        return matches
    
    # La nueva estructura es una lista directamente
    if not isinstance(data, list):
        print("  ⚠️ Formato de datos no esperado (se esperaba lista)")
        return matches
    
    for event in data:
        title = event.get('title', '')
        time_str = event.get('time', '')
        category = event.get('category', 'Deportes')
        status = event.get('status', 'pronto')
        link = event.get('link', '')
        language = event.get('language', '')
        
        if not title or not link:
            continue
        
        # Limpiar título
        title = limpiar_saltos_linea(title)
        category = limpiar_saltos_linea(category)
        
        # Intentar extraer liga y equipos del título
        # Ejemplo: "Copa Mundial de la FIFA: Noruega vs Senegal"
        liga = ''
        equipos = title
        
        if ': ' in title:
            liga, equipos = title.split(': ', 1)
            liga = liga.strip()
            equipos = equipos.strip()
        else:
            # Si no tiene ":", intentar detectar liga por palabras clave
            liga = category if category and category != 'Other' else 'Evento Deportivo'
        
        # Si la liga es "Other", usar un nombre genérico
        if liga == 'Other' or not liga:
            liga = 'Evento Deportivo'
        
        # Procesar hora
        hora_utc = None
        if time_str:
            hora_utc = procesar_hora_eventos(time_str)
        
        # Normalizar equipos (si hay "vs")
        if ' vs ' in equipos:
            partes = equipos.split(' vs ')
            if len(partes) == 2:
                eq1 = partes[0].strip()
                eq2 = partes[1].strip()
                # Intentar detectar liga por equipos (solo para fútbol)
                liga_detectada = detectar_liga_por_equipo(equipos, liga)
                if liga_detectada != liga:
                    liga = liga_detectada
                # Ordenar alfabéticamente
                if eq1.lower() > eq2.lower():
                    equipos = f"{eq2} vs {eq1}"
                else:
                    equipos = f"{eq1} vs {eq2}"
        
        logo = get_logo(liga)
        
        matches.append({
            'hora_utc': hora_utc,
            'logo': logo,
            'liga': liga,
            'equipos': equipos,
            'status': status,
            'canales': [{
                'nombre': 'Stream',
                'url': link,
                'calidad': 'HD'
            }],
            'fuente': 'eventos'
        })
    
    return matches

def procesar_hora_eventos(hora_str):
    if not hora_str:
        return None
    
    try:
        hoy = datetime.now()
        horas, minutos = map(int, hora_str.split(':'))
        local_dt = hoy.replace(hour=horas, minute=minutos, second=0, microsecond=0)
        utc_dt = local_dt + timedelta(hours=5)
        return utc_dt.strftime('%Y-%m-%dT%H:%M:%SZ')
    except Exception as e:
        print(f"  ⚠️ Error procesando hora {hora_str}: {e}")
        return None

def unificar_por_equipos(all_matches):
    unificados = {}
    
    for m in all_matches:
        equipos = m['equipos']
        hora = m.get('hora_utc', '')
        liga = m.get('liga', '')
        logo = m.get('logo', '')
        
        equipos_norm = normalizar_texto(equipos)
        equipos_norm = re.sub(r'\s+', ' ', equipos_norm).strip()
        
        key = equipos_norm
        
        if key not in unificados:
            unificados[key] = m.copy()
            unificados[key]['equipos'] = equipos_norm
            unificados[key]['equipos_original'] = equipos
        else:
            existing = unificados[key]
            
            ligas_genericas = ['Soccer', 'Deportes', 'Evento Deportivo', 'Fútbol']
            if existing['liga'] in ligas_genericas and liga not in ligas_genericas:
                existing['liga'] = liga
                existing['logo'] = logo
            
            for canal in m.get('canales', []):
                url = canal.get('url', '')
                if url and not any(c.get('url') == url for c in existing['canales']):
                    existing['canales'].append(canal)
            
            if hora and (not existing.get('hora_utc') or hora < existing['hora_utc']):
                existing['hora_utc'] = hora
    
    return list(unificados.values())

# ============================================
# ORQUESTADOR PRINCIPAL
# ============================================

def run_scraper():
    print('\n🏆 SCRAPER MULTIFUENTE (TODO a UTC con detección)\n')
    all_matches = []
    processors = [
        ('PLTVHD', SOURCES['pltvhd'], process_pltvhd_source),
        ('GitHub (MLB)', SOURCES['github'], process_github_source),
        ('GitHub2 (Clean)', SOURCES['github2'], process_github_source),
        ('GitLab Eventos', SOURCES['eventos'], process_eventos_source)
    ]
    
    for name, url, processor in processors:
        print(f'📡 {name}...')
        data = fetch_json(url)
        if data:
            matches = processor(data)
            print(f'   ✅ {len(matches)} partidos')
            all_matches.extend(matches)
        else:
            print(f'   ❌ Sin datos')
    
    final_matches = unificar_por_equipos(all_matches)
    final_matches.sort(key=lambda x: x.get('hora_utc', ''))
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(final_matches, f, indent=2, ensure_ascii=False)
    
    print(f'\n💾 Guardados {len(final_matches)} partidos únicos en {OUTPUT_FILE}')
    
    ligas = defaultdict(int)
    for m in final_matches:
        ligas[m['liga']] += 1
    print('\n📋 Resumen por liga:')
    for liga, count in sorted(ligas.items(), key=lambda x: x[1], reverse=True)[:15]:
        print(f'   - {liga}: {count} partidos')
    if len(ligas) > 15:
        print(f'   ... y {len(ligas)-15} ligas más')

if __name__ == '__main__':
    run_scraper()