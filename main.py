import cgi, cgitb, webapp2, jinja2
import urllib2, os, datetime, re
import logging
import facebook

from jinja2 import Markup
from google.appengine.ext import blobstore
from google.appengine.ext.webapp import blobstore_handlers
from google.appengine.api import images
from google.appengine.api import users
from google.appengine.ext import ndb
from google.appengine.datastore.datastore_query import Cursor
from google.appengine.ext.webapp.mail_handlers import InboundMailHandler

from model import *
from webapp2_extras import sessions

config = {}
config['webapp2_extras.sessions'] = dict(secret_key='')

'''
KEY FUNCTION LIBRARY
'''
def post_key(post_id, blog_name):
    return ndb.Key(Post, post_id, parent=blog_key(blog_name))

def blog_key(blog_name):
    return ndb.Key(Blog, blog_name)

def user_key(user_id):
    return ndb.Key(Account, user_id)

JINJA_ENVIRONMENT = jinja2.Environment(
    loader = jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions = ['jinja2.ext.autoescape'],
    autoescape = True)
'''
Facebook LIBRARY
'''
FACEBOOK_APP_ID = "188279604696824"
FACEBOOK_APP_SECRET = "757b728416c4bf05ee9652f26a0139ec"

'''
MAIN
'''
# Facebook Base
class FBBaseHandler(webapp2.RequestHandler):
    @property
    def current_user(self):
        if self.session.get("user"):
            # User is logged in
            return self.session.get("user")
        else:
            cookie = facebook.get_user_from_cookie(self.request.cookies,
                                                   FACEBOOK_APP_ID,
                                                   FACEBOOK_APP_SECRET)            
            if cookie:
                # User logged in
                # Check to see if existing user
                user = FBUser.get_by_id(cookie["uid"])
                if not user:
                    # Not an existing user so get user info
                    graph = facebook.GraphAPI(cookie["access_token"])
                    profile = graph.get_object("me")
                    user = FBUser(
                        id=str(profile["id"]),
                        name=profile["name"],
                        profile_url=profile["link"],
                        access_token=cookie["access_token"]
                    )
                    user.put()
                elif user.access_token != cookie["access_token"]:
                    user.access_token = cookie["access_token"]
                    user.put()
                # User is now logged in
                self.session["user"] = dict(
                    name = user.name,
                    profile_url = user.profile_url,
                    id = user.id,
                    access_token = user.access_token
                )
                return self.session.get("user")
        return None

    def dispatch(self):
        """
        This snippet of code is taken from the webapp2 framework documentation.
        See more at
        http://webapp-improved.appspot.com/api/webapp2_extras/sessions.html

        """
        self.session_store = sessions.get_store(request=self.request)
        try:
            webapp2.RequestHandler.dispatch(self)
        finally:
            self.session_store.save_sessions(self.response)

    @webapp2.cached_property
    def session(self):
        """
        This snippet of code is taken from the webapp2 framework documentation.
        See more at
        http://webapp-improved.appspot.com/api/webapp2_extras/sessions.html

        """
        return self.session_store.get_session()

##class FBPostHandler(FBBaseHandler):
##    def post(self):
##        blog_name = self.request.get('blog_name')
##        message = self.request.get('content')
##        logging.info(message)
##        if not self.current_user or not message:
##            logging.info("Post Failed")
##            self.redirect("/")
##            return
##        try:
##            self.graph.put_object("me", "feed", message = message,
##                                  link = "http://ylc280-blog.appspot.com/" + blog_name,
##                                  name =blog_name,
##                                  description = "test",
##                                  privacy = {'value':'SELF'}
##                                  )
##            logging.info("Post Success")
##        except:
##            logging.info("Post Except")
##            pass
##        self.redirect("/")
    
# Facebook Logout
class LogoutHandler(FBBaseHandler):
    def get(self):
        if self.current_user is not None:
            self.session['user'] = None
        self.redirect('/')

# Index
class Index(FBBaseHandler):
    def get(self, blog_name):
        # Show Blog
        if blog_name:
            post_query = Post.query_post(blog_key(blog_name))
            curs = Cursor(urlsafe=self.request.get('cursor'))
            # Handle Selected Tag
            tag_selected = self.request.get('tag')
            if tag_selected:
                post_query = Post.tag_query_post(tag_selected, blog_key(blog_name))
                posts, cursor, more = post_query.fetch_page(10, start_cursor=curs)
            else:                          
                posts, cursor, more = post_query.fetch_page(10, start_cursor=curs)
            # Handle Tags
            tags = []
            post_query = Post.query_post(blog_key(blog_name))
            for p in post_query.fetch():
                for t in p.tags:
                    tags.append(t)
            tags = list(set(tags))
            tags.sort()
            # Handle Post
            for post in posts:
                # Create the link between http(s) and \s
                post.content = re.sub(r"(http(s)?://[^\s]+?(?<!(\.jpg)|(\.png)|(\.gif)))\s", "<a target='_blank' href='\g<1>'>\g<1></a> ", post.content)
                # Create the image display
                post.content = re.sub(r"(http(s)?://[^\s]+(\.gif|\.png|\.jpg))\s", "<img src='\g<1>'> ", post.content)
                # Create the new line tag
                post.content = re.sub(r"\[n\]", "<br>", post.content)
                post.content = Markup(post.content)
            # Handle Upload
            upload_url = blobstore.create_upload_url('/upload')
        else:
            tags = None
            tag_selected = None
            posts = None
            cursor = None
            more = None
            upload_url = None
            
        template_values = {
            'blog_name': blog_name,
            'tags': tags,
            'tag_select': tag_selected,
            'posts': posts,
            'next_curs': cursor,
            'next': more,
            'upload_url': upload_url,
            'facebook_app_id': FACEBOOK_APP_ID,
            'current_user': self.current_user,
            'owner': False,
            'blog_info': None,
            'pics': None,
        }

        # Handle User Info
        user = users.get_current_user()
        if user:
            account = Account.get_or_insert(
                user.user_id(),
                username = user.nickname(),
                email = user.email(),
            )
            blog_query = Blog.query(Blog.email == user.email())
            blogs = blog_query.fetch()
            for b in blogs:
                if user.email() in b.email and b.name == blog_name:
                    template_values['owner'] = True
                    template_values['blog_info'] = b
                    # Handle Image Library
                    pic_query = Image.query(ancestor = blog_key(blog_name))
                    pics = pic_query.fetch()
                    template_values['pics'] = pics
            
            template_values['blogs'] = blogs
            template_values['url'] = users.create_logout_url(self.request.uri)
            template_values['url_linktext'] = 'Logout'
            template_values['user'] = user
        else:
            template_values['blogs'] = None
            template_values['url'] = users.create_login_url(self.request.uri)
            template_values['url_linktext'] = 'Login'
            template_values['user'] = None
            
        template = JINJA_ENVIRONMENT.get_template('templates/index.html')
        self.response.write(template.render(template_values))

# BLOG CREATE
class BlogCreateHandler(webapp2.RequestHandler):
    def post(self):
        name = self.request.get('name')
        if name:
            user = users.get_current_user()
            exist = False
            blogs = Blog.query(Blog.name == name).fetch()
            if blogs:
                exist = True
            if exist:
                self.redirect('/' + name)
            else:
                blog = Blog()
                blog.author = [user.nickname()]
                blog.email = [user.email()]
                blog.name = name
                blog.put()
                self.redirect('/' + name)
        else:
            self.redirect('/')

# BLOG SWITCH
class BlogSwitchHandler(webapp2.RequestHandler):
    def post(self):
        blog_name = self.request.get('blog')
        self.redirect('/' + blog_name)
            
# BLOG DELETE
class BlogDeleteHandler(webapp2.RequestHandler):
    def post(self):
        user = users.get_current_user()
        blog_id = int(self.request.get('blog'))
        blog = Blog.get_by_id(blog_id)
        blog.key.delete()
        imgs = Image.query(ancestor=blog_key(blog.name)).fetch()
        for img in imgs:
            img.key.delete()
            blobstore.delete(img.blobKey)
        posts = Post.query(ancestor=blog_key(blog.name)).fetch()
        for post in posts:
            comments = Comment.query(ancestor=post_key(str(post.key.id()), blog.name)).fetch()
            for comment in comments:
                comment.key.delete()
            post.key.delete()
        self.redirect('/')

# BLOG ADD AUTHOR
class AuthorHandler(webapp2.RequestHandler):
    def post(self):
        blog_name = self.request.get('blog_name')
        blog_id = int(self.request.get('blog_id'))
        email = self.request.get('email')
        blog = Blog.get_by_id(blog_id)
        blog.email.append(email)
        nickname = Account.query(Account.email == email).fetch()
        if nickname:
            blog.author.append(nickname[0].username)
        blog.put()
        self.redirect('/' + blog_name)
        
# POST METHOD
class BlogPostHandler(webapp2.RequestHandler):
    def post(self):
        user = users.get_current_user()
        blog_name = self.request.get('blog')
        fn = self.request.get('fn')
        if fn == 'Post':
            post = Post(parent=blog_key(blog_name))
            if user:
                post.author = user.nickname()
                post.email = user.email()
            post.title = self.request.get('title')
            post.content = self.request.get('content')
            post.tags = self.request.get('tags').lower().split(',')
            post.put()
            self.redirect('/' + blog_name)
        elif fn == 'Edit':
            post_id = int(self.request.get('id'))
            post = Post.get_by_id(post_id, parent=blog_key(blog_name))
            if user.email() == post.email:
                post.title = self.request.get('title')
                post.content = self.request.get('content')
                post.tags = self.request.get('tags').lower().split(',')
                post.modified = datetime.datetime.now()
                post.put()
                self.redirect('/' + blog_name)
        elif fn == 'Add Post':
            template_values = {
                'blog_name': blog_name,
                'method': 'Add',
                'fn': 'Post',
            }
            template = JINJA_ENVIRONMENT.get_template('templates/post.html')
            self.response.write(template.render(template_values))
        elif fn == "Edit Post":
            post_id = int(self.request.get('id'))
            post = Post.get_by_id(post_id, parent=blog_key(blog_name))
            template_values = {
                'blog_name': blog_name,
                'method': 'Edit',
                'title': post.title,
                'tags': ','.join(post.tags),
                'content': post.content,
                'id': post_id,
                'fn': 'Edit'
            }
            template = JINJA_ENVIRONMENT.get_template('templates/post.html')
            self.response.write(template.render(template_values))
        else:
            self.response.write("Error")
            
# POST
class PostPermalink(webapp2.RequestHandler):
    def get(self, blog_name, post_id):
        user = users.get_current_user()
        post = Post.get_by_id(int(post_id), parent=blog_key(blog_name))
        post.views += 1
        post.put()
        # Create the link between http(s) and \s
        post.content = re.sub(r"(http(s)?://[^\s]+?(?<!(\.jpg)|(\.png)|(\.gif)))\s", "<a href='\g<1>'>\g<1></a> ", post.content)
        # Create the image display
        post.content = re.sub(r"(http(s)?://[^\s]+?(\.gif|\.png|\.jpg))\s", "<img src='\g<1>'> ", post.content)
        # Create the new line tag
        post.content = re.sub(r"\[n\]", "<br>", post.content)
        post.content = Markup(post.content)
        comments = Comment.query_comment(post_key(post_id, blog_name)).fetch()
        template_values = {
            'user': user,
            'post': post,
            'blog_name': blog_name,
            'comments': comments,
        }
        template = JINJA_ENVIRONMENT.get_template('templates/content.html')
        self.response.write(template.render(template_values))

# Comment
class CommentHandler(webapp2.RequestHandler):
    def post(self):
        user = users.get_current_user()
        post_id = self.request.get('id')
        blog_name = self.request.get('blog_name')
        if user:
            content = self.request.get('content')            
            comment = Comment(parent=post_key(post_id, blog_name))
            comment.content = content
            comment.author = user.nickname()
            comment.put()
        self.redirect('/' + blog_name + '/content/' + post_id)
        
# Blob
class UploadHandler(blobstore_handlers.BlobstoreUploadHandler):
    def post(self):
        user = users.get_current_user()
        blog_name = self.request.get('blog')
        upload_files = self.get_uploads('picture')
        if upload_files:
            blob_info = upload_files[0]
            image = Image(parent=blog_key(blog_name))
            image.filename = blob_info.filename
            image.author = user
            image.blobKey = blob_info.key()
            image.servingUrl = images.get_serving_url(blob_info.key())
            image.smallUrl = images.get_serving_url(blob_info.key(), size=90)
            image.put()
            template_values = {
                'server_url': self.request.host_url,
                'image_name': image.filename,
                'image_servingUrl': image.servingUrl,
                'blog_name': blog_name,
            }
            template = JINJA_ENVIRONMENT.get_template('templates/image.html')
            self.response.write(template.render(template_values))
        else:
            self.redirect('/' + blog_name)

class ImageServe(webapp2.RequestHandler):
    def get(self, blog_name, pic_name):
        image = Image.query(Image.filename == pic_name, ancestor=blog_key(blog_name)).fetch()[0]
        self.redirect(str(image.servingUrl))

# XML
class XmlHandler(webapp2.RequestHandler):
    def get(self, blog_name):
        blog = Blog.query(Blog.name == blog_name).fetch()[0]
        post_query = Post.query_post(blog_key(blog_name))
        posts = post_query.fetch()
        template_values = {
            'blog': blog,
            'server_url': self.request.host_url,
            'posts': posts,
        }
        template = JINJA_ENVIRONMENT.get_template('templates/xml.html')
        self.response.write(template.render(template_values))

# Email
class LogSenderHandler(InboundMailHandler):
    # Send to string@ylc280-blog.appspotmail.com
    # Subject will be the blog name
    # Use [;] to separate title, tags and content
    def receive(self, mail):
        sender = mail.sender
        blog_name = mail.subject
        for blog in Blog.query().fetch():
            if sender in blog.email and blog_name == blog.name:
                nickname = Account.query(Account.email == sender).fetch()[0].username
                post = Post(parent=blog_key(blog_name))
                post.author = nickname
                post.email = sender
                bodies = mail.bodies('text/plain')
                for content_type, body in bodies:
                    body = body.decode().split('[;]')
                    if len(body) == 3:
                        post.title = body[0]
                        post.tags = body[1].split(',')
                        post.content = body[2]
                        post.put()

application = webapp2.WSGIApplication([
    LogSenderHandler.mapping(),
    ('/switch', BlogSwitchHandler),
    ('/post', BlogPostHandler),
    ('/create', BlogCreateHandler),
    ('/delete', BlogDeleteHandler),
    ('/upload', UploadHandler),
    ('/comment', CommentHandler),
    ('/addauthor', AuthorHandler),
##    ('/fbpost', FBPostHandler),
    (r'/(.+)/xml', XmlHandler),
    (r'/(.+)/content/(\d+)', PostPermalink),
    (r'/(.+)/img/(.+)', ImageServe),
    (r'/(.*)', Index),
], debug=True, config=config)

