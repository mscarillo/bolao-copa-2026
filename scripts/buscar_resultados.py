#!/usr/bin/env python3
"""
Busca resultados da Copa 2026 e salva no Supabase.
Numeração FIXA baseada no calendário oficial FIFA (par de times → número).
Fontes: Sofascore → worldcup26.ir → openfootball
Secrets: SUPABASE_URL, SUPABASE_KEY
"""
import os, sys, json, requests
from datetime import datetime, timezone

SUPABASE_URL = os.environ.get('SUPABASE_URL','').rstrip('/')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY','')
TIMEOUT = 25

# ─── Aliases EN/outros → português padrão ─────────────────────────
ALIAS = {
    'mexico':'méxico','south africa':'áfrica do sul','south korea':'coréia do sul',
    'korea republic':'coréia do sul','republic of korea':'coréia do sul',
    'czech republic':'república tcheca','czechia':'república tcheca',
    'canada':'canadá','bosnia and herzegovina':'bósnia e herzegovina',
    'bosnia & herzegovina':'bósnia e herzegovina','bosnia':'bósnia e herzegovina',
    'qatar':'catar','switzerland':'suíça','brazil':'brasil','morocco':'marrocos',
    'haiti':'haiti','scotland':'escócia','usa':'estados unidos',
    'united states':'estados unidos','united states of america':'estados unidos',
    'paraguay':'paraguai','australia':'austrália','turkey':'turquia','türkiye':'turquia',
    'germany':'alemanha','curacao':'curaçau','curaçao':'curaçau',
    "côte d'ivoire":'costa do marfim','ivory coast':'costa do marfim',
    "cote d'ivoire":'costa do marfim','ecuador':'equador','netherlands':'holanda',
    'japan':'japão','sweden':'suécia','tunisia':'tunísia','belgium':'bélgica',
    'egypt':'egito','iran':'irã','new zealand':'nova zelândia','spain':'espanha',
    'cape verde':'cabo verde','saudi arabia':'arábia saudita','uruguay':'uruguai',
    'france':'frança','senegal':'senegal','iraq':'iraque','norway':'noruega',
    'argentina':'argentina','algeria':'argélia','austria':'áustria','jordan':'jordânia',
    'portugal':'portugal','dr congo':'rep. do congo','democratic republic of congo':'rep. do congo',
    'congo dr':'rep. do congo','uzbekistan':'uzbequistão','colombia':'colômbia',
    'england':'inglaterra','croatia':'croácia','ghana':'gana','panama':'panamá',
}
def pt(name):
    if not name: return ''
    return ALIAS.get(str(name).lower().strip(), str(name).strip())

# ─── Mapa fixo: par de times → número do jogo (fase de grupos) ────
GAME_MAP = {
    ('méxico','áfrica do sul'):1, ('coréia do sul','república tcheca'):2,
    ('república tcheca','áfrica do sul'):3, ('méxico','coréia do sul'):4,
    ('república tcheca','méxico'):5, ('áfrica do sul','coréia do sul'):6,
    ('canadá','bósnia e herzegovina'):7, ('catar','suíça'):8,
    ('suíça','bósnia e herzegovina'):9, ('canadá','catar'):10,
    ('suíça','canadá'):11, ('bósnia e herzegovina','catar'):12,
    ('brasil','marrocos'):13, ('haiti','escócia'):14,
    ('escócia','marrocos'):15, ('brasil','haiti'):16,
    ('escócia','brasil'):17, ('marrocos','haiti'):18,
    ('estados unidos','paraguai'):19, ('austrália','turquia'):20,
    ('turquia','paraguai'):21, ('estados unidos','austrália'):22,
    ('turquia','estados unidos'):23, ('paraguai','austrália'):24,
    ('alemanha','curaçau'):25, ('costa do marfim','equador'):26,
    ('alemanha','costa do marfim'):27, ('equador','curaçau'):28,
    ('equador','alemanha'):29, ('curaçau','costa do marfim'):30,
    ('holanda','japão'):31, ('suécia','tunísia'):32,
    ('tunísia','japão'):33, ('holanda','suécia'):34,
    ('japão','suécia'):35, ('tunísia','holanda'):36,
    ('bélgica','egito'):37, ('irã','nova zelândia'):38,
    ('bélgica','irã'):39, ('nova zelândia','egito'):40,
    ('egito','irã'):41, ('nova zelândia','bélgica'):42,
    ('espanha','cabo verde'):43, ('arábia saudita','uruguai'):44,
    ('espanha','arábia saudita'):45, ('uruguai','cabo verde'):46,
    ('cabo verde','arábia saudita'):47, ('uruguai','espanha'):48,
    ('frança','senegal'):49, ('iraque','noruega'):50,
    ('frança','iraque'):51, ('noruega','senegal'):52,
    ('noruega','frança'):53, ('senegal','iraque'):54,
    ('argentina','argélia'):55, ('áustria','jordânia'):56,
    ('argentina','áustria'):57, ('jordânia','argélia'):58,
    ('argélia','áustria'):59, ('jordânia','argentina'):60,
    ('portugal','rep. do congo'):61, ('uzbequistão','colômbia'):62,
    ('portugal','uzbequistão'):63, ('colômbia','rep. do congo'):64,
    ('colômbia','portugal'):65, ('rep. do congo','uzbequistão'):66,
    ('inglaterra','croácia'):67, ('gana','panamá'):68,
    ('inglaterra','gana'):69, ('panamá','croácia'):70,
    ('panamá','inglaterra'):71, ('croácia','gana'):72,
}
def game_num(t1, t2):
    k1=(t1.lower(),t2.lower()); k2=(t2.lower(),t1.lower())
    return GAME_MAP.get(k1) or GAME_MAP.get(k2)

# ─── Fonte 1: Sofascore (mais confiável, tempo real) ──────────────
SF = {'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120',
      'Accept':'application/json','Referer':'https://www.sofascore.com/',
      'Origin':'https://www.sofascore.com'}

def fetch_sofascore():
    print("  → Sofascore...")
    try:
        r = requests.get('https://api.sofascore.com/api/v1/unique-tournament/16/seasons',
                         headers=SF, timeout=TIMEOUT)
        if not r.ok:
            print(f"    seasons HTTP {r.status_code}")
            return None
        seasons = r.json().get('seasons',[])
        # 2026 World Cup
        season = next((s for s in seasons if '2026' in str(s.get('year',''))), seasons[0] if seasons else None)
        if not season:
            print("    sem season 2026")
            return None
        sid = season['id']
        print(f"    season {sid} ({season.get('year')})")
        results = []
        for page in range(25):
            u = f'https://api.sofascore.com/api/v1/unique-tournament/16/season/{sid}/events/last/{page}'
            rr = requests.get(u, headers=SF, timeout=TIMEOUT)
            if not rr.ok: break
            d = rr.json()
            for ev in d.get('events',[]):
                st = ev.get('status',{}).get('type','')
                if st != 'finished': continue
                hs = ev.get('homeScore',{}).get('current')
                aws = ev.get('awayScore',{}).get('current')
                if hs is None or aws is None: continue
                results.append({'t1':pt(ev['homeTeam']['name']),'t2':pt(ev['awayTeam']['name']),
                                'g1':int(hs),'g2':int(aws)})
            if not d.get('hasNextPage',False): break
        print(f"    {len(results)} jogos finalizados")
        return results or None
    except Exception as e:
        print(f"    erro: {e}")
        return None

# ─── Fonte 2: worldcup26.ir ───────────────────────────────────────
def fetch_worldcup26():
    print("  → worldcup26.ir...")
    try:
        r = requests.get('https://worldcup26.ir/get/games',
                         headers={'User-Agent':'Mozilla/5.0','Accept':'application/json'},
                         timeout=TIMEOUT)
        print(f"    HTTP {r.status_code}")
        if not r.ok: return None
        raw = r.json()
        games = raw if isinstance(raw,list) else raw.get('games',raw.get('data',raw.get('matches',[])))
        results=[]
        for g in games:
            s1=g.get('home_score',g.get('score1',g.get('homeScore')))
            s2=g.get('away_score',g.get('score2',g.get('awayScore')))
            if s1 is None or s2 is None: continue
            ht=g.get('home_team',g.get('team1',{})); at=g.get('away_team',g.get('team2',{}))
            h=ht.get('name_en',ht.get('name','')) if isinstance(ht,dict) else str(ht)
            a=at.get('name_en',at.get('name','')) if isinstance(at,dict) else str(at)
            if not h or not a: continue
            results.append({'t1':pt(h),'t2':pt(a),'g1':int(s1),'g2':int(s2)})
        print(f"    {len(results)} jogos")
        return results or None
    except Exception as e:
        print(f"    erro: {e}")
        return None

# ─── Fonte 3: openfootball ────────────────────────────────────────
def fetch_openfootball():
    print("  → openfootball...")
    try:
        r = requests.get('https://raw.githubusercontent.com/openfootball/worldcup.json/master/2026/worldcup.json',
                         headers={'User-Agent':'Mozilla/5.0'}, timeout=TIMEOUT)
        if not r.ok:
            print(f"    HTTP {r.status_code}")
            return None
        data = r.json()
        results=[]
        for m in data.get('matches',[]):
            sc = m.get('score') or {}
            ft = sc.get('ft') if isinstance(sc,dict) else None
            if ft and len(ft)==2 and ft[0] is not None and ft[1] is not None:
                results.append({'t1':pt(m.get('team1','')),'t2':pt(m.get('team2','')),
                                'g1':int(ft[0]),'g2':int(ft[1])})
            elif m.get('score1') is not None and m.get('score2') is not None:
                results.append({'t1':pt(m.get('team1','')),'t2':pt(m.get('team2','')),
                                'g1':int(m['score1']),'g2':int(m['score2'])})
        print(f"    {len(results)} jogos com placar")
        return results or None
    except Exception as e:
        print(f"    erro: {e}")
        return None

# ─── Monta linhas ─────────────────────────────────────────────────
def build_rows(raw):
    rows={}; ko=72; seen={}; now=datetime.now(timezone.utc).isoformat()
    for r in raw:
        t1,t2,g1,g2=r['t1'],r['t2'],r['g1'],r['g2']
        if not t1 or not t2: continue
        n=game_num(t1,t2)
        if n:
            rows[n]={'jogo_num':n,'time1':t1,'gols1':g1,'time2':t2,'gols2':g2,'atualizado_em':now}
            print(f"    Jogo {n}: {t1} {g1}-{g2} {t2}")
        else:
            key=tuple(sorted([t1.lower(),t2.lower()]))
            if key not in seen: ko+=1; seen[key]=ko
            n=seen[key]
            rows[n]={'jogo_num':n,'time1':t1,'gols1':g1,'time2':t2,'gols2':g2,'atualizado_em':now}
            print(f"    Jogo {n} (mata-mata): {t1} {g1}-{g2} {t2}")
    return list(rows.values())

# ─── Salva no Supabase ────────────────────────────────────────────
def save(rows):
    h={'apikey':SUPABASE_KEY,'Authorization':f'Bearer {SUPABASE_KEY}',
       'Content-Type':'application/json','Prefer':'resolution=merge-duplicates,return=minimal'}
    for i in range(0,len(rows),50):
        b=rows[i:i+50]
        r=requests.post(f"{SUPABASE_URL}/rest/v1/resultados",headers=h,json=b,timeout=30)
        if not r.ok:
            print(f"❌ Supabase {r.status_code}: {r.text[:300]}")
            sys.exit(1)
    print(f"✅ {len(rows)} resultados salvos no Supabase")

# ─── Main ─────────────────────────────────────────────────────────
def main():
    now=datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
    print(f"\n{'='*52}\n  Copa 2026 — {now}\n{'='*52}\n")
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("❌ SUPABASE_URL / SUPABASE_KEY ausentes"); sys.exit(1)
    print(f"✅ Supabase: {SUPABASE_URL}\n")

    print("🔍 Buscando resultados (tenta 3 fontes)...")
    raw=None
    for fonte in (fetch_sofascore, fetch_worldcup26, fetch_openfootball):
        raw=fonte()
        if raw:
            print(f"  ✅ Fonte usada: {fonte.__name__}\n")
            break

    if not raw:
        print("\n⚠️  NENHUMA fonte retornou jogos finalizados.")
        print("   Causa provável: ainda não há jogos terminados, OU as APIs")
        print("   ainda não publicaram os placares (pode levar algumas horas).")
        print("   O robô tentará de novo na próxima execução (a cada 10 min).")
        sys.exit(0)

    print(f"📊 {len(raw)} resultados brutos. Mapeando números...")
    rows=build_rows(raw)
    if not rows:
        print("⚠️  Nenhum jogo mapeado."); sys.exit(0)

    print(f"\n💾 Salvando {len(rows)} jogos...")
    save(rows)
    print("\n✅ Concluído com sucesso!")

if __name__=='__main__':
    main()
