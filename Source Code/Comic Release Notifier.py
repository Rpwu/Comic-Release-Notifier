from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import pymongo
import requests
import schedule
import smtplib, ssl
import time

class User():
    __slots__ = ['session', 'id', 'username', 'levelId', 'joined', 'lastSeen', 'website', 'biography', 'views', 
                'uploads', 'premium', 'mdAtHome', 'avatar']

    def __init__(self,session,data):
        self.session = session
        self.id = data['id']
        self.username = data['username']
        self.levelId = data['levelId']
        self.joined = data['joined']
        self.lastSeen = data['lastSeen']
        self.website = data['website']
        self.biography = data['biography']
        self.views = data['views']
        self.uploads = data['uploads']
        self.premium = data['premium']
        self.mdAtHome = data['mdAtHome']
        self.avatar = data['avatar']

class Manga():
    __slots__ = ['session','id', 'title', 'altTitles', 'description', 'artist', 'author', 'publication', 'tags', 'lastChapter', 
                'lastVolume', 'isHentai', 'links', 'relations', 'rating', 'views', 'follows', 'comments', 'lastUploaded', 
                'mainCover', 'latestChapter']

    def __init__(self,session,data,latestChapter):
        self.session = session
        self.id = data['id']
        self.title = data['title']
        self.altTitles = data['altTitles']
        self.description = data['description']
        self.artist = data['artist']
        self.author = data['author']
        self.publication = data['publication']
        self.tags = data['tags']
        self.lastChapter = data['lastChapter']
        self.lastVolume = data['lastVolume']
        self.isHentai = data['isHentai']
        self.links = data['links']
        self.relations = data['relations']
        self.rating = data['rating']
        self.views = data['views']
        self.follows = data['follows']
        self.comments = data['comments']
        self.lastUploaded = data['lastUploaded']
        self.mainCover = data['mainCover']
        self.latestChapter = latestChapter

def emailNotification(session,user,client,updates):
    mangaDb = client['mangaDatabase']
    mangaCol = mangaDb['followedManga']
    for mangaChapter in reversed(updates):
        chapterUrl = f'https://mangadex.org/chapter/{mangaChapter["id"]}'
        sender_email = '' # Fill in your email
        receiver_email = '' # Fill in your email
        password = '' # Fill in your email password

        message = MIMEMultipart('alternative')
        message['Subject'] = f'New chapter is out for {mangaChapter["mangaTitle"]}'
        message['From'] = sender_email
        message['To'] = receiver_email

        text = f'''\
        There is a new chapter out on Mangadex for {mangaChapter["mangaTitle"]},
        chapter {mangaChapter["chapter"]} : {mangaChapter["title"]}.
        It can be found here,
        {chapterUrl}'''
        html = f'''\
        <html>
        <body>
            <p>There is a new chapter out on Mangadex for {mangaChapter["mangaTitle"]}, <br>
            chapter {mangaChapter["chapter"]} : {mangaChapter["title"]}. <br>
            <a href={chapterUrl}>It can be found here</a> 
            </p>
        </body>
        </html>
        '''

        part1 = MIMEText(text, 'plain')
        part2 = MIMEText(html, 'html')

        message.attach(part1)
        message.attach(part2)

        context = ssl.create_default_context()
        with smtplib.SMTP_SSL('smtp.gmail.com', 465, context=context) as server:
            server.login(sender_email, password)
            server.sendmail(sender_email, receiver_email, message.as_string())

def followedUpdates(session,user,client):
    mangaDb = client['mangaDatabase']
    mangaCol = mangaDb['followedManga']
    try:
        resp = session.get('https://mangadex.org/api/v2/user/me/followed-updates')
        if (resp.json()['code'] == 200):
            mangaUpdates = resp.json()['data']['chapters']
            for followedManga in mangaCol.find():
                updates = []
                oldChap = {}
                print(followedManga['chapter'])
                mangaSort = [chapter for chapter in mangaUpdates if chapter['mangaTitle'] == followedManga['mangaTitle']]
                for newManga in mangaSort:
                    if (float(newManga['chapter']) > float(followedManga['chapter'])):
                        updates.append(newManga)
                        emailNotification(session,user,client,updates)
                if (len(updates) >= 1):
                    latestChap = updates[0]
                    replaceTitle = latestChap['mangaTitle']
                    oldChap['mangaTitle'] = replaceTitle
                    mangaCol.delete_one(oldChap)
                    mangaCol.insert_one(latestChap)
    except Exception as err:
        return err

def setupFollows(session,user,follows):
    client = pymongo.MongoClient("mongodb+srv://:@cluster.tbhfi.mongodb.net/Cluster?retryWrites=true&w=majority") # Set up connection (fill in your own connection)
    dblist = client.list_database_names()
    mangasList = []
    chapterList = []
    print('Gathering manga information...')
    for mangaId in follows:
        latestChapter = {}
        try:
            resp = session.get(f'https://mangadex.org/api/v2/manga/{mangaId}')
            resp2 = session.get(f'https://mangadex.org/api/v2/manga/{mangaId}/chapters')
            if (resp2.json()['code'] == 200):
                chapterInfo = [chapter for chapter in resp2.json()['data']['chapters'] if chapter['language'] == 'gb']
                if (len(chapterInfo) >= 1):
                    latestChapter = chapterInfo[0]
                    chapterList.append(latestChapter)
                else:
                    print(f'{follows[mangaId]} has no chapters available in the specified language')
            if (resp.json()['code'] == 200):
                mangasList.append(Manga(session,resp.json()['data'],latestChapter))
        except Exception as err:
            return err
    if 'mangaDatabase' not in dblist: # First time set up for database
        mangaDb = client['mangaDatabase']
        mangaCol = mangaDb['followedManga']
        mangaInsert = mangaCol.insert_many(chapterList)
    followedUpdates(session,user,client)

def FollowedManga(session,user):
    try:
        resp = session.get('https://mangadex.org/api/v2/user/me/followed-manga')
        if (resp.json()['code'] == 200):
            follows = {}
            followedData = resp.json()['data'] # User's followed manga
            while True:
                permissionAll = input('Enable notifications for all followed manga? (Y/N)')
                if (permissionAll.upper() == 'Y'):
                    for manga in followedData:
                        follows[manga['mangaId']] = manga['mangaTitle']
                    setupFollows(session,user,follows)
                    break
                elif (permissionAll.upper() == 'N'):
                    for manga in followedData:
                        mangaId = manga['mangaId']
                        mangaTitle = manga['mangaTitle']
                        while True:
                            permission = input(f'Enable notifications for {mangaTitle}? (Y/N)')
                            if (permission.upper() == 'Y'):
                                follows[mangaId] = mangaTitle
                                break
                            elif (permission.upper() == 'N'):
                                break
                            else:
                                continue
                    if not(follows == {}):
                        setupFollows(session,user,follows)
                    break
                else:
                    continue
    except Exception as err:
        return err


def MangadexLogin():
    client = pymongo.MongoClient("mongodb+srv://:@cluster.tbhfi.mongodb.net/Cluster?retryWrites=true&w=majority") # Set up connection (fill in your own connection)
    dblist = client.list_database_names()
    url = 'https://mangadex.org/ajax/actions.ajax.php?function=login'
    follows_url = 'https://mangadex.org/api/v2/user/me/followed-updates'
    header = {
        'method' : 'POST',
        'origin' : 'https://mangadex.org',
        'Accept' : '*/*',
        'Accept-Encoding' : 'gzip, deflate, br',
        'path' : '/ajax/actions.ajax.php?function=login',
        'scheme' : 'https',
        'Content-length' : '367',
        'Content-Type' : 'application/x-www-form-urlencoded; charset=UTF-8',
        'sec-fetch-dest' : 'empty',
        'sec-fetch-mode' : 'cors',
        'sec-fetch-site' : 'same-origin',
        'x-requested-with': 'XMLHttpRequest'
    }
    login_data = {
        'login_username' : '', # Fill in your Mangadex username
        'login_password' : '' # Fill in your Mangadex username
    }

    session = requests.session() # Create session
    resq = session.post(url,data = login_data,headers = header) # Login
    try :
        resp = session.get('https://mangadex.org/api/v2/user/me') # Get info to create User instance
        if (resp.json()['code'] == 200):
            user = User(session,resp.json()['data'])
            if 'mangaDatabase' not in dblist:
                FollowedManga(session,user) # Function to get followed manga
            else:
                setupFollows(session,user,client)
    except Exception as err:
        return err

    return session

def main():
    schedule.every().hour.do(MangadexLogin)
    while True:
        schedule.run_pending()
        time.sleep(1)

main()
