import json
import re
from datetime import datetime, timedelta
from collections import defaultdict

# ============================================
# DURACIÓN DE PARTIDOS POR DEPORTE (en minutos)
# ============================================

SPORT_DURATION = {
    'football': 140,
    'nba': 195,
    'mlb': 195,
    'nfl': 195,
    'ufc': 300,
    'wwe': 180,
    'box': 300,
    'nhl': 180,
    'tenis': 180,
    'default': 140
}

CONFIG = {
    'input_file': 'scraper_output.json',
    'output_file': 'matches.json'
}

# ============================================
# LIGAS EXCLUIDAS (NO SE MOSTRARÁN)
# ============================================
EXCLUDED_LEAGUES = [
    'Rugby',
    'CFL',
]

EXCLUDED_KEYWORDS = []

# ============================================
# CARGAR BASE DE DATOS DE EQUIPOS NBA
# ============================================

def load_nba_teams():
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

# ============================================
# CARGAR BASE DE DATOS DE EQUIPOS MLB
# ============================================

def load_mlb_teams():
    mlb_teams = []
    mlb_aliases = {}
    
    try:
        with open('mlb_teams.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, dict) and 'mlb_teams' in data:
                for team in data['mlb_teams']:
                    nombre = team.get('name', '')
                    if nombre:
                        mlb_teams.append(nombre.lower())
                        aliases = team.get('aliases', [])
                        for alias in aliases:
                            mlb_aliases[alias.lower()] = nombre
        print(f"✅ Cargados {len(mlb_teams)} equipos MLB con {len(mlb_aliases)} alias")
    except FileNotFoundError:
        print("⚠️ No se encuentra mlb_teams.json")
    except Exception as e:
        print(f"⚠️ Error cargando mlb_teams.json: {e}")
    
    return mlb_teams, mlb_aliases

MLB_TEAMS, MLB_ALIASES = load_mlb_teams()

# ============================================
# CARGAR BASE DE DATOS DE EQUIPOS DE FÚTBOL
# ============================================

def load_football_teams():
    """Carga la base de datos de equipos de fútbol desde teams.json"""
    football_teams = {}
    
    try:
        with open('teams.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, dict):
                football_teams = data
        print(f"✅ Cargados {len(football_teams)} equipos de fútbol desde teams.json")
    except FileNotFoundError:
        print("⚠️ No se encuentra teams.json - La normalización de fútbol no estará disponible")
    except Exception as e:
        print(f"⚠️ Error cargando teams.json: {e}")
    
    return football_teams

FOOTBALL_TEAMS = load_football_teams()

# ============================================
# NORMALIZAR TEXTO
# ============================================

def normalizar_texto(texto):
    if not texto:
        return texto
    
    texto = texto.lower()
    
    reemplazos = {
        'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u',
        'à': 'a', 'è': 'e', 'ì': 'i', 'ò': 'o', 'ù': 'u',
        'â': 'a', 'ê': 'e', 'î': 'i', 'ô': 'o', 'û': 'u',
        'ã': 'a', 'õ': 'o', 'ñ': 'n', 'ç': 'c',
        'ä': 'a', 'ë': 'e', 'ï': 'i', 'ö': 'o', 'ü': 'u'
    }
    
    for acentuado, sin_acento in reemplazos.items():
        texto = texto.replace(acentuado, sin_acento)
    
    texto = re.sub(r'[^a-z0-9\s-]', '', texto)
    
    return texto.strip()

# ============================================
# NORMALIZAR EQUIPOS DE FÚTBOL
# ============================================

def normalizar_equipo_football(nombre_equipo):
    """
    Normaliza un nombre de equipo usando la base de datos de fútbol.
    "new zealand" → "Nueva Zelanda"
    "egypt" → "Egipto"
    """
    if not nombre_equipo or not FOOTBALL_TEAMS:
        return nombre_equipo
    
    nombre_lower = normalizar_texto(nombre_equipo)
    
    for team_data in FOOTBALL_TEAMS.values():
        # Buscar por nombre oficial
        if normalizar_texto(team_data.get('name', '')) == nombre_lower:
            return team_data.get('name', nombre_equipo)
        # Buscar por alias
        for alias in team_data.get('aliases', []):
            if normalizar_texto(alias) == nombre_lower:
                return team_data.get('name', nombre_equipo)
    
    return nombre_equipo

def normalizar_partido_football(texto_equipos):
    """
    Normaliza ambos equipos en un texto 'Equipo1 vs Equipo2'
    "new zealand vs egypt" → "Nueva Zelanda vs Egipto"
    """
    if not texto_equipos or ' vs ' not in texto_equipos:
        return texto_equipos
    
    partes = texto_equipos.split(' vs ')
    if len(partes) != 2:
        return texto_equipos
    
    equipo1 = normalizar_equipo_football(partes[0].strip())
    equipo2 = normalizar_equipo_football(partes[1].strip())
    
    # Ordenar alfabéticamente
    if equipo1.lower() > equipo2.lower():
        return f"{equipo2} vs {equipo1}"
    return f"{equipo1} vs {equipo2}"

# ============================================
# EXTRAER SOLO NOMBRES DE EQUIPOS NBA
# ============================================

def extraer_solo_equipos(texto):
    if not texto or ' vs ' not in texto:
        return texto
    
    texto_lower = texto.lower()
    equipos_encontrados = []
    
    partes = texto_lower.split(' vs ')
    
    for parte in partes:
        parte_limpia = parte.strip()
        equipo_oficial = None
        
        if parte_limpia in NBA_ALIASES:
            equipo_oficial = NBA_ALIASES[parte_limpia]
        else:
            for alias, nombre in NBA_ALIASES.items():
                if alias in parte_limpia:
                    equipo_oficial = nombre
                    break
        
        if not equipo_oficial:
            for team in NBA_TEAMS:
                if team in parte_limpia:
                    equipo_oficial = ' '.join([w.capitalize() for w in team.split()])
                    break
        
        if equipo_oficial:
            equipos_encontrados.append(equipo_oficial)
        else:
            equipos_encontrados.append(parte_limpia.title())
    
    if len(equipos_encontrados) == 2:
        if equipos_encontrados[0].lower() > equipos_encontrados[1].lower():
            return f"{equipos_encontrados[1]} vs {equipos_encontrados[0]}"
        return f"{equipos_encontrados[0]} vs {equipos_encontrados[1]}"
    
    return texto

# ============================================
# EXTRAER SOLO NOMBRES DE EQUIPOS MLB
# ============================================

def extraer_solo_equipos_mlb(texto):
    if not texto or ' vs ' not in texto:
        return texto
    
    texto_lower = texto.lower()
    equipos_encontrados = []
    
    partes = texto_lower.split(' vs ')
    
    for parte in partes:
        parte_limpia = parte.strip()
        equipo_oficial = None
        
        if parte_limpia in MLB_ALIASES:
            equipo_oficial = MLB_ALIASES[parte_limpia]
        else:
            for alias, nombre in MLB_ALIASES.items():
                if alias in parte_limpia:
                    equipo_oficial = nombre
                    break
        
        if not equipo_oficial:
            for team in MLB_TEAMS:
                if team in parte_limpia:
                    equipo_oficial = ' '.join([w.capitalize() for w in team.split()])
                    break
        
        if equipo_oficial:
            equipos_encontrados.append(equipo_oficial)
        else:
            equipos_encontrados.append(parte_limpia.title())
    
    if len(equipos_encontrados) == 2:
        if equipos_encontrados[0].lower() > equipos_encontrados[1].lower():
            return f"{equipos_encontrados[1]} vs {equipos_encontrados[0]}"
        return f"{equipos_encontrados[0]} vs {equipos_encontrados[1]}"
    
    return texto

# ============================================
# NORMALIZAR EVENTO GENERAL (NHL, NFL, etc.)
# ============================================

def normalizar_evento_general(texto):
    if not texto:
        return texto
    
    texto_limpio = texto.lower()
    
    prefijos = [
        r'juego\s+#?\d*\s*[–-]\s*',
        r'game\s+#?\d*\s*[–-]\s*',
        r'partido\s+#?\d*\s*[–-]\s*',
        r'nhl\s*[–-]\s*',
        r'nfl\s*[–-]\s*',
        r'mlb\s*[–-]\s*',
        r'wnba\s*[–-]\s*',
        r'nba\s*[–-]\s*',
        r'ufc\s*[–-]\s*',
        r'box\s*[–-]\s*',
        r'boxeo\s*[–-]\s*',
        r'wwe\s*[–-]\s*',
        r'tenis\s*[–-]\s*',
        r'tennis\s*[–-]\s*',
    ]
    
    for prefijo in prefijos:
        texto_limpio = re.sub(prefijo, '', texto_limpio, flags=re.IGNORECASE)
    
    texto_limpio = re.sub(r'\s+', ' ', texto_limpio).strip()
    
    if ' vs ' in texto_limpio:
        partes = texto_limpio.split(' vs ')
        if len(partes) == 2:
            equipo1 = partes[0].strip()
            equipo2 = partes[1].strip()
            if equipo1 > equipo2:
                texto_limpio = f"{equipo2} vs {equipo1}"
    
    if texto_limpio:
        palabras = texto_limpio.split()
        texto_limpio = ' '.join([p.capitalize() for p in palabras])
    
    return texto_limpio

# ============================================
# LIMPIAR NOMBRE DE LIGA
# ============================================

def limpiar_nombre_liga(liga):
    if not liga:
        return liga
    
    separadores = [' – ', ' - ', ', ']
    for sep in separadores:
        if sep in liga:
            liga = liga.split(sep)[0]
            break
    
    return liga.strip()

# ============================================
# REORDENAR PREFIJO DE EVENTO
# ============================================

def reordenar_prefijo_evento(texto):
    if not texto:
        return texto
    
    patron = re.compile(
        r'(?:^|\s+)(Juego\s+#?\d*\s*[–-]|Game\s+#?\d*\s*[–-]|Partido\s+#?\d*\s*[–-])',
        re.IGNORECASE
    )
    
    match = patron.search(texto)
    if match:
        prefijo = match.group(1).strip()
        texto_limpio = patron.sub('', texto).strip()
        texto_limpio = re.sub(r'\s+', ' ', texto_limpio)
        return f"{prefijo} {texto_limpio}"
    
    return texto

# ============================================
# ELIMINAR "– (a confirmar)"
# ============================================

def limpiar_a_confirmar(texto):
    if not texto:
        return texto
    
    texto = re.sub(r'\s*[–-]\s*\(a confirmar\)', '', texto, flags=re.IGNORECASE)
    texto = re.sub(r'\s*\(a confirmar\)', '', texto, flags=re.IGNORECASE)
    texto = re.sub(r'\s+', ' ', texto).strip()
    
    return texto

# ============================================
# CORREGIR AMÉRICA POR LIGA
# ============================================

def corregir_america_por_liga(equipos_texto, liga):
    if not equipos_texto:
        return equipos_texto
    
    liga_lower = liga.lower() if liga else ''
    
    if 'concacaf' in liga_lower or 'liga mx' in liga_lower:
        equipos_texto = equipos_texto.replace('América de Cali', 'Club América')
        equipos_texto = equipos_texto.replace('America de Cali', 'Club América')
    
    return equipos_texto

# ============================================
# FUNCIÓN PARA VERIFICAR SI UNA LIGA DEBE SER EXCLUIDA
# ============================================

def is_league_excluded(liga):
    if not liga:
        return False
    
    liga_lower = liga.lower()
    
    for excluded in EXCLUDED_LEAGUES:
        if excluded.lower() == liga_lower:
            return True
    
    for keyword in EXCLUDED_KEYWORDS:
        if keyword.lower() in liga_lower:
            return True
    
    return False

# ============================================
# DETECCIÓN DE DEPORTE
# ============================================

def get_sport_from_liga(liga):
    liga_lower = liga.lower()
    
    if 'tenis' in liga_lower or 'tennis' in liga_lower:
        return 'tenis'
    if 'nba' in liga_lower or 'wnba' in liga_lower:
        return 'nba'
    if 'mlb' in liga_lower:
        return 'mlb'
    if 'nfl' in liga_lower:
        return 'nfl'
    if 'nhl' in liga_lower:
        return 'nhl'
    if 'wwe' in liga_lower:
        return 'wwe'
    if 'ufc' in liga_lower:
        return 'ufc'
    if 'deportes' in liga_lower:
        return 'deportes'
    if 'box' in liga_lower or 'boxeo' in liga_lower:
        return 'box'
    return 'football'

# ============================================
# CALCULAR HORA FIN
# ============================================

def calcular_hora_fin(hora_inicio_utc, deporte):
    if not hora_inicio_utc:
        return None
    
    try:
        duracion = SPORT_DURATION.get(deporte, SPORT_DURATION['default'])
        hora_limpia = hora_inicio_utc.replace('Z', '')
        
        formatos = ['%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M']
        
        inicio_dt = None
        for fmt in formatos:
            try:
                inicio_dt = datetime.strptime(hora_limpia, fmt)
                break
            except:
                continue
        
        if not inicio_dt:
            return None
        
        fin_dt = inicio_dt + timedelta(minutes=duracion)
        return fin_dt.strftime('%Y-%m-%dT%H:%M:%SZ')
    except Exception:
        return None

# ============================================
# GENERAR CLAVE DE UNIFICACIÓN
# ============================================

def generar_clave(liga, equipos, hora_utc, sport=None):
    if sport == 'football':
        if hora_utc:
            try:
                dt = datetime.strptime(hora_utc[:16], '%Y-%m-%dT%H:%M')
                hora_base = (dt.hour // 3) * 3
                dt_rounded = dt.replace(hour=hora_base, minute=0, second=0)
                return f"football|{equipos}|{dt_rounded.isoformat()}"
            except:
                return f"football|{equipos}|{hora_utc[:16]}"
        return f"football|{equipos}"
    
    if sport == 'nba' and 'wnba' not in liga.lower():
        equipos_normalizado = equipos.lower().replace(' vs ', '|')
        return f"{liga}|{equipos_normalizado}"
    
    if sport == 'mlb':
        equipos_normalizado = equipos.lower().replace(' vs ', '|')
        return f"{liga}|{equipos_normalizado}"
    
    if sport in ['nhl', 'nfl', 'box']:
        equipos_normalizado = normalizar_evento_general(equipos)
        return f"{liga}|{equipos_normalizado}"
    
    if not hora_utc:
        return f"{liga}|{equipos}"
    
    try:
        hora_limpia = hora_utc.replace('Z', '')
        if len(hora_limpia) == 16:
            hora_limpia = hora_limpia + ':00'
        
        dt = datetime.strptime(hora_limpia, '%Y-%m-%dT%H:%M:%S')
        hora_base = (dt.hour // 3) * 3
        dt_rounded = dt.replace(hour=hora_base, minute=0, second=0)
        return f"{liga}|{equipos}|{dt_rounded.isoformat()}"
    except:
        return f"{liga}|{equipos}"

# ============================================
# GENERAR matches.json
# ============================================

def generate_matches_json(input_file=None, output_file=None):
    input_file = input_file or CONFIG['input_file']
    output_file = output_file or CONFIG['output_file']
    
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            raw_matches = json.load(f)
    except FileNotFoundError:
        print(f"❌ No se encuentra {input_file}")
        return
    
    print(f"📊 Procesando {len(raw_matches)} eventos...")
    
    gitlab_events = []
    other_events = []
    
    for item in raw_matches:
        if item.get('fuente') == 'eventos':
            gitlab_events.append(item)
        else:
            other_events.append(item)
    
    print(f"   📌 Eventos base (otras fuentes): {len(other_events)}")
    print(f"   📌 Eventos GitLab (solo aportan canales): {len(gitlab_events)}")
    
    unified = {}
    excluded_count = 0
    
    for item in other_events:
        match_text = item.get('equipos')
        if not match_text:
            continue
        
        liga = item.get('liga', '').replace(':', '')
        liga = limpiar_nombre_liga(liga)
        
        if is_league_excluded(liga):
            excluded_count += 1
            print(f"  ⏭️ Excluido por liga: {liga}")
            continue
        
        sport_actual = get_sport_from_liga(liga)
        
        match_text = reordenar_prefijo_evento(match_text)
        match_text = limpiar_a_confirmar(match_text)
        
        if sport_actual == 'nba' and 'wnba' not in liga.lower():
            match_text = extraer_solo_equipos(match_text)
        elif sport_actual == 'mlb':
            match_text = extraer_solo_equipos_mlb(match_text)
        elif sport_actual == 'football':
            # 🔥 NORMALIZAR EQUIPOS DE FÚTBOL
            match_text = normalizar_partido_football(match_text)
        
        equipos_ordenados = match_text
        
        if sport_actual == 'football':
            equipos_ordenados = corregir_america_por_liga(equipos_ordenados, liga)
        
        logo = item.get('logo', '')
        
        hora_utc = item.get('hora_utc', '')
        key = generar_clave(liga, equipos_ordenados, hora_utc, sport_actual)
        hora_fin = calcular_hora_fin(hora_utc, sport_actual)
        
        if key not in unified:
            unified[key] = {
                'hora_utc': hora_utc,
                'hora_fin_utc': hora_fin,
                'liga': liga,
                'equipos': equipos_ordenados,
                'logo': logo,
                'sport': sport_actual,
                'canales': []
            }
        
        target = unified[key]
        for canal in item.get('canales', []):
            url = canal.get('url', '')
            if not url:
                continue
            
            exists = any(c.get('url') == url for c in target['canales'])
            if not exists:
                target['canales'].append({
                    'nombre': canal.get('nombre', 'Canal'),
                    'url': url,
                    'calidad': canal.get('calidad', 'HD')
                })
        
        if hora_utc and (not target['hora_utc'] or hora_utc < target['hora_utc']):
            target['hora_utc'] = hora_utc
            target['hora_fin_utc'] = calcular_hora_fin(hora_utc, sport_actual)
    
    gitlab_merged = 0
    gitlab_ignored = 0
    
    for item in gitlab_events:
        liga = item.get('liga', '').replace(':', '')
        liga = limpiar_nombre_liga(liga)
        
        if is_league_excluded(liga):
            continue
        
        encontrado = False
        for existing in unified.values():
            if existing.get('liga', '').lower() == liga.lower():
                encontrado = True
                gitlab_merged += 1
                print(f"  🔗 GitLab → unificado por liga: '{liga}'")
                
                for canal in item.get('canales', []):
                    url = canal.get('url', '')
                    if not url:
                        continue
                    
                    exists = any(c.get('url') == url for c in existing['canales'])
                    if not exists:
                        existing['canales'].append({
                            'nombre': canal.get('nombre', 'Canal'),
                            'url': url,
                            'calidad': canal.get('calidad', 'HD')
                        })
                
                break
        
        if not encontrado:
            gitlab_ignored += 1
            print(f"  ⏭️ GitLab ignorado (sin coincidencia por liga): '{liga}'")
    
    print(f"   🔗 GitLab unificados: {gitlab_merged}")
    print(f"   ⏭️ GitLab ignorados: {gitlab_ignored}")
    
    matches_list = list(unified.values())
    matches_list.sort(key=lambda x: x.get('hora_utc', ''))
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(matches_list, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Generado {output_file} con {len(matches_list)} partidos")
    
    if excluded_count > 0:
        print(f"⏭️ Ligas excluidas: {excluded_count} eventos filtrados")
    
    deportes = defaultdict(int)
    for m in matches_list:
        deportes[m.get('sport', 'football')] += 1
    
    print(f"\n📊 Desglose por deporte:")
    for deporte, count in sorted(deportes.items(), key=lambda x: x[1], reverse=True):
        print(f"   - {deporte}: {count}")
    
    total_canales = sum(len(m['canales']) for m in matches_list)
    print(f"📡 Total de canales únicos: {total_canales}")
    
    return matches_list

# ============================================
# CLI
# ============================================

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print("""
🏆 SPORTS ENGINE

Comandos:
  python engine.py batch → Generar matches.json
        """)
    elif sys.argv[1] == 'batch':
        generate_matches_json()
    else:
        print("Comando no reconocido")