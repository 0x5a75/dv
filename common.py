#!/usr/bin/env python
#coding:utf-8
"""
  Author:   --<zhiyuan>--
  Purpose: 
  Created: 2014/4/18
"""
import re
import urllib2
import itertools
from bs4 import BeautifulSoup

#----------------------------------------------------------------------
def open_url(url):
    """Url open"""
    error_count = 3
    while error_count:
        try:    
            chunk=urllib2.urlopen(url,timeout=15).read()
            break
        except urllib2.HTTPError, e:
            if e.code == 404:
                break
        except BaseException, e:
            error_count=error_count-1
    if 'chunk' in dir():
        return chunk
    else:
        return False
#----------------------------------------------------------------------
def parse_movie(chunk):
    """"""
    movie_info = {'image_num':None,'image':None}
    regex = re.compile(r'/id=(\d+)/')
    soup = BeautifulSoup(chunk)
    
    movie_info['title'] = soup.find(id="title").text
    
    posts = soup('td',text='品番：')
    movie_info['cid'] = posts[0].findNextSibling().text
    
    posts = soup('td',text='発売日：')
    movie_info['release_date'] = posts[0].findNextSibling().text
    
    posts = soup('td',text='収録時間：')
    movie_info['duration'] = posts[0].findNextSibling().text
    
    posts = soup('td',text='出演者：')
    star_ids = regex.findall(str(posts[0].findNextSibling()))
    stars = [i.text for i in posts[0].findNextSibling()('a')]
    movie_info['star_zip'] = zip(star_ids, stars)
    movie_info['star_id'] = '@'.join(star_ids)
    movie_info['star'] = '@'.join(stars)
    
    posts = soup('td',text='監督：')
    director_ids = regex.findall(str(posts[0].findNextSibling()))
    directors = [i.text for i in posts[0].findNextSibling()('a')]
    movie_info['director_id'] = '@'.join(director_ids)
    movie_info['director'] = '@'.join(directors)
    
    posts = soup('td',text='シリーズ：')
    series_ids  = regex.findall(str(posts[0].findNextSibling()))
    seriess = [i.text for i in posts[0].findNextSibling()('a')]
    movie_info['series_id'] = '@'.join(series_ids)
    movie_info['series'] = '@'.join(seriess)
    
    posts = soup('td',text='メーカー：')
    maker_ids  = regex.findall(str(posts[0].findNextSibling()))
    makers = [i.text for i in posts[0].findNextSibling()('a')]
    movie_info['maker_id'] = '@'.join(maker_ids)
    movie_info['maker'] = '@'.join(makers)
    
    posts = soup('td',text='レーベル：')
    laber_ids  = regex.findall(str(posts[0].findNextSibling()))
    labers = [i.text for i in posts[0].findNextSibling()('a')]
    movie_info['laber_id'] = '@'.join(laber_ids)
    movie_info['laber'] = '@'.join(labers)
    
    
    posts = soup('td',text='ジャンル：')
    genre_ids  = regex.findall(str(posts[0].findNextSibling()))
    genres = [i.text for i in posts[0].findNextSibling()('a')]
    movie_info['genre_id'] = '@'.join(genre_ids)
    movie_info['genre'] = '@'.join(genres)

    posts = soup(id="sample-image-block")
    if posts:
        movie_info['image'] = posts[0].img['src']
        movie_info['image_num'] = len(posts[0]('img'))
    return movie_info
#----------------------------------------------------------------------
def parse_release(chunk):
    """"""
    results = []
    soup = BeautifulSoup(chunk)
    posts = soup(attrs={"class":"tmb"})
    for post in posts:
        cid = re.findall(u'/cid=(.+)/',post.a['href'])[0]
        try:
            pid = re.findall(u'/([A-Z,a-z,\d]+)pt.jpg',post.a.img['src'])[0]
        except:
            pid = None
        title = post.a.img['alt']
        star = post.findNextSibling().span.text
        results.append({'cid':cid, 'title':title, 'star':star, 'pid': pid})
    return results
#----------------------------------------------------------------------
def parse_star(chunk):
    """"""
    soup = BeautifulSoup(chunk)
    post = soup(attrs={"class":"w100"})[0]
    star_name = post.td.img['alt']
    star_avatar = re.findall(u'/mono/actjpgs/(.+?).jpg',post.td.img['src'])[0]
    posts = post.table.findAll('td')
    results =dict(zip(['birth_date','sign','blood_type','size','birth_place','fun'] ,[i.text for i in posts[1::2]]))
    results['star_avatar'] = star_avatar
    results['star_name'] = star_name
    return results