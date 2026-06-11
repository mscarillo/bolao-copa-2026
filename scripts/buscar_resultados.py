#!/usr/bin/env python3
"""
Busca os resultados da Copa do Mundo 2026 e salva em resultados.json
Fonte: sofascore.com (dados públicos, sem autenticação)
Roda automaticamente pelo GitHub Actions a cada 10 minutos.
"""

import json
import requests
from datetime import datetime, timezone
from pathlib import Path

# ── Mapeamento de nomes para português ────────────────────────────────────────
NOMES = {
    'Mexico': 'México',
    'South Africa': 'África do Sul',
    'South Korea': 'Coréia do Sul',
    'Czech Republic': 'República Tcheca', 'Czechia': 'República Tcheca',
    'Canada': 'Canadá',
    'Bosnia and Herzegovina': 'Bósnia e Herzegovina', 'Bosnia': 'Bósnia e Herzegovina',
    'Qatar': 'Catar', 'Switzerland': 'Suíça',
    'Brazil': 'Brasil', 'Morocco': 'Marrocos', 'Haiti': 'Haiti', 'Scotland': 'Escócia',
    'USA': 'Estados Unidos', 'United States': 'Estados Unidos',
    'Paraguay': 'Paraguai', 'Australia': 'Austrália', 'Turkey': 'Turquia',
    'Germany': 'Alemanha', 'Curacao': 'Curaçau',
    "Côte d'Ivoire": 'Costa do Marfim', 'Ivory Coast': 'Costa do Marfim',
    'Ecuador': 'Equador', 'Netherlands': 'Holanda', 'Japan': 'Japão',
    'Sweden': 'Suécia', 'Tunisia': 'Tunísia', 'Belgium': 'Bélgica',
    'Egypt': 'Egito', 'Iran': 'Irã', 'New Zealand': 'Nova Zelândia',
    'Spain': 'Espanha', 'Cape Verde': 'Cabo Verde',
    'Saudi Arabia': 'Arábia Saudita', 'Uruguay': 'Uruguai',
    'France': 'França', 'Senegal': 'Senegal', 'Iraq': 'Iraque',
    'Norway': 'Noruega', 'Argentina': 'Argentina', 'Algeria': 'Argélia',
    'Austria': 'Áustria', 'Jordan': 'Jordânia', 'Portugal': 'Portugal',
    'DR Congo': 'Rep. do Congo', 'Democratic Republic of Congo': 'Rep. do Congo',
    'Uzbekistan': 'Uzbequistão', 'Colombia': 'Colômbia',
    'England': 'Inglaterra', 'Croatia': 'Croácia', 'Ghana': 'Gana', 'Panama': 'Panamá',
}

def pt(name: str) -> str:
    """Traduz nome do time para português."""
    return NOMES.get(name, name)


# ── Fonte 1: Sofascore API (pública, usada pelo app deles) ────────────────────
SOFASCORE_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/json',
    'Referer': 'https://www.sofascore.com/',
}

# ID do torneio Copa do Mundo 2026 no Sofascore
# (17 = FIFA World Cup, season varia — o script detecta automaticamente)
SOFASCORE_TOURNAMENT_URL = 'https://api.sofascore.com/api/v1/unique-tournament/17/season/latest/events/last/0'

def buscar_sofascore():
    """Tenta buscar resultados via Sofascore."""
    resultados = []
    try:
        # Primeiro busca a season atual
        r = requests.get(
            'https://api.sofascore.com/api/v1/unique-tournament/17/seasons',
            headers=SOFASCORE_HEADERS, timeout=10
        )
        if not r.ok:
            return None

        seasons = r.json().get('seasons', [])
        if not seasons:
            return None

        # Pega a temporada mais recente (2026)
        season = next(
            (s for s in seasons if '2026' in str(s.get('year', ''))),
            seasons[0]
        )
        season_id = season['id']

        # Busca todos os eventos (jogos) da temporada
        page = 0
        while True:
            url = f'https://api.sofascore.com/api/v1/unique-tournament/17/season/{season_id}/events/last/{page}'
            r = requests.get(url, headers=SOFASCORE_HEADERS, timeout=10)
            if not r.ok:
                break
            data = r.json()
            events = data.get('events', [])
            if not events:
                break

            for ev in events:
                status = ev.get('status', {}).get('type', '')
                if status != 'finished':
                    continue

                home = ev.get('homeTeam', {}).get('name', '')
                away = ev.get('awayTeam', {}).get('name', '')
                hs = ev.get('homeScore', {}).get('current')
                aws = ev.get('awayScore', {}).get('current')

                if hs is None or aws is None:
                    continue

                resultados.append({
                    'home': pt(home), 'away': pt(away),
                    'gols_home': hs, 'gols_away': aws,
                    'round': ev.get('roundInfo', {}).get('name', ''),
                    'date': ev.get('startTimestamp', 0),
                })

            if not data.get('hasNextPage', False):
                break
            page += 1

        return resultados if resultados else None

    except Exception as e:
        print(f'Sofascore erro: {e}')
        return None


# ── Fonte 2: football-data.org (gratuito, sem chave para leitura básica) ───────
def buscar_football_data():
    """Fallback: football-data.org API pública."""
    resultados = []
    try:
        # competition code para Copa do Mundo é WC
        r = requests.get(
            'https://api.football-data.org/v4/competitions/WC/matches?status=FINISHED',
            headers={'Accept': 'application/json'},
            timeout=10
        )
        if not r.ok:
            return None

        matches = r.json().get('matches', [])
        for m in matches:
            home = m.get('homeTeam', {}).get('name', '')
            away = m.get('awayTeam', {}).get('name', '')
            score = m.get('score', {})
            hs = score.get('fullTime', {}).get('home')
            aws = score.get('fullTime', {}).get('away')
            if hs is None or aws is None:
                continue
            resultados.append({
                'home': pt(home), 'away': pt(away),
                'gols_home': hs, 'gols_away': aws,
                'round': m.get('stage', ''),
                'date': m.get('utcDate', ''),
            })
        return resultados if resultados else None

    except Exception as e:
        print(f'football-data.org erro: {e}')
        return None


# ── Mapeamento jogo → número sequencial ───────────────────────────────────────
# Ordem cronológica da fase de grupos exatamente como na planilha dos palpites
GRUPOS_ORDEM = [
    ('México','África do Sul'),
    ('Coréia do Sul','República Tcheca'),
    ('República Tcheca','África do Sul'),
    ('México','Coréia do Sul'),
    ('República Tcheca','México'),
    ('África do Sul','Coréia do Sul'),
    ('Canadá','Bósnia e Herzegovina'),
    ('Catar','Suíça'),
    ('Suíça','Bósnia e Herzegovina'),
    ('Canadá','Catar'),
    ('Suíça','Canadá'),
    ('Bósnia e Herzegovina','Catar'),
    ('Brasil','Marrocos'),
    ('Haiti','Escócia'),
    ('Escócia','Marrocos'),
    ('Brasil','Haiti'),
    ('Escócia','Brasil'),
    ('Marrocos','Haiti'),
    ('Estados Unidos','Paraguai'),
    ('Austrália','Turquia'),
    ('Turquia','Paraguai'),
    ('Estados Unidos','Austrália'),
    ('Turquia','Estados Unidos'),
    ('Paraguai','Austrália'),
    ('Alemanha','Curaçau'),
    ('Costa do Marfim','Equador'),
    ('Alemanha','Costa do Marfim'),
    ('Equador','Curaçau'),
    ('Equador','Alemanha'),
    ('Curaçau','Costa do Marfim'),
    ('Holanda','Japão'),
    ('Suécia','Tunísia'),
    ('Tunísia','Japão'),
    ('Holanda','Suécia'),
    ('Japão','Suécia'),
    ('Tunísia','Holanda'),
    ('Bélgica','Egito'),
    ('Irã','Nova Zelândia'),
    ('Bélgica','Irã'),
    ('Nova Zelândia','Egito'),
    ('Egito','Irã'),
    ('Nova Zelândia','Bélgica'),
    ('Espanha','Cabo Verde'),
    ('Arábia Saudita','Uruguai'),
    ('Espanha','Arábia Saudita'),
    ('Uruguai','Cabo Verde'),
    ('Cabo Verde','Arábia Saudita'),
    ('Uruguai','Espanha'),
    ('França','Senegal'),
    ('Iraque','Noruega'),
    ('França','Iraque'),
    ('Noruega','Senegal'),
    ('Noruega','França'),
    ('Senegal','Iraque'),
    ('Argentina','Argélia'),
    ('Áustria','Jordânia'),
    ('Argentina','Áustria'),
    ('Jordânia','Argélia'),
    ('Argélia','Áustria'),
    ('Jordânia','Argentina'),
    ('Portugal','Rep. do Congo'),
    ('Uzbequistão','Colômbia'),
    ('Portugal','Uzbequistão'),
    ('Colômbia','Rep. do Congo'),
    ('Colômbia','Portugal'),
    ('Rep. do Congo','Uzbequistão'),
    ('Inglaterra','Croácia'),
    ('Gana','Panamá'),
    ('Inglaterra','Gana'),
    ('Panamá','Croácia'),
    ('Panamá','Inglaterra'),
    ('Croácia','Gana'),
]

def match_num(home_pt: str, away_pt: str) -> int | None:
    """Retorna o número do jogo (1-72) para fase de grupos, ou None se não encontrado."""
    for i, (t1, t2) in enumerate(GRUPOS_ORDEM, 1):
        if (t1.lower() == home_pt.lower() and t2.lower() == away_pt.lower()):
            return i
        if (t2.lower() == home_pt.lower() and t1.lower() == away_pt.lower()):
            return i  # ordem invertida também conta
    return None  # mata-mata — numeração dinâmica a partir de 73


# ── Constrói o JSON final ──────────────────────────────────────────────────────
def construir_json(resultados_brutos: list) -> dict:
    """Converte lista de resultados brutos para o formato do bolão."""

    # Lê arquivo atual para preservar jogos do mata-mata que já tínhamos
    output_path = Path('resultados.json')
    existente = {}
    if output_path.exists():
        try:
            old = json.loads(output_path.read_text())
            existente = {j['num']: j for j in old.get('jogos', [])}
        except Exception:
            pass

    jogos_map = dict(existente)  # num → jogo

    # Próximo número disponível para mata-mata
    ko_num = max((n for n in jogos_map if n > 72), default=72)

    for r in resultados_brutos:
        home, away = r['home'], r['away']
        num = match_num(home, away)

        if num:
            # Fase de grupos: número fixo
            jogos_map[num] = {
                'num': num,
                'time1': home, 'gols1': r['gols_home'],
                'time2': away, 'gols2': r['gols_away'],
            }
        else:
            # Mata-mata: verifica se já existe esse confronto
            existente_ko = next(
                (j for j in jogos_map.values()
                 if j['num'] > 72
                 and j['time1'].lower() == home.lower()
                 and j['time2'].lower() == away.lower()),
                None
            )
            if existente_ko:
                existente_ko.update({'gols1': r['gols_home'], 'gols2': r['gols_away']})
            else:
                ko_num += 1
                jogos_map[ko_num] = {
                    'num': ko_num,
                    'time1': home, 'gols1': r['gols_home'],
                    'time2': away, 'gols2': r['gols_away'],
                }

    jogos = sorted(jogos_map.values(), key=lambda j: j['num'])
    print(f'Total de jogos com resultado: {len(jogos)}')

    return {
        'atualizado_em': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S'),
        'jogos': jogos,
        'final': {
            'campeao': None, 'vice': None,
            'terceiro': None, 'quarto': None,
            'artilheiro': None,
        }
    }


# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    print('Buscando resultados Copa 2026...')

    resultados = None

    # Tenta Sofascore primeiro
    print('Tentando Sofascore...')
    resultados = buscar_sofascore()

    # Fallback: football-data.org
    if not resultados:
        print('Tentando football-data.org...')
        resultados = buscar_football_data()

    if not resultados:
        print('Nenhuma fonte retornou dados. Mantendo arquivo existente.')
        # Cria arquivo vazio se não existir
        output_path = Path('resultados.json')
        if not output_path.exists():
            output_path.write_text(json.dumps({
                'atualizado_em': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S'),
                'jogos': [],
                'final': {'campeao': None, 'vice': None, 'terceiro': None, 'quarto': None, 'artilheiro': None}
            }, ensure_ascii=False, indent=2))
        return

    dados = construir_json(resultados)

    output_path = Path('resultados.json')
    output_path.write_text(
        json.dumps(dados, ensure_ascii=False, indent=2),
        encoding='utf-8'
    )
    print(f'resultados.json salvo com {len(dados["jogos"])} jogos.')


if __name__ == '__main__':
    main()
