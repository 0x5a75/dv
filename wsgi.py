#!/usr/bin/env python
#coding:utf-8
"""
  Author:   --<zhiyuan>--
  Purpose: 
  Created: 2014/4/11
"""
import os
import json
import torndb
import logging
import datetime
import uimodules

import tornado.web
import tornado.wsgi
import wsgiref.simple_server

from common import *
from logentries import LogentriesHandler
LOGENTRIES_TOKEN = os.getenv("LOGENTRIES_TOKEN") if os.getenv("LOGENTRIES_TOKEN") else 'c4a897c3-1020-4341-82fc-6513ad7ef999'
log = logging.getLogger('mylogger')
log.addHandler(LogentriesHandler(LOGENTRIES_TOKEN))

if os.getenv("VCAP_SERVICES"):
    cred = json.loads(os.environ['VCAP_SERVICES'])["mysql-5.1"][0]["credentials"]
    db = torndb.Connection(cred['host']+':'+str(cred['port']), cred['name'], cred['user'], cred['password'], connect_timeout=10)
else:
    db = torndb.Connection("127.0.0.1", "dmm", "root", "admin", connect_timeout=10)

########################################################################
class BaseHandler(tornado.web.RequestHandler):
    def get_current_user(self):
        return self.get_secure_cookie("user")
########################################################################
class LoginHandler(BaseHandler):
    def get(self):
        self.render('login.html')
    def post(self):
        getpassword = self.get_argument("password")
        if "red yellow blue green" == getpassword or "god*is*a*girl" == getpassword:
            self.set_secure_cookie("user", "admin")
            self.redirect("/",)
        else:
            wrong=self.get_secure_cookie("wrong")
            if wrong==False or wrong == None:
                wrong=0  
            self.set_secure_cookie("wrong", str(int(wrong)+1))
            self.write(str(wrong)+'<a href="/login">password incorrect.</a>')
########################################################################
class LogoutHandler(BaseHandler):
    def get(self):
        self.clear_cookie("user")
        self.redirect(self.get_argument("next", "/"))
########################################################################
class TestHandler(tornado.web.RequestHandler):
    #----------------------------------------------------------------------
    def get(self, q):
        sql = tornado.escape.url_unescape(q)
        try:
            row = db.get(sql)
            count = str(row['COUNT(*)'])
        except BaseException, e:
            count = str(e)
        self.write(count)
########################################################################
class MatchHandler(tornado.web.RequestHandler):
    #----------------------------------------------------------------------
    def post(self):
        data = self.get_argument('data', 'No data received')
        rows = data.split('-')
        try:
            for i in rows:
                sql = "UPDATE movie_index SET update_time = NOW() WHERE cid = %s AND update_time IS NULL"
                db.update(sql, i)
        except torndb.OperationalError:
            db.reconnect()
            for i in rows:
                sql = "UPDATE movie_index SET update_time = NOW() WHERE cid = %s AND update_time IS NULL"
                db.update(sql, i)
        except BaseException, e:
            data = str(e)
        self.write(data)
########################################################################
class ReleaseCarwl(tornado.web.RequestHandler):
    #----------------------------------------------------------------------
    def get(self, page):
        url ='http://www.dmm.co.jp/mono/dvd/-/list/=/limit=120/list_type=release/sort=date/page=%s/'%page
        chunk = open_url(url)
        if chunk:
            try:
                releases = parse_release(chunk)
            except BaseException, e:
                releases = str(e.args)
        else:
            releases = 'url open error'
        if type(releases) is not str:
            for i in releases:
                try:
                    placeholders = ', '.join(['%s'] * len(i))
                    columns = ', '.join(i.keys())
                    sql = "INSERT into %s ( %s ) VALUES ( %s )" % ('movie_index', columns, placeholders)
                    db.insertmany(sql, [i.values()])
                except torndb.OperationalError:
                    db.reconnect()
                    db.insertmany(sql, [i.values()])
                except BaseException, e:
                    if not 'Duplicate entry' in str(e.args): error = str(e.args)
        releases = json.dumps(releases, ensure_ascii=False)
        if 'error' in dir():
            self.write(error)
        else:
            self.write(releases)
########################################################################
class StarCarwl(tornado.web.RequestHandler):
    #----------------------------------------------------------------------
    def get(self, q):
        url ='http://actress.dmm.co.jp/-/detail/=/actress_id=%s/'%q
        chunk = open_url(url)
        if chunk:
            try:
                star_info = parse_star(chunk)
            except BaseException, e:
                star_info = str(e.args)
        else:
            star_info = 'url open error'
        if type(star_info) is dict:
            try:
                placeholders = [i+'=%s' for i in star_info.keys()]
                columns = ', '.join(placeholders)
                sql = 'UPDATE star set %s WHERE star_id = %s'%(columns,'%s')
                db.updatemany(sql,[star_info.values()+[q]])
            except torndb.OperationalError:
                db.reconnect()
                db.updatemany(sql,[star_info.values()+[q]])
            except BaseException,e:
                print e
        star_info = json.dumps(star_info, ensure_ascii=False)
        self.write(star_info)

########################################################################
class MovieCarwl(tornado.web.RequestHandler):
    #----------------------------------------------------------------------
    def get(self, q):
        q=tornado.escape.url_unescape(q)
        error = ''
        url='http://www.dmm.co.jp/mono/dvd/-/detail/=/cid=%s/'%q
        chunk = open_url(url)
        if chunk:
            try:
                movie_info = parse_movie(chunk)
            except BaseException,e:
                movie_info = {'error':str(e)}
        else:
            movie_info = {'error':'url open error'}
        if len(movie_info)>1:
            star_zip = movie_info['star_zip']
            try:
                sql = 'INSERT INTO star (star_id, star_name) VALUES (%s,%s)'
                db.insertmany(sql,movie_info['star_zip'])
            except torndb.OperationalError:
                db.reconnect()
                db.insertmany(sql,movie_info['star_zip'])
            except BaseException,e:
                if not 'Duplicate entry' in str(e.args):error = error+'star'+str(e.args)
            try:
                sql = 'UPDATE movie_index set pid = %s, star = %s, star_id = %s, release_date = %s, error = 1 WHERE cid = %s'
                if movie_info['star_zip']:
                    (star_id,star) = movie_info['star_zip'][0]
                else:
                    (star_id,star) = (None,None)
                release_date = movie_info['release_date']
                pid = movie_info['cid']
                db.update(sql, pid, star, star_id, release_date, q)
            except torndb.OperationalError:
                db.reconnect()
                db.update(sql, pid, star, star_id, release_date, q)
            except BaseException, e:
                error = error+'index'+str(e.args)
            try:
                movie_info.pop('star_zip')
                placeholders = ', '.join(['%s'] * len(movie_info))
                columns = ', '.join(movie_info.keys())
                sql = "INSERT into %s ( %s ) VALUES ( %s )" % ('movie', columns, placeholders)
                db.insertmany(sql, [movie_info.values()])
            except torndb.OperationalError:
                db.reconnect()
                db.insertmany(sql, [movie_info.values()])
            except BaseException, e:
                if not 'Duplicate entry' in str(e.args): error = error+'movie'+str(e.args)
            movie_info['star_zip'] = star_zip
            movie_info['error'] = error
        movie_info=json.dumps(movie_info, ensure_ascii=False)
        self.write(movie_info)
########################################################################
class IndexHandler(BaseHandler):
    @tornado.web.authenticated
    #----------------------------------------------------------------------
    def get(self):
        page = self.get_argument('page', '1')
        item_sort = self.get_argument('sort', 'r')
        dt = datetime.datetime.now().date() + datetime.timedelta(days=-1)
        results = []
        
        if item_sort == 'u':
            sql = "SELECT * FROM movie_index WHERE update_time > DATE_SUB(NOW(),INTERVAL 24 HOUR) ORDER BY release_date DESC LIMIT 600"
        elif item_sort == 'r':
            sql = "SELECT * FROM movie_index ORDER BY release_date DESC LIMIT 1200"
        elif item_sort == 'f':
            sql = "SELECT movie_index.* FROM favorites_movie LEFT JOIN movie_index ON favorites_movie.cid= movie_index.cid order by add_time DESC"
        else:
            sql = "SELECT * FROM movie_index WHERE update_time IS NOT NULL ORDER BY release_date DESC LIMIT 600"
        
        try:
            movies = db.query(sql)
            error = False
        except torndb.OperationalError:
            db.reconnect()
            movies = db.query(sql)
            error = False
        except BaseException,e:
            error = str(e.args)
            
        sql = "SELECT * FROM search_web WHERE checked =1 LIMIT 2"
        try:
            search_webs = db.query(sql)
        except torndb.OperationalError:
            db.reconnect()
            search_webs = db.query(sql)
        except BaseException,e:
            search_webs = None
        

        ym = datetime.datetime.now().strftime("%Y-%m")
        d = datetime.datetime.now().strftime("-%d")
        format = '%Y-%m-%d'
        dt=datetime.datetime.strptime(ym+d,format)

        if not error:
            for i in movies:
                i['star_avatar'] = None
                if i['star_id']:
                    sql = "SELECT star_avatar FROM star WHERE star_id = %s"
                    try:
                        result = db.get(sql,i['star_id'])
                    except BaseException, e:
                        result = None
                    if result:
                        i['star_avatar'] = result['star_avatar']
                i['star'] = i['star']
                try:
                    i['mid'] = '-'.join(re.findall(u'\d?([a-z]+)(\d+)[a-z]?',i['pid'])[0]).upper()
                    if not (u'【' in i['title'] and u'】' in i['title']): results.append(i)
                except:
                    pass
            if results:
                try:
                    page = int(page)
                except:
                    page = 1
                page_size = 15
                results_count =len(results)
                results = results[(page-1)*page_size:(page-1)*page_size+page_size]
                self.render('list.html', results=results, search_webs = search_webs, page=page, page_size=page_size, results_count=results_count,dt = dt)
            else:
                self.render('list.html', results=results, info='No results')
        else:
            self.render('list.html', results=results, info=error)
########################################################################
class Movie_info(BaseHandler):
    @tornado.web.authenticated
    #----------------------------------------------------------------------
    def get(self,q):
        q=tornado.escape.url_unescape(q)
        sql = "SELECT * FROM movie WHERE cid = %s"
        try:
            movie_info = db.get(sql, q)
            error = False
        except torndb.OperationalError:
            db.reconnect()
            movie_info = db.get(sql, q)
            error = False
        except BaseException,e:
            log.error('get local movie info error: %s'%e)
            error = str(e.args)
            movie_info = {}
        if error or not movie_info :
            sql = "SELECT cid FROM movie_index WHERE pid = %s"
            cid = db.get(sql,q)
            if cid: cid = cid['cid']
            else: cid = q
            url='http://www.dmm.co.jp/mono/dvd/-/detail/=/cid=%s/'%cid
            chunk = open_url(url)
            if chunk:
                try:
                    movie_info = parse_movie(chunk)
                    try:
                        movie_info.pop('star_zip')
                        placeholders = ', '.join(['%s'] * len(movie_info))
                        columns = ', '.join(movie_info.keys())
                        sql = "INSERT into %s ( %s ) VALUES ( %s )" % ('movie', columns, placeholders)
                        db.insertmany(sql, [movie_info.values()])
                    except torndb.OperationalError:
                        db.reconnect()
                        db.insertmany(sql, [movie_info.values()])
                    except BaseException, e:
                        if not 'Duplicate entry' in str(e.args): movie_info = {'error':str(e)}
                except BaseException, e:
                    movie_info = {'error':str(e)}
            else:
                movie_info = {'error':str(e)}
        if len(movie_info)>1:
            try:
                movie_info['mid'] = '-'.join(re.findall(u'\d?([a-z]+)(\d+)[a-z]?',movie_info['cid'])[0]).upper()
            except:
                movie_info['mid'] = movie_info['cid']
            movie_info['error'] = False

        return self.render('movie_info.html', movie_info=movie_info)
########################################################################
class ListHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self, st, q):
        search_gen = {'s': 'star', 'p': 'cid', 't': 'title', 'd': 'movie.director', 'g':'movie.genre'}
        q = tornado.escape.url_unescape(q)
        st = tornado.escape.url_unescape(st)
        page = self.get_argument('page', '1')
        item_sort = self.get_argument('sort', 'r')
        results = []
        error = None
        if st in ('d', 'g'):
            if item_sort == 'a':
                sql = 'SELECT movie_index.* FROM movie_index LEFT JOIN movie ON movie_index.cid = movie.cid WHERE update_time IS NOT NULL AND %s LIKE %s ORDER BY release_date DESC LIMIT 300'%(search_gen[st],'%s')
            elif item_sort == 'u':
                sql = 'SELECT movie_index.* FROM movie_index LEFT JOIN movie ON movie_index.cid = movie.cid WHERE update_time IS NOT NULL AND %s LIKE %s ORDER BY update_time DESC LIMIT 300'%(search_gen[st],'%s')
            else:
                sql = 'SELECT movie_index.* FROM movie_index LEFT JOIN movie ON movie_index.cid = movie.cid WHERE %s LIKE %s ORDER BY release_date DESC LIMIT 300'%(search_gen[st],'%s')
        else:
            if item_sort == 'a':
                sql = "SELECT * from movie_index where update_time IS NOT NULL AND %s like %s ORDER BY release_date DESC LIMIT 300"%(search_gen[st],'%s')
            elif item_sort == 'u':
                sql = "SELECT * from movie_index where update_time IS NOT NULL AND %s like %s ORDER BY update_time DESC LIMIT 300"%(search_gen[st],'%s')
            else:
                sql = "SELECT * from movie_index where %s like %s ORDER BY release_date DESC LIMIT 300"%(search_gen[st],'%s')
        try:
            movies = db.query(sql, "%"+q+"%")
        except torndb.OperationalError:
            db.reconnect()
            movies = db.query(sql, "%"+q+"%")
        except BaseException, e:
            error = str(e.args)
        
        sql = "SELECT * FROM search_web WHERE checked =1 LIMIT 2"
        try:
            search_webs = db.query(sql)
        except torndb.OperationalError:
            db.reconnect()
            search_webs = db.query(sql)
        except BaseException,e:
            search_webs = None

        ym = datetime.datetime.now().strftime("%Y-%m")
        d = datetime.datetime.now().strftime("-%d")
        format = '%Y-%m-%d'
        dt=datetime.datetime.strptime(ym+d,format)

        if not error:
            for i in movies:
                i['star_avatar'] = None
                if i['star_id']:
                    sql = "SELECT star_avatar FROM star WHERE star_id = %s"
                    try:
                        result = db.get(sql,i['star_id'])
                    except torndb.OperationalError:
                        db.reconnect()
                        result = db.get(sql,i['star_id'])
                    except BaseException, e:
                        result = None
                    if result:
                        i['star_avatar'] = result['star_avatar']
                try:
                    i['mid'] = '-'.join(re.findall(u'\d?([a-z]+)(\d+)[a-z]?',i['cid'])[0]).upper()
                    if not (u'【' in i['title'] and u'】' in i['title']): results.append(i)
                except:
                    pass
            if results:
                try:
                    page = int(page)
                except:
                    page = 1
                page_size = 15
                results_count =len(results)
                results = results[(page-1)*page_size:(page-1)*page_size+page_size]
                self.render('list.html', results=results, search_webs = search_webs, page=page, page_size=page_size, results_count=results_count, dt=dt)
            else:
                self.render('list.html', results=results, info='No results')
        else:
            self.render('list.html', results=results, info=error)

class FavAddHandler(tornado.web.RequestHandler):
    #----------------------------------------------------------------------
    def get(self, fav_type, fav_id):
        user_id = 1
        info = 'favorited'
        if fav_type == 'm':
            try:
                sql ='INSERT INTO favorites_movie(user_id,cid,add_time) \
SELECT %s,%s,NOW() FROM favorites_movie \
WHERE NOT EXISTS \
(SELECT user_id,cid FROM favorites_movie WHERE user_id = %s AND cid = %s) \
LIMIT 1'
                print sql
                db.updatemany(sql,[[user_id, fav_id,user_id, fav_id]])
            except torndb.OperationalError:
                db.reconnect()
                db.updatemany(sql,[[user_id, fav_id,user_id, fav_id]])
            except BaseException,e:
                info = str(e)
        if fav_type == 's':
            try:
                sql ='INSERT INTO favorites_star(user_id,star_id,add_time) \
SELECT %s,%s,NOW() FROM favorites_star \
WHERE NOT EXISTS \
(SELECT user_id,star_id FROM favorites_star WHERE user_id = %s AND star_id = %s) \
LIMIT 1'
                db.updatemany(sql,[[user_id, fav_id,user_id, fav_id]])
            except torndb.OperationalError:
                db.reconnect()
                db.updatemany(sql,[[user_id, fav_id,user_id, fav_id]])
            except BaseException,e:
                info = str(e)
        self.write(info)

class FavDelHandler(tornado.web.RequestHandler):
    #----------------------------------------------------------------------
    def get(self, fav_type, fav_id):
        user_id = 1
        info = 'Cancel favorited'
        if fav_type == 'm':
            try:
                sql ='DELETE FROM favorites_movie WHERE user_id=%s AND cid = %s'
                db.updatemany(sql,[[user_id, fav_id]])
            except torndb.OperationalError:
                db.reconnect()
                db.updatemany(sql,[[user_id, fav_id]])
            except BaseException,e:
                info = str(e)
        if fav_type == 's':
            try:
                sql ='DELETE FROM favorites_star WHERE user_id=%s AND star_id = %s'
                db.updatemany(sql,[[user_id, fav_id]])
            except torndb.OperationalError:
                db.reconnect()
                db.updatemany(sql,[[user_id, fav_id]])
            except BaseException,e:
                info = str(e)
        self.write(info)
        
class FavHandler(tornado.web.RequestHandler):
    #----------------------------------------------------------------------
    def get(self):
        sql = r'SELECT star.star_name,star.star_id,star.star_avatar FROM favorites_star LEFT JOIN star ON favorites_star.star_id = star.star_id'
        try:
            stars = db.query(sql)
        except torndb.OperationalError:
            db.reconnect()
            stars = db.query(sql)
        except BaseException, e:
            stars = str(e.args)
        self.render('fav_star.html', stars=stars)

settings = {
    "template_path": os.path.join(os.path.dirname(__file__), "templates"),
    "static_path": os.path.join(os.path.dirname(__file__), "static"),
    "ui_modules": uimodules,
    "cookie_secret": "bZJc2sWbQLKos6GkHn/VB9oXwQt8S0R0kRvJ5/xJ89E=",
    #"xsrf_cookies": True,
    "login_url": "/login",
}

application = tornado.wsgi.WSGIApplication(
    [(r'/', IndexHandler),
     (r'/mc/(.+)', MovieCarwl),
     (r'/rc/(\d+)', ReleaseCarwl),
     (r'/sc/(\d+)', StarCarwl),
     (r'/([p,t,s,d,g])/(.+)', ListHandler),
     (r'/mi/(.+)', Movie_info),
     (r'/mh/', MatchHandler),
     (r'/login', LoginHandler),
     (r'/logout', LogoutHandler),
     (r'/test/(.+)', TestHandler),
     (r'/fav-add/([m,s])/(.+)', FavAddHandler),
     (r'/fav-del/([m,s])/(.+)', FavDelHandler),
     (r'/fav-s/', FavHandler)],
    **settings
)

if __name__ == "__main__":
    server = wsgiref.simple_server.make_server('', 8000, application)
    server.serve_forever()
