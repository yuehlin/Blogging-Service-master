from google.appengine.ext import ndb

class Comment(ndb.Model):
    author = ndb.StringProperty()
    content = ndb.TextProperty()
    created = ndb.DateTimeProperty(auto_now_add=True)
    modified = ndb.DateTimeProperty(auto_now_add=True)
    @classmethod
    def query_comment(cls, ancestor_key):
        return cls.query(ancestor=ancestor_key).order(-cls.created)

class Post(ndb.Model):
    author = ndb.StringProperty()
    email = ndb.StringProperty()
    title = ndb.StringProperty(indexed=False)
    content = ndb.TextProperty()
    created = ndb.DateTimeProperty(auto_now_add=True)
    modified = ndb.DateTimeProperty(auto_now_add=True)
    tags = ndb.StringProperty(repeated=True)
    views = ndb.IntegerProperty(indexed=False, default = 0)
    @classmethod
    def query_post(cls, ancestor_key):
        return cls.query(ancestor=ancestor_key).order(-cls.modified)
    @classmethod
    def tag_query_post(cls, tag_selected, ancestor_key):
        return cls.query(cls.tags.IN([tag_selected]), ancestor=ancestor_key).order(-cls.modified)
    
class Image(ndb.Model):
    filename = ndb.StringProperty()
    author = ndb.UserProperty()
    blobKey = ndb.BlobKeyProperty()
    servingUrl = ndb.StringProperty()
    smallUrl = ndb.StringProperty()

class Blog(ndb.Model):
    author = ndb.StringProperty(repeated=True)
    email = ndb.StringProperty(repeated=True)
    name = ndb.StringProperty()

class Account(ndb.Model):
    username = ndb.StringProperty()
    email = ndb.StringProperty()

class FBUser(ndb.Model):
    id = ndb.StringProperty(required=True)
    created = ndb.DateTimeProperty(auto_now_add=True)
    updated = ndb.DateTimeProperty(auto_now=True)
    name = ndb.StringProperty(required=True)
    profile_url = ndb.StringProperty(required=True)
    access_token = ndb.StringProperty(required=True)
