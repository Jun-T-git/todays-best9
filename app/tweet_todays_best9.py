import requests
from bs4 import BeautifulSoup
from operator import mul
import datetime
import re
import tweepy
import sys


# dateで受け取った日に開催された各試合の出場成績のリンクをリスト形式で返す
# date: 試合日（例：2021-09-24）
def fetch_game_links(date):
  params = { 'date': date }
  schedule_page = requests.get('https://baseball.yahoo.co.jp/npb/schedule', params=params)
  soup_schedule = BeautifulSoup(schedule_page.text, 'html.parser')
  game_link_elms = soup_schedule.find_all('a', class_='bb-score__content')
  game_links = list(map(lambda x: x['href'].replace('index', 'stats'), game_link_elms))
  return game_links

# statsで受け取った成績から総合スコアを計算する
def calc_batter_score(stats):
  # 打数，　得点，　安打，　打点，　三振，　四球，　死球，　犠打，　盗塁，　失策，　本塁打
  eval_list = [-0.01, 0, 2, 2, 0, 1, 0.5, 0.5, 1, -2, 3] # statsの第3要素以降と加重和をとる
  score = sum(list(map(mul, stats[3:], eval_list)))
  return score

# statsで受け取った成績から総合スコアを計算する
def calc_pitcher_score(stats):
  # 投球回, 投球数, 打者, 被安打, 被本塁打, 奪三振, 与四球, 与死球, ボーク, 失点, 自責点
  eval_list = [3, 0, 0, -0.1, -0.1, 0.2, -0.1, -0.1, -0.1, -1, -1.5] # statsの第3要素以降と加重和をとる
  score = sum(list(map(mul, stats[3:], eval_list)))
  return score

# game_linkで受け取ったリンク先のstatsをリスト形式で返す
def fetch_game_stats(game_link):
  game_page = requests.get(game_link)
  soup_game = BeautifulSoup(game_page.text, 'html.parser')
  batter_stats_rows = soup_game.find_all('tr', class_='bb-statsTable__row')
  pitcher_stats_rows = soup_game.find_all('tr', class_='bb-scoreTable__row')
  stats_list = []
  # 野手成績
  for row in batter_stats_rows:
    stats_html = row.find_all('td', class_='bb-statsTable__data')
    if stats_html:
      stats = list(map(lambda x: x.text, stats_html))[:14]
      stats[0] = re.sub("[()打]", '', stats[0])
      stats[0] = '指' if len(stats[0]) == 0 else stats[0][0] # 最初に出場したポジションのみに変換（代打のみの場合は指名打者扱い）
      stats[3:] = list(map(int, stats[3:])) # 野手成績をintに変換
      stats.append(calc_batter_score(stats))
      stats_list.append(stats)
  # 投手成績
  for row in pitcher_stats_rows:
    stats_html = row.find_all('td', class_='bb-scoreTable__data')
    if stats_html:
      stats = list(map(lambda x: x.text, stats_html))[:14]
      stats[0] = '投'
      stats[1] = stats[1].replace('\n', '')
      stats[3] = float(stats[3]) # 投球回をfloatに変換
      stats[4:] = list(map(int, stats[4:])) # 投手成績をintに変換
      stats.append(calc_pitcher_score(stats))
      stats_list.append(stats)
  return stats_list

# ベストナインを返す
def select_best9(all_game_stats):
  best9_dic = {
      '投': [[-99.9]],
      '捕': [[-99.9]],
      '一': [[-99.9]],
      '二': [[-99.9]],
      '三': [[-99.9]],
      '遊': [[-99.9]],
      '右': [[-99.9]],
      '左': [[-99.9]],
      '中': [[-99.9]],
      '指': [[-99.9]],
  }
  for stats in score_rank:
    if stats[0] in best9_dic.keys():
      if best9_dic[stats[0]][0][-1] < stats[-1]: 
        best9_dic[stats[0]] = [stats]
      elif best9_dic[stats[0]][0][-1] == stats[-1]:
        best9_dic[stats[0]].append(stats)
  return best9_dic

# ツイート内容
def tweet_content(date, best9_stats):
  content = f'{date}のベストナイン\n\n'
  for (position, stats_list) in best9_stats.items():
    row = f'({position})'
    for stats in stats_list:
      row += f' {stats[1]},'
    content += row + '\n'
  content += '\n#プロ野球\n#NPB\n#今日のベストナイン'
  return content

def tweet_best9(tweet_content):
  CK="e7VK69thvuKi32JviHeGQ7v04"
  CS="jmf7pcYqLNpxIe91JlGIMQgQavzFpWjL3FIVNFioxLOPdEAdET"
  AT="1441398495194140679-zrIDft039fiYe2WqAg14nXiWMNxxxb"
  AS="Ua1dfVHyH9KpFbYnvuRoO0RV2ocqNdAhDuZTViLd6QsXQ"
  # Twitterオブジェクトの生成
  auth = tweepy.OAuthHandler(CK, CS)
  auth.set_access_token(AT, AS)
  api = tweepy.API(auth)
  # ツイート
  api.update_status(tweet_content)


if __name__ == '__main__':
    d_today = datetime.date.today()
    game_links = fetch_game_links(d_today)
    all_game_stats = []
    for game_link in game_links:
        game_stats = fetch_game_stats(game_link)
        all_game_stats.extend(game_stats)
    # score_rank = sorted(all_game_stats, key=lambda x: x[-1], reverse=True)
    if len(all_game_stats) == 0:
        print("No data")
        sys.exit()
    best9_stats = select_best9(all_game_stats)
    content = tweet_content(d_today, best9_stats)
    print(content)
    # tweet_best9(content)
