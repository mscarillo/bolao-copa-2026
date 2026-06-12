#!/usr/bin/env python3
"""
GitHub Actions — busca resultados da Copa 2026 e salva no Supabase.
Fontes: worldcup26.ir → Sofascore → openfootball
Secrets: SUPABASE_URL, SUPABASE_KEY
"""
import os, sys, json, requests
from datetime import datetime, timezone

SUPABASE_URL = os.environ.get('SUPABASE_URL','').rstrip('/')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY','')
TIMEOUT = 20

# ── Nomes em português ─────────────────────────────────────────────
NM = {
    'mexico':'México','south africa':'África do Sul',
    'south korea':'Coréia do Sul','korea republic':'Coréia do Sul',
    'czech republic':'República Tcheca','czechia':'República Tcheca',
    'canada':'Canadá','bosnia and herzegovina':'Bósnia e Herzegovina',
    'qatar':'Catar','switzerland':'Suíça','brazil':'Brasil',
    'morocco':'Marrocos','haiti':'Haiti','scotland':'Escócia',
    'usa':'Estados Unidos','united states':'Estados Unidos',
    'paraguay':'Paraguai','australia':'Austrália',
    'turkey':'Turquia','türkiye':'Turquia','germany':'Alemanha',
    'curacao':'Curaçau','curaçao':'Curaçau',
    "côte d'ivoire":'Costa do Marfim','ivory coast':'Costa do Marfim',
    'ecuador':'Equador','netherlands':'Holanda','japan':'Japão',
    'sweden':'Suécia','tunisia':'Tunísia','belgium':'Bélgica',
    'egypt':'Egito','iran':'Irã','new zealand':'Nova Zelândia',
    'spain':'Espanha','cape verde':'Cabo Verde',
    'saudi arabia':'Arábia Saudita','uruguay':'Uruguai',
    'france':'França','senegal':'Senegal','iraq':'Iraque',
    'norway':'Noruega','argentina':'Argentina','algeria':'Argélia',
    'austria':'Áustria','jordan':'Jordânia','portugal':'Portugal',
    'dr congo':'Rep. do Congo','democratic republic of congo':'Rep. do Congo',
    'uzbekistan':'Uzbequistão','colombia':'Colômbia',
    'england':'Inglaterra','croatia':'Croácia','ghana':'Gana','panama':'Panamá',
}
def pt(n):
    if not n: return ''
    return NM.get(str(n).lower().strip(), str(n).strip())

# ── Ordem dos jogos 1-72 ──────────────────────────────────────────
GROUP_ORDER = [
    ('México','África do Sul'),('Coréia do Sul','República Tcheca'),
    ('República Tcheca','África do Sul'),('México','Coréia do Sul'),
    ('República Tcheca','México'),('África do Sul','Coréia do Sul'),
    ('Canadá','Bósnia e Herzegovina'),('Catar','Suíça'),
    ('Suíça','Bósnia e Herzegovina'),('Canadá','Catar'),
    ('Suíça','Canadá'),('Bósnia e Herzegovina','Catar'),
    ('Brasil','Marrocos'),('Haiti','Escócia'),
    ('Escócia','Marrocos'),('Brasil','Haiti'),
    ('Escócia','Brasil'),('Marrocos','Haiti'),
    ('Estados Unidos','Paraguai'),('Austrália','Turquia'),
    ('Turquia','Paraguai'),('Estados Unidos','Austrália'),
    ('Turquia','Estados Unidos'),('Paraguai','Austrália'),
    ('Alemanha','Curaçau'),('Costa do Marfim','Equador'),
    ('Alemanha','Costa do Marfim'),('Equador','Curaçau'),
    ('Equador','Alemanha'),('Curaçau','Costa do Marfim'),
    ('Holanda','Japão'),('Suécia','Tunísia'),
    ('Tunísia','Japão'),('Holanda','Suécia'),
    ('Japão','Suécia'),('Tunísia','Holanda'),
    ('Bélgica','Egito'),('Irã','Nova Zelândia'),
    ('Bélgica','Irã'),('Nova Zelândia','Egito'),
    ('Egito','Irã'),('Nova Zelândia','Bélgica'),
    ('Espanha','Cabo Verde'),('Arábia Saudita','Uruguai'),
    ('Espanha','Arábia Saudita'),('Uruguai','Cabo Verde'),
    ('Cabo Verde','Arábia Saudita'),('Uruguai','Espanha'),
    ('França','Senegal'),('Iraque','Noruega'),
    ('França','Iraque'),('Noruega','Senegal'),
    ('Noruega','França'),('Senegal','Iraque'),
    ('Argentina','Argélia'),('Áustria','Jordânia'),
    ('Argentina','Áustria'),('Jordânia','Argélia'),
    ('Argélia','Áustria'),('Jordânia','Argentina'),
    ('Portugal','Rep. do Congo'),('Uzbequistão','Colômbia'),
    ('Portugal','Uzbequistão'),('Colômbia','Rep. do Congo'),
    ('Colômbia','Portugal'),('Rep. do Congo','Uzbequistão'),
    ('Inglaterra','Croácia'),('Gana','Panamá'),
    ('Inglaterra','Gana'),('Panamá','Croácia'),
    ('Panamá','Inglaterra'),('Croácia','Gana'),
]

def match_num(t1, t2):
    for i,(a,b) in enumerate(GROUP_ORDER,1):
        if (a.lower()==t1.lower() and b.lower()==t2.lower()) or \
           (b.lower()==t1.lower() and a.lower()==t2.lower()):
            return i
    return None

# ── Fonte 1: worldcup26.ir ────────────────────────────────────────
def fetch_worldcup26():
    print("  → worldcup26.ir ...")
    try:
        r = requests.get('https://worldcup26.ir/get/games',
            headers={'User-Agent':'Mozilla/5.0','Accept':'application/json'},
            timeout=TIMEOUT)
        print(f"    Status: {r.status_code}")
        if not r.ok: return None
        raw = r.json()
        print(f"    Tipo resposta: {type(raw)}, keys: {list(raw.keys()) if isinstance(raw,dict) else 'lista'}")
        games = raw if isinstance(raw,list) else raw.get('games', raw.get('data', raw.get('matches',[])))
        print(f"    Total jogos na resposta: {len(games)}")

        results = []
        for g in games:
            # Tenta todos os campos possíveis de placar
            s1 = (g.get('home_score') or g.get('score1') or
                  g.get('homeScore') or g.get('home_goals') or
                  g.get('team1_goals'))
            s2 = (g.get('away_score') or g.get('score2') or
                  g.get('awayScore') or g.get('away_goals') or
                  g.get('team2_goals'))
            if s1 is None or s2 is None: continue

            # Tenta todos os campos de nome de time
            def get_team(prefix, alt_key):
                t = g.get(prefix+'_team') or g.get(alt_key) or {}
                if isinstance(t, dict):
                    return t.get('name_en') or t.get('name') or ''
                return str(t) if t else ''

            home = get_team('home','team1')
            away = get_team('away','team2')
            if not home or not away: continue

            results.append({'t1':pt(home),'t2':pt(away),'g1':int(s1),'g2':int(s2)})

        print(f"    ✅ {len(results)} jogos com placar")
        return results if results else None
    except Exception as e:
        print(f"    ❌ Erro: {e}")
        return None

# ── Fonte 2: Sofascore ────────────────────────────────────────────
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
        print(f"    Season ID: {sid}")

        results = []
        for page in range(20):
            r = requests.get(
                f'https://api.sofascore.com/api/v1/unique-tournament/16/season/{sid}/events/last/{page}',
                headers=SF, timeout=TIMEOUT)
            if not r.ok: break
            data = r.json()
            for ev in data.get('events',[]):
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
        print(f"    ❌ Erro: {e}")
        return None

# ── Fonte 3: openfootball ─────────────────────────────────────────
def fetch_openfootball():
    print("  → openfootball ...")
    try:
        r = requests.get(
            'https://raw.githubusercontent.com/openfootball/worldcup.json/master/2026/worldcup.json',
            timeout=TIMEOUT)
        if not r.ok: return None
        results = []
        for m in r.json().get('matches',[]):
            if m.get('score1') is None or m.get('score2') is None: continue
            results.append({'t1':pt(m['team1']),'t2':pt(m['team2']),
                           'g1':m['score1'],'g2':m['score2']})
        print(f"    ✅ {len(results)} jogos")
        return results if results else None
    except Exception as e:
        print(f"    ❌ Erro: {e}")
        return None

# ── Monta rows do Supabase ────────────────────────────────────────
def build_rows(raw):
    rows = {}
    ko_num = 72
    seen_ko = {}
    for r in raw:
        t1,t2,g1,g2 = r['t1'],r['t2'],r['g1'],r['g2']
        if not t1 or not t2: continue
        n = match_num(t1,t2)
        if n:
            rows[n] = {'jogo_num':n,'time1':t1,'gols1':g1,'time2':t2,'gols2':g2,
                       'atualizado_em':datetime.now(timezone.utc).isoformat()}
        else:
            key = tuple(sorted([t1.lower(),t2.lower()]))
            if key not in seen_ko:
                ko_num += 1
                seen_ko[key] = ko_num
            n = seen_ko[key]
            rows[n] = {'jogo_num':n,'time1':t1,'gols1':g1,'time2':t2,'gols2':g2,
                       'atualizado_em':datetime.now(timezone.utc).isoformat()}
    return list(rows.values())

# ── Supabase upsert ───────────────────────────────────────────────
def save(rows):
    url = f"{SUPABASE_URL}/rest/v1/resultados"
    headers = {
        'apikey': SUPABASE_KEY,
        'Authorization': f'Bearer {SUPABASE_KEY}',
        'Content-Type': 'application/json',
        'Prefer': 'resolution=merge-duplicates,return=minimal',
    }
    # Send in batches of 50
    for i in range(0, len(rows), 50):
        batch = rows[i:i+50]
        r = requests.post(url, headers=headers, json=batch, timeout=30)
        if not r.ok:
            print(f"❌ Supabase {r.status_code}: {r.text[:300]}")
            sys.exit(1)
    print(f"✅ {len(rows)} resultados salvos no Supabase")

# ── Main ──────────────────────────────────────────────────────────
def main():
    now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
    print(f"\n{'='*50}")
    print(f"  Copa 2026 — Atualização: {now}")
    print(f"{'='*50}\n")

    if not SUPABASE_URL or not SUPABASE_KEY:
        print("❌ SUPABASE_URL / SUPABASE_KEY não definidos nos Secrets do GitHub")
        sys.exit(1)
    print(f"✅ Supabase: {SUPABASE_URL}\n")

    print("🔍 Buscando resultados...")
    raw = fetch_worldcup26() or fetch_sofascore() or fetch_openfootball()

    if not raw:
        print("\n⚠️  Nenhuma fonte retornou dados — normal se ainda não houve jogos.")
        sys.exit(0)

    rows = build_rows(raw)
    print(f"\n📊 {len(rows)} jogos para salvar")
    if not rows:
        print("⚠️  Nenhum jogo válido.")
        sys.exit(0)

    save(rows)
    print("✅ Concluído!")

if __name__ == '__main__':
    main()
