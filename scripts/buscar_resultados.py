#!/usr/bin/env python3
"""
Busca resultados da Copa 2026 e salva no Supabase.
A numeração dos jogos é FIXA e baseada no calendário oficial da FIFA.
Fontes: worldcup26.ir → Sofascore → openfootball
Secrets GitHub: SUPABASE_URL, SUPABASE_KEY
"""
import os, sys, requests
from datetime import datetime, timezone

SUPABASE_URL = os.environ.get('SUPABASE_URL','').rstrip('/')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY','')
TIMEOUT = 20

# ─── CALENDÁRIO OFICIAL FIFA — mapeamento fixo time1 × time2 → número do jogo
# Fonte: tabela oficial divulgada pela FIFA em 06/06/2026
# Grupos em ordem cronológica exata (mesma da planilha de palpites)
GAME_MAP = {
    # Jogo: (time1_lower, time2_lower) → num
    # GRUPO A
    ('méxico','áfrica do sul'): 1,
    ('coréia do sul','república tcheca'): 2,
    ('república tcheca','áfrica do sul'): 3,
    ('méxico','coréia do sul'): 4,
    ('república tcheca','méxico'): 5,
    ('áfrica do sul','coréia do sul'): 6,
    # GRUPO B
    ('canadá','bósnia e herzegovina'): 7,
    ('catar','suíça'): 8,
    ('suíça','bósnia e herzegovina'): 9,
    ('canadá','catar'): 10,
    ('suíça','canadá'): 11,
    ('bósnia e herzegovina','catar'): 12,
    # GRUPO C
    ('brasil','marrocos'): 13,
    ('haiti','escócia'): 14,
    ('escócia','marrocos'): 15,
    ('brasil','haiti'): 16,
    ('escócia','brasil'): 17,
    ('marrocos','haiti'): 18,
    # GRUPO D
    ('estados unidos','paraguai'): 19,
    ('austrália','turquia'): 20,
    ('turquia','paraguai'): 21,
    ('estados unidos','austrália'): 22,
    ('turquia','estados unidos'): 23,
    ('paraguai','austrália'): 24,
    # GRUPO E
    ('alemanha','curaçau'): 25,
    ('costa do marfim','equador'): 26,
    ('alemanha','costa do marfim'): 27,
    ('equador','curaçau'): 28,
    ('equador','alemanha'): 29,
    ('curaçau','costa do marfim'): 30,
    # GRUPO F
    ('holanda','japão'): 31,
    ('suécia','tunísia'): 32,
    ('tunísia','japão'): 33,
    ('holanda','suécia'): 34,
    ('japão','suécia'): 35,
    ('tunísia','holanda'): 36,
    # GRUPO G
    ('bélgica','egito'): 37,
    ('irã','nova zelândia'): 38,
    ('bélgica','irã'): 39,
    ('nova zelândia','egito'): 40,
    ('egito','irã'): 41,
    ('nova zelândia','bélgica'): 42,
    # GRUPO H
    ('espanha','cabo verde'): 43,
    ('arábia saudita','uruguai'): 44,
    ('espanha','arábia saudita'): 45,
    ('uruguai','cabo verde'): 46,
    ('cabo verde','arábia saudita'): 47,
    ('uruguai','espanha'): 48,
    # GRUPO I
    ('frança','senegal'): 49,
    ('iraque','noruega'): 50,
    ('frança','iraque'): 51,
    ('noruega','senegal'): 52,
    ('noruega','frança'): 53,
    ('senegal','iraque'): 54,
    # GRUPO J
    ('argentina','argélia'): 55,
    ('áustria','jordânia'): 56,
    ('argentina','áustria'): 57,
    ('jordânia','argélia'): 58,
    ('argélia','áustria'): 59,
    ('jordânia','argentina'): 60,
    # GRUPO K
    ('portugal','rep. do congo'): 61,
    ('uzbequistão','colômbia'): 62,
    ('portugal','uzbequistão'): 63,
    ('colômbia','rep. do congo'): 64,
    ('colômbia','portugal'): 65,
    ('rep. do congo','uzbequistão'): 66,
    # GRUPO L
    ('inglaterra','croácia'): 67,
    ('gana','panamá'): 68,
    ('inglaterra','gana'): 69,
    ('panamá','croácia'): 70,
    ('panamá','inglaterra'): 71,
    ('croácia','gana'): 72,
}

# Nomes alternativos que as APIs podem retornar → nome padrão em português
ALIAS = {
    'mexico':'méxico', 'south africa':'áfrica do sul',
    'south korea':'coréia do sul', 'korea republic':'coréia do sul',
    'republic of korea':'coréia do sul', 'korea, republic of':'coréia do sul',
    'czech republic':'república tcheca', 'czechia':'república tcheca',
    'canada':'canadá', 'bosnia and herzegovina':'bósnia e herzegovina',
    'bosnia':'bósnia e herzegovina', 'qatar':'catar', 'switzerland':'suíça',
    'brazil':'brasil', 'morocco':'marrocos', 'haiti':'haiti', 'scotland':'escócia',
    'usa':'estados unidos', 'united states':'estados unidos',
    'united states of america':'estados unidos',
    'paraguay':'paraguai', 'australia':'austrália',
    'turkey':'turquia', 'türkiye':'turquia',
    'germany':'alemanha', 'curacao':'curaçau', 'curaçao':'curaçau',
    "côte d'ivoire":'costa do marfim', 'ivory coast':'costa do marfim',
    "cote d'ivoire":'costa do marfim',
    'ecuador':'equador', 'netherlands':'holanda', 'japan':'japão',
    'sweden':'suécia', 'tunisia':'tunísia', 'belgium':'bélgica',
    'egypt':'egito', 'iran':'irã', 'new zealand':'nova zelândia',
    'spain':'espanha', 'cape verde':'cabo verde',
    'saudi arabia':'arábia saudita', 'uruguay':'uruguai',
    'france':'frança', 'senegal':'senegal', 'iraq':'iraque',
    'norway':'noruega', 'argentina':'argentina', 'algeria':'argélia',
    'austria':'áustria', 'jordan':'jordânia', 'portugal':'portugal',
    'dr congo':'rep. do congo', 'democratic republic of congo':'rep. do congo',
    'congo dr':'rep. do congo', 'congo, democratic republic of the':'rep. do congo',
    'uzbekistan':'uzbequistão', 'colombia':'colômbia',
    'england':'inglaterra', 'croatia':'croácia', 'ghana':'gana', 'panama':'panamá',
}

def pt(name):
    """Converte nome para português padrão."""
    if not name: return ''
    s = str(name).lower().strip()
    return ALIAS.get(s, str(name).strip())

def get_game_num(t1_pt, t2_pt):
    """Retorna número do jogo pela tabela fixa, ou None para mata-mata."""
    k1 = (t1_pt.lower(), t2_pt.lower())
    k2 = (t2_pt.lower(), t1_pt.lower())
    return GAME_MAP.get(k1) or GAME_MAP.get(k2)

# ─── Fonte 1: worldcup26.ir ───────────────────────────────────────
def fetch_worldcup26():
    print("  → worldcup26.ir ...")
    try:
        r = requests.get('https://worldcup26.ir/get/games',
            headers={'User-Agent':'Mozilla/5.0','Accept':'application/json'},
            timeout=TIMEOUT)
        print(f"    HTTP {r.status_code}")
        if not r.ok: return None
        raw = r.json()
        games = raw if isinstance(raw,list) else raw.get('games', raw.get('data', raw.get('matches',[])))
        results = []
        for g in games:
            # Verificar status — só jogos finalizados
            status = str(g.get('status','') or g.get('state','')).lower()
            finished = status in ('finished','ft','full time','fulltime','ended','fim','encerrado','completed')
            
            s1 = g.get('home_score') if g.get('home_score') is not None else \
                 g.get('score1') if g.get('score1') is not None else \
                 g.get('homeScore') if g.get('homeScore') is not None else None
            s2 = g.get('away_score') if g.get('away_score') is not None else \
                 g.get('score2') if g.get('score2') is not None else \
                 g.get('awayScore') if g.get('awayScore') is not None else None
            
            if s1 is None or s2 is None: continue
            if not finished: continue  # CRÍTICO: só jogos finalizados

            def team_name(prefix, alt):
                t = g.get(f'{prefix}_team') or g.get(alt) or {}
                if isinstance(t, dict):
                    return t.get('name_en') or t.get('name') or ''
                return str(t) if t else ''
            
            home = team_name('home','team1')
            away = team_name('away','team2')
            if not home or not away: continue
            results.append({'t1':pt(home),'t2':pt(away),'g1':int(s1),'g2':int(s2)})
        
        print(f"    ✅ {len(results)} jogos finalizados")
        return results if results else None
    except Exception as e:
        print(f"    ❌ {e}")
        return None

# ─── Fonte 2: Sofascore ───────────────────────────────────────────
SF = {'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
      'Accept':'application/json','Referer':'https://www.sofascore.com/'}

def fetch_sofascore():
    print("  → Sofascore ...")
    try:
        r = requests.get('https://api.sofascore.com/api/v1/unique-tournament/16/seasons',
                         headers=SF, timeout=TIMEOUT)
        if not r.ok: return None
        seasons = r.json().get('seasons',[])
        season = next((s for s in seasons if '2026' in str(s.get('year',''))),
                      seasons[0] if seasons else None)
        if not season: return None
        sid = season['id']
        print(f"    Season: {sid}")
        results = []
        for page in range(20):
            r = requests.get(
                f'https://api.sofascore.com/api/v1/unique-tournament/16/season/{sid}/events/last/{page}',
                headers=SF, timeout=TIMEOUT)
            if not r.ok: break
            data = r.json()
            for ev in data.get('events',[]):
                # Apenas status 'finished' — nunca 'inprogress' ou 'notstarted'
                if ev.get('status',{}).get('type') != 'finished': continue
                hs = ev.get('homeScore',{}).get('current')
                aws = ev.get('awayScore',{}).get('current')
                if hs is None or aws is None: continue
                results.append({
                    't1': pt(ev['homeTeam']['name']),
                    't2': pt(ev['awayTeam']['name']),
                    'g1': hs, 'g2': aws
                })
            if not data.get('hasNextPage',False): break
        print(f"    ✅ {len(results)} jogos")
        return results if results else None
    except Exception as e:
        print(f"    ❌ {e}")
        return None

# ─── Fonte 3: openfootball ────────────────────────────────────────
def fetch_openfootball():
    print("  → openfootball ...")
    try:
        r = requests.get(
            'https://raw.githubusercontent.com/openfootball/worldcup.json/master/2026/worldcup.json',
            timeout=TIMEOUT)
        if not r.ok: return None
        results = []
        for m in r.json().get('matches',[]):
            # openfootball só tem placares quando jogo terminou
            if m.get('score1') is None or m.get('score2') is None: continue
            results.append({
                't1':pt(m.get('team1','')),
                't2':pt(m.get('team2','')),
                'g1':m['score1'],'g2':m['score2']
            })
        print(f"    ✅ {len(results)} jogos")
        return results if results else None
    except Exception as e:
        print(f"    ❌ {e}")
        return None

# ─── Converte resultados → linhas Supabase ────────────────────────
def build_rows(raw):
    rows = {}
    ko_num = 72
    seen_ko = {}
    now = datetime.now(timezone.utc).isoformat()
    
    for r in raw:
        t1,t2,g1,g2 = r['t1'],r['t2'],r['g1'],r['g2']
        if not t1 or not t2: continue
        
        n = get_game_num(t1, t2)
        if n:
            # Fase de grupos: número fixo
            rows[n] = {'jogo_num':n,'time1':t1,'gols1':g1,'time2':t2,'gols2':g2,'atualizado_em':now}
            print(f"    Jogo {n:3d}: {t1} {g1}–{g2} {t2}")
        else:
            # Mata-mata: numera sequencialmente a partir de 73
            key = tuple(sorted([t1.lower(),t2.lower()]))
            if key not in seen_ko:
                ko_num += 1
                seen_ko[key] = ko_num
            n = seen_ko[key]
            rows[n] = {'jogo_num':n,'time1':t1,'gols1':g1,'time2':t2,'gols2':g2,'atualizado_em':now}
            print(f"    Jogo {n:3d}: {t1} {g1}–{g2} {t2} (mata-mata)")
    
    return list(rows.values())

# ─── Supabase upsert ──────────────────────────────────────────────
def save(rows):
    headers = {
        'apikey': SUPABASE_KEY,
        'Authorization': f'Bearer {SUPABASE_KEY}',
        'Content-Type': 'application/json',
        'Prefer': 'resolution=merge-duplicates,return=minimal',
    }
    for i in range(0, len(rows), 50):
        batch = rows[i:i+50]
        r = requests.post(f"{SUPABASE_URL}/rest/v1/resultados",
                          headers=headers, json=batch, timeout=30)
        if not r.ok:
            print(f"❌ Supabase {r.status_code}: {r.text[:300]}")
            sys.exit(1)
    print(f"✅ {len(rows)} resultados salvos no Supabase")

# ─── Main ─────────────────────────────────────────────────────────
def main():
    now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
    print(f"\n{'='*50}\n  Copa 2026 — {now}\n{'='*50}\n")

    if not SUPABASE_URL or not SUPABASE_KEY:
        print("❌ SUPABASE_URL / SUPABASE_KEY não definidos")
        sys.exit(1)
    print(f"✅ Supabase: {SUPABASE_URL}\n")

    print("🔍 Buscando resultados...")
    raw = fetch_worldcup26() or fetch_sofascore() or fetch_openfootball()

    if not raw:
        print("⚠️  Nenhuma fonte retornou dados finalizados.")
        sys.exit(0)

    print(f"\n📊 Processando {len(raw)} resultados:")
    rows = build_rows(raw)

    if not rows:
        print("⚠️  Nenhum jogo mapeado para número de jogo.")
        sys.exit(0)

    print(f"\n💾 Salvando {len(rows)} jogos no Supabase...")
    save(rows)
    print("✅ Concluído!")

if __name__ == '__main__':
    main()
