import requests
from bs4 import BeautifulSoup
import datetime
import re
from operator import mul
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
  eval_list = [-0.05, 0, 4, 2.5, 0, 1.5, 1, 1, 1.5, -2, 1] # statsの第3要素以降と加重和をとる
  score = sum(list(map(mul, stats[3:], eval_list)))
  return score

# statsで受け取った成績から総合スコアを計算する
def calc_pitcher_score(stats):
  # 投球回, 投球数, 打者, 被安打, 被本塁打, 奪三振, 与四球, 与死球, ボーク, 失点, 自責点
  eval_list = [3, 0, 0, -0.05, -0.05, 0.05, -0.1, -0.05, -0.05, -0.5, -2] # statsの第3要素以降と加重和をとる
  score = sum(list(map(mul, stats[3:], eval_list)))
  return score

# game_linkで受け取ったリンク先のstatsをリスト形式で返す
def fetch_batter_stats(game_link):
  game_page = requests.get(game_link)
  soup_game = BeautifulSoup(game_page.text, 'html.parser')
  batter_stats_rows = soup_game.find_all('tr', class_='bb-statsTable__row')
  stats_list = []
  # 野手成績
  for row in batter_stats_rows:
    stats_html = row.find_all('td', class_='bb-statsTable__data')
    if stats_html:
      stats = list(map(lambda x: x.text, stats_html))[:14]
      stats[0] = re.sub("[()打走]", '', stats[0])
      stats[0] = '指' if len(stats[0]) == 0 else stats[0][0] # 最初に出場したポジションのみに変換（代打のみの場合は指名打者扱い）
      stats[3:] = list(map(int, stats[3:])) # 野手成績をintに変換
      stats.append(calc_batter_score(stats))
      stats_list.append(stats)
  return stats_list

# game_linkで受け取ったリンク先のstatsをリスト形式で返す
def fetch_pitcher_stats(game_link):
  game_page = requests.get(game_link)
  soup_game = BeautifulSoup(game_page.text, 'html.parser')
  pitcher_stats_rows = soup_game.find_all('tr', class_='bb-scoreTable__row')
  stats_list = []
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
def select_best9(batter_stats, pitcher_stats):
  best9_dic = {
      '投': None,
      '捕': None,
      '一': None,
      '二': None,
      '三': None,
      '遊': None,
      '右': None,
      '左': None,
      '中': None,
      '指': None,
  }
  count = 0
  best9_dic['投'] = pitcher_stats[0]
  for stats in batter_stats:
    if stats[0] in best9_dic.keys() and best9_dic[stats[0]] == None:
        best9_dic[stats[0]] = stats
        count += 1
        if count == 9:
          break
  return best9_dic

# ツイート内容（ベストナイン）
def tweet_content_best9(date, best9_stats):
  content = f'{date}のベストナイン\n\n'
  for (position, stats) in best9_stats.items():
    row = f'【{position}】'
    if position == '投':
      row += f'{stats[1]}（{stats[3]}-{stats[-2]}）'
    else:
      row += f'{stats[1]}（{stats[3]}-{stats[5]}-{stats[6]}）'
    content += row + '\n'
  return content

# ツイート内容（野手成績）
def tweet_content_batter(date, all_batter_stats):
  content = f'{date}の野手成績ランキング\n\n'
  rank = 1
  for stats in all_batter_stats:
    content += f'{rank}. {stats[1]}（{stats[3]}-{stats[5]}-{stats[6]}） {round(stats[-1], 1)}点\n'
    rank += 1
    if rank > 6:
      break
  return content

# ツイート内容（投手成績）
def tweet_content_pitcher(date, all_pitcher_stats):
  content = f'{date}の投手成績ランキング\n\n'
  rank = 1
  for stats in all_pitcher_stats:
    content += f'{rank}. {stats[1]}（{stats[3]}-{stats[-2]}） {round(stats[-1], 1)}点\n'
    rank += 1
    if rank > 6:
      break
  return content

def tweet(tweet_content):
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
  # print(d_today)
  game_links = fetch_game_links(d_today) # 試合リンクの取得
  # print(game_links)
  all_batter_stats = []
  all_pitcher_stats = []
  for game_link in game_links:
    # 野手成績取得
    batter_stats = fetch_batter_stats(game_link)
    all_batter_stats.extend(batter_stats)
    all_batter_stats = sorted(all_batter_stats, key=lambda x: x[-1], reverse=True)
    # 投手成績取得
    pitcher_stats = fetch_pitcher_stats(game_link)
    all_pitcher_stats.extend(pitcher_stats)
    all_pitcher_stats = sorted(all_pitcher_stats, key=lambda x: x[-1], reverse=True)
  # print(all_batter_stats)
  # print(all_pitcher_stats)
  if len(all_batter_stats) == 0 or len(all_pitcher_stats) == 0:
    print("No data")
    sys.exit()
  best9_stats = select_best9(all_batter_stats, all_pitcher_stats)
  best9_content = tweet_content_best9(d_today, best9_stats)
  batter_content = tweet_content_batter(d_today, all_batter_stats)
  pitcher_content = tweet_content_pitcher(d_today, all_pitcher_stats)
  tweet(best9_content)
  tweet(batter_content)
  tweet(pitcher_content)
  print("ツイートしました")
  # print(best9_stats)
  # print(tweet_content_best9(d_today, best9_stats))
  # print(tweet_content_batter(d_today, all_batter_stats))
  # print(tweet_content_pitcher(d_today, all_pitcher_stats))