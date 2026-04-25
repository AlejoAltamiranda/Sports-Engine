import json
import urllib.request
import re
from datetime import datetime, timedelta
from collections import defaultdict

# ============================================
# CONFIGURACIÓN GLOBAL
# ============================================
SOURCES = {
    'github': 'https://raw.githubusercontent.com/AlejoAltamiranda/stream/refs/heads/main/events.json',
    'elcanal': 'https://elcanaldeportivo.com/partidos.json',
    'streamtp': 'https://streamtpnew.com/eventos.json',
    'cdn': 'https://api.cdnlivetv.tv/api/v1/events/sports/soccer/?user=cdnlivetv&plan=free'
}
OUTPUT_FILE = 'scraper_output.json'

# ============================================
# DETECCIÓN Y CONVERSIÓN DE HORAS
# ============================================

def detectar_tipo_hora(hora_str):
    """
    Detecta si una hora es UTC o Local
    UTC: termina con Z o tiene formato ISO con Z
    Local: formato ISO sin Z, o solo hora (ej: "16:00")
    """
    if not hora_str:
        return 'desconocido'
    
    # Si tiene Z al final, es UTC
    if hora_str.endswith('Z'):
        return 'utc'
    
    # Si tiene T pero no Z, es local
    if 'T' in hora_str and not hora_str.endswith('Z'):
        return 'local'
    
    # Si es solo hora (ej: "16:00" o "14:30"), es local
    if ':' in hora_str and len(hora_str) <= 8:
        return 'local'
    
    return 'desconocido'

def convertir_local_a_utc(hora_str, fecha_referencia=None):
    """Convierte hora LOCAL de Colombia (UTC-5) a UTC"""
    if not hora_str:
        return None
    
    try:
        # Limpiar formato
        if 'T' in hora_str:
            hora_limpia = hora_str.replace('Z', '').replace('T', ' ')
        else:
            hora_limpia = hora_str
        
        # Añadir fecha si solo es hora
        if ':' in hora_limpia and len(hora_limpia) <= 8:
            if fecha_referencia:
                fecha_str = fecha_referencia.strftime('%Y-%m-%d')
            else:
                fecha_str = datetime.now().strftime('%Y-%m-%d')
            hora_completa = f"{fecha_str} {hora_limpia}"
        else:
            hora_completa = hora_limpia
        
        # Intentar diferentes formatos
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
        
        # Colombia UTC-5 → sumar 5 horas
        utc_dt = local_dt + timedelta(hours=5)
        return utc_dt.strftime('%Y-%m-%dT%H:%M:%SZ')
    
    except Exception as e:
        print(f"  ⚠️ Error convirtiendo {hora_str}: {e}")
        return hora_str

def formatear_utc(hora_str):
    """Formatea una hora que ya está en UTC"""
    if not hora_str:
        return None
    
    try:
        # Si tiene espacio, reemplazar por T
        if ' ' in hora_str:
            hora_str = hora_str.replace(' ', 'T')
        
        # Si no tiene Z, agregarla
        if not hora_str.endswith('Z'):
            hora_str = hora_str + 'Z'
        
        return hora_str
    except:
        return hora_str

def procesar_hora_segun_fuente(hora_str, fuente, fecha_ref=None):
    """
    Procesa la hora según la fuente con detección automática
    - cdn, github: siempre UTC → formatear
    - elcanal, streamtp: detectar si es UTC o LOCAL → actuar según corresponda
    """
    if not hora_str:
        return None
    
    # Fuentes que siempre son UTC (no necesitan detección)
    if fuente in ['cdn', 'github']:
        return formatear_utc(hora_str)
    
    # Fuentes que pueden ser UTC o LOCAL (detección automática)
    if fuente in ['elcanal', 'streamtp']:
        tipo = detectar_tipo_hora(hora_str)
        if tipo == 'utc':
            print(f"  🔍 {fuente}: UTC detectado → {hora_str}")
            return formatear_utc(hora_str)
        else:
            print(f"  🔍 {fuente}: LOCAL detectado → {hora_str} (convirtiendo a UTC)")
            return convertir_local_a_utc(hora_str, fecha_ref)
    
    return hora_str

# ============================================
# MAPEO DE URLs (elcanaldeportivo)
# ============================================
URL_MAPPING = {
    "/ver/dsports2.php": "https://elcanaldeportivo.com/ver/dsports2.php",
    "/ver/directvsportsplus.php": "https://elcanaldeportivo.com/ver/directvsportsplus.php",
    "/ver/espn2.php": "https://elcanaldeportivo.com/ver/espn2.php",
    "/ver/espn4.php": "https://elcanaldeportivo.com/ver/espn4.php",
    "/ver/tntsportspremium.php": "https://elcanaldeportivo.com/ver/tntsportspremium.php",
    "/ver/winsportsmas.php": "https://elcanaldeportivo.com/ver/winsportsmas.php",
    "/ver/elcanaldelfutbol.php": "https://elcanaldeportivo.com/ver/elcanaldelfutbol.php",
    "/ver/liga1maxpe.php": "https://elcanaldeportivo.com/ver/liga1maxpe.php",
    "/ver/espnpremium.php": "https://elcanaldeportivo.com/ver/espnpremium.php",
    "/ver/espn.php": "https://elcanaldeportivo.com/ver/espn.php",
    "/ver/espn-sharecast.php": "https://elcanaldeportivo.com/ver/espn-sharecast.php",
    "default": "https://elcanaldeportivo.com"
}

def fix_elcanal_url(url):
    if not url:
        return url
    if url.startswith('http://') or url.startswith('https://'):
        return url
    if url in URL_MAPPING:
        return URL_MAPPING[url]
    return f"https://elcanaldeportivo.com{url}"

# ============================================
# MAPEO DE LIGAS A PAÍSES (para logos)
# ============================================
TOURNAMENT_TO_COUNTRY = {
    'La Liga': 'spain', 'LaLiga': 'spain', 'LaLiga 2:': 'spain',
    'Copa Alemania': 'germany', 'DFB Pokal': 'germany',
    'Eredivisie': 'netherlands',
    'Copa de Portugal': 'portugal', 'Taça de Portugal': 'portugal', 'Primeira Liga': 'portugal',
    'Liga 1': 'peru', 'Primera Division': 'peru',
    'Copa do Brasil': 'brazil', 'Brasileirão': 'brazil',
    'Liga Profesional': 'argentina', 'Primera División': 'argentina', 'Futbol Argentino': 'argentina',
    'Liga BetPlay': 'colombia', 'Liga Betplay': 'colombia', 'Primera A': 'colombia',
    'Liga de Primera': 'chile', 'Futbol Chileno': 'chile',
    'Liga Pro': 'ecuador',
    'Turkish Cup': 'turkey',
    'Pro League': 'arabia',
    'Primera División Uruguay': 'uruguay', 'Liga Uruguaya': 'uruguay','Uruguayan Primera División': 'uruguay',
    'Torneo Apertura Uruguay': 'uruguay','Torneo Clausura Uruguay': 'uruguay',
    'Champions League': 'champions', 'Champions': 'champions', 'UEFA Champions League': 'champions',
    'mls': 'estados unidos', 'MLS': 'usa', 'mls': 'usa',
    'MLB': 'mlb',
    'NBA': 'nba',
    'WWE': 'wwe',
    'UFC': 'ufc'
}

COUNTRY_LOGO = {
    'spain': 'img/es.png', 'germany': 'img/de.png', 'netherlands': 'img/nl.png',
    'portugal': 'img/pt.png', 'peru': 'img/pe.png', 'brazil': 'img/br.png',
    'argentina': 'img/ar.png', 'colombia': 'img/col.png', 'chile': 'img/cl.png',
    'ecuador': 'img/ec.png', 'turkey': 'img/tr.png', 'usa': 'img/usa.png', 
    'arabia': 'img/sa.png', 'paraguay': 'img/py.png', 'uruguay': 'img/uy.png',
    'mexico': 'img/mx.png', 'nba': 'img/nba.png', 'mlb': 'img/mlb.png', 'wwe': 'img/wwe.png', 
    'champions':'img/champions.png', 'ufc': 'img/ufc.png', 'default': 'img/default.png'
}

# ============================================
# FUNCIONES COMUNES
# ============================================

def get_logo(liga, country_from_source=None):
    if country_from_source and country_from_source.lower() in COUNTRY_LOGO:
        return COUNTRY_LOGO[country_from_source.lower()]
    country = TOURNAMENT_TO_COUNTRY.get(liga, 'default')
    return COUNTRY_LOGO.get(country, COUNTRY_LOGO['default'])

def extract_channel_name(url):
    match = re.search(r'stream=([^&]+)', url)
    if match:
        name = match.group(1).replace('dsports', 'Dsports').replace('espn', 'ESPN')
        name = name.replace('premiere', 'Premiere').replace('fanatiz', 'Fanatiz')
        name = name.replace('disney', 'Disney+').replace('winplus', 'Win Sports+')
        name = re.sub(r'([a-z])(\d+)', r'\1 \2', name)
        return name.title()
    return 'Canal'

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
    
    # Nuevo formato: array directo
    if isinstance(data, list):
        for event in data:
            if 'title' not in event:
                continue
            equipos = event['title']
            liga = event.get('category', 'MLB')
            hora_raw = event.get('time', '')
            # Convertir "2026-04-24 22:40 UTC" a ISO
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
    
    # Formato antiguo: con objeto 'events'
    if 'events' in data:
        for event in data['events']:
            if 'title' not in event:
                continue
            equipos = event['title']
            liga = event.get('category', 'MLB')
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

def process_elcanal_source(data):
    matches = []
    if not data:
        return matches
    
    today = datetime.now()
    
    for item in data:
        if 'equipos' not in item:
            continue
        
        liga = item.get('liga', 'Fútbol').replace(':', '')
        hora_raw = item.get('hora_utc', '')
        hora_utc = procesar_hora_segun_fuente(hora_raw, 'elcanal', today)
        
        canales_fixed = []
        for ch in item.get('canales', []):
            original_url = ch.get('url', '')
            canales_fixed.append({
                'nombre': ch.get('nombre'),
                'url': fix_elcanal_url(original_url),
                'calidad': ch.get('calidad', '720p')
            })
        
        matches.append({
            'hora_utc': hora_utc,
            'logo': get_logo(liga),
            'liga': liga,
            'equipos': item['equipos'],
            'status': 'pronto',
            'canales': canales_fixed,
            'fuente': 'elcanal'
        })
    
    return matches

def process_streamtp_source(data):
    matches, grouped = [], defaultdict(lambda: {'channels': [], 'status': ''})
    if not data:
        return matches
    
    today = datetime.now()
    
    for item in data:
        key = f"{item.get('title')}|{item.get('time')}"
        grouped[key]['channels'].append({
            'nombre': extract_channel_name(item.get('link', '')),
            'url': item.get('link'),
            'calidad': '720p'
        })
        grouped[key]['status'] = item.get('status', '')
    
    for key, info in grouped.items():
        title, time_str = key.split('|')
        if ': ' in title:
            liga, equipos = title.split(': ', 1)
        else:
            liga, equipos = 'Fútbol', title
        
        hora_utc = procesar_hora_segun_fuente(time_str, 'streamtp', today)
        
        matches.append({
            'hora_utc': hora_utc,
            'logo': get_logo(liga),
            'liga': liga,
            'equipos': equipos,
            'status': info['status'],
            'canales': info['channels'],
            'fuente': 'streamtp'
        })
    return matches

def process_cdn_source(data):
    matches = []
    if not data:
        return matches
    events = data.get('cdn-live-tv', {}).get('Soccer', [])
    for event in events:
        home, away = event.get('homeTeam'), event.get('awayTeam')
        if not home or not away:
            continue
        equipos = f"{home} vs {away}"
        liga = event.get('tournament', 'Fútbol')
        hora_raw = event.get('start', '')
        hora_utc = procesar_hora_segun_fuente(hora_raw, 'cdn')
        logo = get_logo(liga, event.get('country'))
        canales = [{'nombre': ch.get('channel_name', 'Canal'), 'url': ch.get('url', ''), 'calidad': 'HD'} for ch in event.get('channels', [])]
        matches.append({
            'hora_utc': hora_utc,
            'logo': logo,
            'liga': liga,
            'equipos': equipos,
            'status': event.get('status', 'pronto'),
            'canales': canales,
            'fuente': 'cdn'
        })
    return matches

# ============================================
# ORQUESTADOR PRINCIPAL
# ============================================

def run_scraper():
    print('\n🏆 SCRAPER MULTIFUENTE (TODO a UTC con detección)\n')
    all_matches = []
    processors = [
        ('GitHub (MLB)', SOURCES['github'], process_github_source),
        ('ElCanalDeportivo', SOURCES['elcanal'], process_elcanal_source),
        ('StreamTPNew', SOURCES['streamtp'], process_streamtp_source),
        ('CDN Live TV', SOURCES['cdn'], process_cdn_source)
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
    
    # UNIFICAR PARTIDOS DUPLICADOS
    unique = {}
    for m in all_matches:
        if not m.get('hora_utc'):
            continue
        key = f"{m['equipos']}|{m['hora_utc'][:16]}"
        if key not in unique:
            unique[key] = m
        else:
            existing = unique[key]
            existing['canales'].extend(m['canales'])
            if existing['logo'] == COUNTRY_LOGO['default'] and m['logo'] != COUNTRY_LOGO['default']:
                existing['logo'] = m['logo']
    
    final_matches = list(unique.values())
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
