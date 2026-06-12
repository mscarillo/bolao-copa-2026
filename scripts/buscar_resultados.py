#!/usr/bin/env python3
"""
GitHub Actions — busca resultados da Copa 2026 e salva no Supabase.

Fontes em cascata:
  1. worldcup26.ir  — API pública, sem chave
  2. Sofascore      — API pública não oficial
  3. openfootball   — JSON no GitHub (pode ter delay)

Secrets necessários no GitHub:
  SUPABASE_URL  → https://xxxx.supabase.co
  SUPABASE_KEY  → anon key (eyJhbGci...)
"""

import os, sys, json, requests
from datetime import datetime, timezone

# ── Credenciais ────────────────────────────────────────────────────────────────
SUPABASE_URL = os.environ.get('SUPABASE_URL', '').rstrip('/')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', '')
TIMEOUT = 20

# ── Mapa de nomes para português ───────────────────────────────────────────────
NM = {
    # inglês → português
    'mexico':'México','south africa':'África do Sul','south korea':'Coréia do Sul',
    'korea republic':'Coréia do Sul','czech republic':'República Tcheca',
    'czechia':'República Tcheca','canada':'Canadá',
    'bosnia and herzegovina':'Bósnia e Herzegovina','bosnia':'Bósnia e Herzegovina',
    'qatar':'Catar','switzerland':'Suíça','brazil':'Brasil','morocco':'Marrocos',
    'haiti':'Haiti','scotland':'Escócia','usa':'Estados Unidos',
    'united states':'Estados Unidos','paraguay':'Paraguai','australia':'Austrália',
    'turkey':'Turquia','türkiye':'Turquia','germany':'Alemanha','curacao':'Curaçau',
    'curaçao':'Curaçau',"côte d'ivoire":'Costa do Marfim','ivory coast':'Costa do Marfim',
    'ecuador':'Equador','netherlands':'Holanda','japan':'Japão','sweden':'Suécia',
    'tunisia':'Tunísia','belgium':'Bélgica','egypt':'Egito','iran':'Irã',
    'new zealand':'Nova Zelândia','spain':'Espanha','cape verde':'Cabo Verde',
    'saudi arabia':'Arábia Saudita','uruguay':'Uruguai','france':'França',
    'senegal':'Senegal','iraq':'Iraque','norway':'Noruega','argentina':'Argentina',
    'algeria':'Argélia','austria':'Áustria','jordan':'Jordânia','portugal':'Portugal',
    'dr congo':'Rep. do Congo','democratic republic of congo':'Rep. do Congo',
    'uzbekistan':'Uzbequistão','colombia':'Colômbia','england':'Inglaterra',
    'croatia':'Croácia','ghana':'Gana','panama':'Panamá',
}

def pt(name):
    if not name: return ''
    k = str(name).lower().strip()
    return NM.get(k) or NM.get(k.replace(' republic','').strip()) or str(name).strip()

# ── Ordem sequencial dos jogos (fase de grupos = 1–72) ─────────────────────────
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
    """Retorna número do jogo 1-72 se for fase de grupos, senão None."""
    for i, (a, b) in enumerate(GROUP_ORDER, 1):
        if (a.lower()==t1.lower() and b.lower()==t2.lower()) or \
           (b.lower()==t1.lower() and a.lower()==t2.lower()):
            return i
    return None

# ── Fonte 1: worldcup26.ir ─────────────────────────────────────────────────────
def fetch_worldcup26ir():
    print("  → Tentando worldcup26.ir ...")
    try:
        r = requests.get(
            'https://worldcup26.ir/get/games',
            headers={'User-Agent':'Mozilla/5.0','Accept':'application/json'},
            timeout=TIMEOUT
        )
        if not r.ok:
            print(f"    HTTP {r.status_code}")
            return None
        raw = r.json()
        # A API pode devolver lista direta ou objeto com campo
        games = raw if isinstance(raw, list) else \
                raw.get('games', raw.get('data', raw.get('matches', [])))
        if not games:
            print("    Nenhum jogo retornado")
            return None

        results = []
        for g in games:
            # Detecta placar — a API pode usar nomes variados
            s1 = g.get('home_score') if g.get('home_score') is not None else \
                 g.get('score1') if g.get('score1') is not None else \
                 g.get('homeScore') if g.get('homeScore') is not None else \
                 g.get('goals_home')
            s2 = g.get('away_score') if g.get('away_score') is not None else \
                 g.get('score2') if g.get('score2') is not None else \
                 g.get('awayScore') if g.get('awayScore') is not None else \
                 g.get('goals_away')
            if s1 is None or s2 is None:
                continue

            # Time casa
            ht = g.get('home_team') or g.get('team1') or g.get('homeTeam') or {}
            at = g.get('away_team') or g.get('team2') or g.get('awayTeam') or {}
            home_name = ht.get('name_en') or ht.get('name') or ht if isinstance(ht,str) else ''
            away_name = at.get('name_en') or at.get('name') or at if isinstance(at,str) else ''

            results.append({
                'home': pt(home_name), 'away': pt(away_name),
                'g1': int(s1), 'g2': int(s2)
            })

        print(f"    ✅ {len(results)} jogos encontrados")
        return results if results else None
    except Exception as e:
        print(f"    Erro: {e}")
        return None

# ── Fonte 2: Sofascore ─────────────────────────────────────────────────────────
SF_HDR = {
    'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept':'application/json',
    'Referer':'https://www.sofascore.com/',
}

def fetch_sofascore():
    print("  → Tentando Sofascore ...")
    try:
        # tournament 16 = FIFA World Cup
        r = requests.get(
            'https://api.sofascore.com/api/v1/unique-tournament/16/seasons',
            headers=SF_HDR, timeout=TIMEOUT)
        if not r.ok: return None
        seasons = r.json().get('seasons', [])
        season = next((s for s in seasons if '2026' in str(s.get('year',''))),
                      seasons[0] if seasons else None)
        if not season: return None
        sid = season['id']

        results = []
        for page in range(15):
            r = requests.get(
                f'https://api.sofascore.com/api/v1/unique-tournament/16/season/{sid}/events/last/{page}',
                headers=SF_HDR, timeout=TIMEOUT)
            if not r.ok: break
            data = r.json()
            for ev in data.get('events', []):
                if ev.get('status', {}).get('type') != 'finished': continue
                hs = ev.get('homeScore', {}).get('current')
                aws = ev.get('awayScore', {}).get('current')
                if hs is None or aws is None: continue
                results.append({
                    'home': pt(ev['homeTeam']['name']),
                    'away': pt(ev['awayTeam']['name']),
                    'g1': hs, 'g2': aws
                })
            if not data.get('hasNextPage', False): break

        print(f"    ✅ {len(results)} jogos encontrados")
        return results if results else None
    except Exception as e:
        print(f"    Erro: {e}")
        return None

# ── Fonte 3: openfootball ──────────────────────────────────────────────────────
def fetch_openfootball():
    print("  → Tentando openfootball ...")
    try:
        r = requests.get(
            'https://raw.githubusercontent.com/openfootball/worldcup.json/master/2026/worldcup.json',
            timeout=TIMEOUT)
        if not r.ok: return None
        results = []
        for m in r.json().get('matches', []):
            if m.get('score1') is None or m.get('score2') is None: continue
            results.append({
                'home': pt(m['team1']), 'away': pt(m['team2']),
                'g1': m['score1'], 'g2': m['score2']
            })
        print(f"    ✅ {len(results)} jogos encontrados")
        return results if results else None
    except Exception as e:
        print(f"    Erro: {e}")
        return None

# ── Converte resultados → linhas do Supabase ───────────────────────────────────
def build_rows(raw):
    rows = []
    ko_num = 72  # mata-mata começa em 73
    seen_ko = {}  # evita duplicatas no mata-mata

    for r in raw:
        t1, t2, g1, g2 = r['home'], r['away'], r['g1'], r['g2']
        if not t1 or not t2: continue

        n = match_num(t1, t2)
        if n:
            # Fase de grupos — número fixo
            rows.append({
                'jogo_num': n,
                'time1': t1, 'gols1': g1,
                'time2': t2, 'gols2': g2,
                'atualizado_em': datetime.now(timezone.utc).isoformat()
            })
        else:
            # Mata-mata — agrupa por confronto
            key = tuple(sorted([t1.lower(), t2.lower()]))
            if key not in seen_ko:
                ko_num += 1
                seen_ko[key] = ko_num
            rows.append({
                'jogo_num': seen_ko[key],
                'time1': t1, 'gols1': g1,
                'time2': t2, 'gols2': g2,
                'atualizado_em': datetime.now(timezone.utc).isoformat()
            })

    # Remove duplicatas de fase de grupos (mantém só 1 por jogo_num)
    seen_nums = {}
    deduped = []
    for row in rows:
        n = row['jogo_num']
        if n not in seen_nums:
            seen_nums[n] = True
            deduped.append(row)
    return deduped

# ── Supabase upsert ────────────────────────────────────────────────────────────
def save_supabase(rows):
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("❌ SUPABASE_URL ou SUPABASE_KEY não configurados nos Secrets do GitHub!")
        sys.exit(1)

    # Envia em lotes de 50 para não estourar limites
    batch_size = 50
    total = 0
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i+batch_size]
        r = requests.post(
            f"{SUPABASE_URL}/rest/v1/resultados",
            headers={
                'apikey': SUPABASE_KEY,
                'Authorization': f'Bearer {SUPABASE_KEY}',
                'Content-Type': 'application/json',
                'Prefer': 'resolution=merge-duplicates,return=minimal',
            },
            json=batch,
            timeout=30
        )
        if not r.ok:
            print(f"❌ Supabase erro {r.status_code}: {r.text[:300]}")
            sys.exit(1)
        total += len(batch)

    print(f"✅ {total} resultados salvos no Supabase.")

# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
    print(f"\n{'='*50}")
    print(f"  Bolão Copa 2026 — Atualização de resultados")
    print(f"  {now}")
    print(f"{'='*50}\n")

    # Verifica secrets antes de tudo
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("❌ ERRO: Variáveis SUPABASE_URL e SUPABASE_KEY não encontradas.")
        print("   Configure os Secrets no GitHub: Settings → Secrets → Actions")
        sys.exit(1)
    print(f"✅ Supabase configurado: {SUPABASE_URL[:40]}...\n")

    print("🔍 Buscando resultados...")
    raw = fetch_worldcup26ir() or fetch_sofascore() or fetch_openfootball()

    if not raw:
        print("\n⚠️  Nenhuma fonte retornou dados.")
        print("   Isso é normal se nenhum jogo foi disputado ainda.")
        print("   O script vai tentar novamente na próxima execução.")
        sys.exit(0)  # exit 0 = não é erro, apenas sem dados

    print(f"\n📊 Processando {len(raw)} resultados...")
    rows = build_rows(raw)
    print(f"   {len(rows)} jogos únicos para salvar")

    if not rows:
        print("⚠️  Nenhum resultado válido para salvar.")
        sys.exit(0)

    print("\n💾 Salvando no Supabase...")
    save_supabase(rows)

    print(f"\n✅ Concluído com sucesso!\n")

if __name__ == '__main__':
    main()
