#!/usr/bin/env python3
"""
GitHub Actions script — busca resultados da Copa 2026 e salva no Supabase.
Fontes (em ordem de prioridade):
  1. worldcup26.ir  — API pública, sem chave, atualizada em tempo real
  2. Sofascore      — API pública não oficial, fallback
  3. openfootball  — fallback manual, pode ter delay de horas

Configuração (variáveis de ambiente / GitHub Secrets):
  SUPABASE_URL  — URL do seu projeto Supabase (ex: https://xxxx.supabase.co)
  SUPABASE_KEY  — anon/service key do Supabase
"""

import os, json, sys, requests
from datetime import datetime, timezone

# ── Config ────────────────────────────────────────────────────────────────────
SUPABASE_URL = os.environ.get('SUPABASE_URL', '').rstrip('/')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', '')

HEADERS_JSON = {'Content-Type': 'application/json'}
TIMEOUT = 15

# ── Nome PT-BR dos times ───────────────────────────────────────────────────────
NM = {
    'mexico':'México', 'México':'México',
    'south africa':'África do Sul', 'South Africa':'África do Sul',
    'south korea':'Coréia do Sul', 'South Korea':'Coréia do Sul', 'Korea Republic':'Coréia do Sul',
    'czech republic':'República Tcheca', 'czechia':'República Tcheca', 'Czechia':'República Tcheca', 'Czech Republic':'República Tcheca',
    'canada':'Canadá', 'Canada':'Canadá',
    'bosnia and herzegovina':'Bósnia e Herzegovina', 'Bosnia':'Bósnia e Herzegovina', 'Bosnia and Herzegovina':'Bósnia e Herzegovina',
    'qatar':'Catar', 'Qatar':'Catar',
    'switzerland':'Suíça', 'Switzerland':'Suíça',
    'brazil':'Brasil', 'Brazil':'Brasil',
    'morocco':'Marrocos', 'Morocco':'Marrocos',
    'haiti':'Haiti', 'Haiti':'Haiti',
    'scotland':'Escócia', 'Scotland':'Escócia',
    'usa':'Estados Unidos', 'united states':'Estados Unidos', 'United States':'Estados Unidos', 'USA':'Estados Unidos',
    'paraguay':'Paraguai', 'Paraguay':'Paraguai',
    'australia':'Austrália', 'Australia':'Austrália',
    'turkey':'Turquia', 'Turkey':'Turquia', 'Türkiye':'Turquia',
    'germany':'Alemanha', 'Germany':'Alemanha',
    'curacao':'Curaçau', 'Curacao':'Curaçau', 'Curaçao':'Curaçau',
    "côte d'ivoire":'Costa do Marfim', 'ivory coast':'Costa do Marfim', "Côte d'Ivoire":'Costa do Marfim',
    'ecuador':'Equador', 'Ecuador':'Equador',
    'netherlands':'Holanda', 'Netherlands':'Holanda',
    'japan':'Japão', 'Japan':'Japão',
    'sweden':'Suécia', 'Sweden':'Suécia',
    'tunisia':'Tunísia', 'Tunisia':'Tunísia',
    'belgium':'Bélgica', 'Belgium':'Bélgica',
    'egypt':'Egito', 'Egypt':'Egito',
    'iran':'Irã', 'Iran':'Irã',
    'new zealand':'Nova Zelândia', 'New Zealand':'Nova Zelândia',
    'spain':'Espanha', 'Spain':'Espanha',
    'cape verde':'Cabo Verde', 'Cape Verde':'Cabo Verde',
    'saudi arabia':'Arábia Saudita', 'Saudi Arabia':'Arábia Saudita',
    'uruguay':'Uruguai', 'Uruguay':'Uruguai',
    'france':'França', 'France':'França',
    'senegal':'Senegal', 'Senegal':'Senegal',
    'iraq':'Iraque', 'Iraq':'Iraque',
    'norway':'Noruega', 'Norway':'Noruega',
    'argentina':'Argentina', 'Argentina':'Argentina',
    'algeria':'Argélia', 'Algeria':'Argélia',
    'austria':'Áustria', 'Austria':'Áustria',
    'jordan':'Jordânia', 'Jordan':'Jordânia',
    'portugal':'Portugal', 'Portugal':'Portugal',
    'dr congo':'Rep. do Congo', 'democratic republic of congo':'Rep. do Congo', 'DR Congo':'Rep. do Congo',
    'uzbekistan':'Uzbequistão', 'Uzbekistan':'Uzbequistão',
    'colombia':'Colômbia', 'Colombia':'Colômbia',
    'england':'Inglaterra', 'England':'Inglaterra',
    'croatia':'Croácia', 'Croatia':'Croácia',
    'ghana':'Gana', 'Ghana':'Gana',
    'panama':'Panamá', 'Panama':'Panamá',
}

def pt(name: str) -> str:
    if not name: return ''
    return NM.get(name) or NM.get(name.lower()) or name

# ── Ordem sequencial da fase de grupos (mesma que na planilha) ─────────────────
GROUP_ORDER = [
    ('México','África do Sul'), ('Coréia do Sul','República Tcheca'),
    ('República Tcheca','África do Sul'), ('México','Coréia do Sul'),
    ('República Tcheca','México'), ('África do Sul','Coréia do Sul'),
    ('Canadá','Bósnia e Herzegovina'), ('Catar','Suíça'),
    ('Suíça','Bósnia e Herzegovina'), ('Canadá','Catar'),
    ('Suíça','Canadá'), ('Bósnia e Herzegovina','Catar'),
    ('Brasil','Marrocos'), ('Haiti','Escócia'),
    ('Escócia','Marrocos'), ('Brasil','Haiti'),
    ('Escócia','Brasil'), ('Marrocos','Haiti'),
    ('Estados Unidos','Paraguai'), ('Austrália','Turquia'),
    ('Turquia','Paraguai'), ('Estados Unidos','Austrália'),
    ('Turquia','Estados Unidos'), ('Paraguai','Austrália'),
    ('Alemanha','Curaçau'), ('Costa do Marfim','Equador'),
    ('Alemanha','Costa do Marfim'), ('Equador','Curaçau'),
    ('Equador','Alemanha'), ('Curaçau','Costa do Marfim'),
    ('Holanda','Japão'), ('Suécia','Tunísia'),
    ('Tunísia','Japão'), ('Holanda','Suécia'),
    ('Japão','Suécia'), ('Tunísia','Holanda'),
    ('Bélgica','Egito'), ('Irã','Nova Zelândia'),
    ('Bélgica','Irã'), ('Nova Zelândia','Egito'),
    ('Egito','Irã'), ('Nova Zelândia','Bélgica'),
    ('Espanha','Cabo Verde'), ('Arábia Saudita','Uruguai'),
    ('Espanha','Arábia Saudita'), ('Uruguai','Cabo Verde'),
    ('Cabo Verde','Arábia Saudita'), ('Uruguai','Espanha'),
    ('França','Senegal'), ('Iraque','Noruega'),
    ('França','Iraque'), ('Noruega','Senegal'),
    ('Noruega','França'), ('Senegal','Iraque'),
    ('Argentina','Argélia'), ('Áustria','Jordânia'),
    ('Argentina','Áustria'), ('Jordânia','Argélia'),
    ('Argélia','Áustria'), ('Jordânia','Argentina'),
    ('Portugal','Rep. do Congo'), ('Uzbequistão','Colômbia'),
    ('Portugal','Uzbequistão'), ('Colômbia','Rep. do Congo'),
    ('Colômbia','Portugal'), ('Rep. do Congo','Uzbequistão'),
    ('Inglaterra','Croácia'), ('Gana','Panamá'),
    ('Inglaterra','Gana'), ('Panamá','Croácia'),
    ('Panamá','Inglaterra'), ('Croácia','Gana'),
]

def match_num(t1_pt: str, t2_pt: str):
    """Retorna número do jogo (1-72) para fase de grupos, ou None para mata-mata."""
    for i, (a, b) in enumerate(GROUP_ORDER, 1):
        if (a.lower()==t1_pt.lower() and b.lower()==t2_pt.lower()) or \
           (b.lower()==t1_pt.lower() and a.lower()==t2_pt.lower()):
            return i
    return None

# ── Fonte 1: worldcup26.ir ─────────────────────────────────────────────────────
def fetch_worldcup26ir():
    """API pública do worldcup26.ir — sem chave, sem autenticação."""
    print("🌐 Tentando worldcup26.ir...")
    try:
        r = requests.get('https://worldcup26.ir/get/games',
                         headers={'User-Agent': 'Mozilla/5.0'}, timeout=TIMEOUT)
        r.raise_for_status()
        data = r.json()
        games = data if isinstance(data, list) else data.get('games', data.get('data', []))
        results = []
        for g in games:
            # Detecta campos de placar — API pode usar campos diferentes
            status = str(g.get('status', g.get('state', ''))).lower()
            if status not in ('finished', 'ft', 'full time', 'completed', '1', 'fim', 'encerrado'):
                # Tenta verificar se tem placar definido mesmo sem status "finished"
                score1 = g.get('home_score', g.get('score1', g.get('homeScore', g.get('goals_home'))))
                score2 = g.get('away_score', g.get('score2', g.get('awayScore', g.get('goals_away'))))
                if score1 is None or score2 is None:
                    continue
            else:
                score1 = g.get('home_score', g.get('score1', g.get('homeScore', g.get('goals_home'))))
                score2 = g.get('away_score', g.get('score2', g.get('awayScore', g.get('goals_away'))))

            if score1 is None or score2 is None:
                continue

            home_raw = g.get('home_team', g.get('team1', g.get('homeTeam', {}))).get('name_en', '') \
                if isinstance(g.get('home_team', g.get('team1', g.get('homeTeam'))), dict) \
                else str(g.get('home_team', g.get('team1', '')))
            away_raw = g.get('away_team', g.get('team2', g.get('awayTeam', {}))).get('name_en', '') \
                if isinstance(g.get('away_team', g.get('team2', g.get('awayTeam'))), dict) \
                else str(g.get('away_team', g.get('team2', '')))

            results.append({
                'home': pt(home_raw), 'away': pt(away_raw),
                'gols_home': int(score1), 'gols_away': int(score2),
            })
        if results:
            print(f"  ✅ worldcup26.ir: {len(results)} jogos com resultado")
        return results or None
    except Exception as e:
        print(f"  ❌ worldcup26.ir erro: {e}")
        return None

# ── Fonte 2: Sofascore ─────────────────────────────────────────────────────────
SF_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/json',
    'Referer': 'https://www.sofascore.com/',
    'Accept-Language': 'pt-BR,pt;q=0.9',
}

def fetch_sofascore():
    """Sofascore API pública (usada pelo app deles)."""
    print("🌐 Tentando Sofascore...")
    try:
        # Busca season atual do World Cup (tournament ID 16)
        r = requests.get('https://api.sofascore.com/api/v1/unique-tournament/16/seasons',
                         headers=SF_HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        seasons = r.json().get('seasons', [])
        season = next((s for s in seasons if '2026' in str(s.get('year',''))), seasons[0] if seasons else None)
        if not season:
            return None
        sid = season['id']

        results = []
        page = 0
        while page < 10:  # max 10 páginas
            url = f'https://api.sofascore.com/api/v1/unique-tournament/16/season/{sid}/events/last/{page}'
            r = requests.get(url, headers=SF_HEADERS, timeout=TIMEOUT)
            if not r.ok: break
            data = r.json()
            events = data.get('events', [])
            if not events: break
            for ev in events:
                if ev.get('status', {}).get('type') != 'finished': continue
                hs = ev.get('homeScore', {}).get('current')
                aws = ev.get('awayScore', {}).get('current')
                if hs is None or aws is None: continue
                results.append({
                    'home': pt(ev.get('homeTeam', {}).get('name', '')),
                    'away': pt(ev.get('awayTeam', {}).get('name', '')),
                    'gols_home': hs, 'gols_away': aws,
                })
            if not data.get('hasNextPage', False): break
            page += 1

        if results:
            print(f"  ✅ Sofascore: {len(results)} jogos com resultado")
        return results or None
    except Exception as e:
        print(f"  ❌ Sofascore erro: {e}")
        return None

# ── Fonte 3: openfootball (fallback lento) ─────────────────────────────────────
def fetch_openfootball():
    print("🌐 Tentando openfootball (fallback)...")
    try:
        r = requests.get(
            'https://raw.githubusercontent.com/openfootball/worldcup.json/master/2026/worldcup.json',
            timeout=TIMEOUT)
        r.raise_for_status()
        data = r.json()
        results = []
        GR = {f'Matchday {i}' for i in range(1, 19)}
        for m in data.get('matches', []):
            if m.get('score1') is None or m.get('score2') is None: continue
            results.append({
                'home': pt(m.get('team1','')), 'away': pt(m.get('team2','')),
                'gols_home': m['score1'], 'gols_away': m['score2'],
            })
        if results:
            print(f"  ✅ openfootball: {len(results)} jogos com resultado")
        return results or None
    except Exception as e:
        print(f"  ❌ openfootball erro: {e}")
        return None

# ── Converte resultados brutos → linhas do Supabase ───────────────────────────
def to_supabase_rows(raw_results: list) -> list:
    rows = []
    ko_counter = 72  # mata-mata começa em 73

    # Agrupa para detectar duplicatas de confronto
    seen = {}  # (t1_lower, t2_lower) → row

    for r in raw_results:
        t1, t2 = r['home'], r['away']
        n = match_num(t1, t2)

        if n:
            # Fase de grupos — número fixo
            key = n
        else:
            # Mata-mata — usa confronto como chave
            k = tuple(sorted([t1.lower(), t2.lower()]))
            if k in seen:
                seen[k].update({'gols1': r['gols_home'], 'gols2': r['gols_away'],
                                 'time1': t1, 'time2': t2})
                continue
            ko_counter += 1
            key = ko_counter
            seen[k] = None  # marca como visto

        row = {
            'jogo_num': key,
            'time1': t1, 'gols1': r['gols_home'],
            'time2': t2, 'gols2': r['gols_away'],
            'atualizado_em': datetime.now(timezone.utc).isoformat(),
        }
        rows.append(row)

    return rows

# ── Supabase upsert ───────────────────────────────────────────────────────────
def save_to_supabase(rows: list):
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("❌ SUPABASE_URL ou SUPABASE_KEY não configurados!")
        sys.exit(1)

    url = f"{SUPABASE_URL}/rest/v1/resultados"
    headers = {
        'apikey': SUPABASE_KEY,
        'Authorization': f'Bearer {SUPABASE_KEY}',
        'Content-Type': 'application/json',
        'Prefer': 'resolution=merge-duplicates,return=minimal',
    }
    r = requests.post(url, headers=headers, json=rows, timeout=30)
    if not r.ok:
        print(f"❌ Supabase erro {r.status_code}: {r.text}")
        sys.exit(1)
    print(f"✅ {len(rows)} resultados salvos no Supabase!")

# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    print(f"🚀 Buscando resultados — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")

    raw = fetch_worldcup26ir() \
       or fetch_sofascore() \
       or fetch_openfootball()

    if not raw:
        print("⚠️  Nenhuma fonte retornou dados. Abortando sem sobrescrever Supabase.")
        sys.exit(0)

    rows = to_supabase_rows(raw)
    if not rows:
        print("⚠️  Nenhum jogo finalizado encontrado.")
        sys.exit(0)

    print(f"📊 {len(rows)} jogos para salvar (fase de grupos + mata-mata)")
    save_to_supabase(rows)

if __name__ == '__main__':
    main()
