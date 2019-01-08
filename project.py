from flask import (Flask,
                   render_template,
                   request,
                   redirect,
                   jsonify,
                   url_for,
                   flash)
from sqlalchemy import create_engine, asc, and_
from sqlalchemy.orm import sessionmaker
from database_setup import Base, Category, Item, User
from flask import session as login_session
import random
import string
from oauth2client.client import flow_from_clientsecrets
from oauth2client.client import FlowExchangeError
import httplib2
import json
from flask import make_response
import requests

app = Flask(__name__, static_folder='/vagrant/static')
# Connect to Database and create database session
engine = create_engine('postgresql://catalog:password@localhost/catalog')
Base.metadata.bind = engine

DBSession = sessionmaker(bind=engine)
session = DBSession()


CLIENT_ID = json.loads(
    open('client_secrets.json', 'r').read())['web']['client_id']
APPLICATION_NAME = "Restaurant Menu Application"

# json part


@app.route('/catalog.json')
def restaurantsJSON():
    catagories = session.query(Category).all()
    tempdata = [r.serialize for r in catagories]
    for cat in tempdata:
        cat["Item"] = [x.serialize for x in session.query(
            Item).filter_by(catagory_id=cat["id"]).all()]
    return jsonify(Category=tempdata)


@app.route('/catalog/<int:catid>/<int:itemid>/json')
def itemjson(catid, itemid):
    item = session.query(Item).filter_by(id=itemid).one_or_none()
    return jsonify(Item=item.serialize)

# Create anti-forgery state token


@app.route('/login')
def showLogin():
    state = ''.join(random.choice(string.ascii_uppercase + string.digits)
                    for x in xrange(32))
    login_session['state'] = state
    # return "The current session state is %s" % login_session['state']
    return render_template('login.html', STATE=state)


@app.route('/gconnect', methods=['POST'])
def gconnect():
    # Validate state token
    if request.args.get('state') != login_session['state']:
        response = make_response(json.dumps('Invalid state parameter.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    # Obtain authorization code
    code = request.data

    try:
        # Upgrade the authorization code into a credentials object
        oauth_flow = flow_from_clientsecrets('client_secrets.json', scope='')
        oauth_flow.redirect_uri = 'postmessage'
        # use code from google get user's access token
        credentials = oauth_flow.step2_exchange(code)
    except FlowExchangeError:
        response = make_response(
            json.dumps('Failed to upgrade the authorization code.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Check that the access token is valid.
    access_token = credentials.access_token
    url = ('https://www.googleapis.com/oauth2/v1/tokeninfo?access_token=%s'
           % access_token)
    h = httplib2.Http()
    result = json.loads(h.request(url, 'GET')[1])
    # If there was an error in the access token info, abort.
    if result.get('error') is not None:
        response = make_response(json.dumps(result.get('error')), 500)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify that the access token is used for the intended user.
    gplus_id = credentials.id_token['sub']
    if result['user_id'] != gplus_id:
        response = make_response(
            json.dumps("Token's user ID doesn't match given user ID."), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify that the access token is valid for this app.
    if result['issued_to'] != CLIENT_ID:
        response = make_response(
            json.dumps("Token's client ID does not match app's."), 401)
        print "Token's client ID does not match app's."
        response.headers['Content-Type'] = 'application/json'
        return response

    stored_access_token = login_session.get('access_token')
    stored_gplus_id = login_session.get('gplus_id')
    if stored_access_token is not None and gplus_id == stored_gplus_id:
        response = make_response(
            json.dumps('Current user is already connected.'), 200)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Store the access token in the session for later use.
    login_session['access_token'] = credentials.access_token
    login_session['gplus_id'] = gplus_id

    # Get user info
    userinfo_url = "https://www.googleapis.com/oauth2/v1/userinfo"
    params = {'access_token': credentials.access_token, 'alt': 'json'}
    answer = requests.get(userinfo_url, params=params)

    data = answer.json()

    login_session['username'] = data.get('name', '')
    login_session['picture'] = data.get('picture', '')
    login_session['email'] = data.get('email', '')
    # see if a user exists
    user_id = getUserID(login_session['email'])
    print user_id
    if not user_id:
        user_id = createUser(login_session)
        print user_id
    login_session['user_id'] = user_id

    output = ''
    output += '<h1>Welcome, '
    output += login_session['username']
    output += '!</h1>'
    output += '<img src="'
    output += login_session['picture']
    output += ' " style = "width: 300px; height: 300px;border-radius:" \
        "150px;-webkit-border-radius: 150px;-moz-border-radius: 150px;"> '
    flash("you are now logged in as %s" % login_session['username'])
    print "done!"
    return output

# create a process to disconnect the page


@app.route('/gdisconnect')  # use google api to revoke token
def gdisconnect():
    access_token = login_session.get('access_token')
    if access_token is None:
        print 'access token is none'
        response = make_response(json.dumps('current user not connected'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    # print 'revoken token is {}'.format(access_token)
    # print 'user name is {}'.format(login_session['username'])
    token = login_session['access_token']
    url = 'https://accounts.google.com/o/oauth2/revoke?token=%s' % token
    h = httplib2.Http()
    result = h.request(url, 'GET')[0]
    print 'result is {}'.format(result)
    if result['status'] == '200':
        del login_session['access_token']
        del login_session['gplus_id']
        del login_session['username']
        del login_session['email']
        del login_session['picture']
        response = make_response(json.dumps('Successfully disconnected.'), 200)
        response.headers['Content-Type'] = 'application/json'
        return response
    else:
        response = make_response(
            json.dumps(
                'Failed to revoke token for given user.',
                400))
        response.headers['Content-Type'] = 'application/json'
        return response

# restrict page by user


def createUser(login_session):
    newUser = User(
        name=login_session['username'],
        email=login_session['email'],
        picture=login_session['picture'])
    session.add(newUser)
    session.commit()
    user = session.query(User).filter_by(email=login_session['email']).one()
    return user.id


def getUserInfo(user_id):
    user = session.query(User).filter_by(id=user_id).one()
    return user


def getUserID(email):
    try:
        user = session.query(User).filter_by(email=email).one()
        return user.id
    except BaseException:
        return None
# Disconnect based on provider


@app.route('/disconnect')
def disconnect():
    print login_session
    gdisconnect()
    del login_session['access_token']
    return redirect(url_for('showcatagories'))


# show all categoryies
@app.route('/')
@app.route('/catagory/')
def showcatagories():
    catagories = session.query(Category).all()
    items = session.query(Item).order_by(Item.created_date.desc()).all()
    itemswithcat = [session.query(Category).filter_by(
        id=item.catagory_id).one() for item in items]
    print(session.query(Category).filter_by(
        id=items[0].catagory_id).one().name)
    return render_template(
        'catagories.html', catagories=catagories,
        items=zip(items, itemswithcat))


@app.route('/catagory/<string:catagory>/items/')
@app.route('/catagory/<string:catagory>/')
def showItem(catagory):
    catagories = session.query(Category).all()
    catagory = session.query(Category).filter_by(name=catagory).one()
    items = session.query(Item).filter_by(catagory_id=catagory.id).all()
    creator = catagory.user_id
    total = len(items)
    print login_session
    if 'username' not in login_session:
        return render_template('publicitem.html', catagories=catagories,
                               items=items, catagory=catagory, total=total)
    else:
        return render_template(
            'item.html', catagories=catagories, items=items,
            catagory=catagory, total=total)


@app.route('/catagory/<string:catagory_name>/<string:item_name>/')
def showDescription(catagory_name, item_name):
    # print login_session['user_id']
    item = session.query(Item).filter_by(name=item_name).one()
    catagory = session.query(Category).filter_by(name=catagory_name).one()
    creator_id = item.user_id
    if 'user_id' not in login_session:
        return render_template('publicdescription.html',
                               item=item, catagory=catagory)
    if login_session['user_id'] == creator_id:

        return render_template(
            'description.html', item=item, catagory=catagory)
    else:
        return render_template('publicdescription.html',
                               item=item, catagory=catagory)


@app.route('/catagory/<string:item>/edit', methods=['GET', 'POST'])
def editItem(item):
    if 'username' not in login_session:
        return redirect('/login')
    item = session.query(Item).filter_by(name=item).one()
    creator_id = item.user_id
    if login_session['user_id'] != creator_id:
        flash('you have no rights to delete this item')
        return redirect(url_for('showcatagories'))
    else:
        catagory = session.query(Category).filter_by(id=item.catagory_id).one()
        total_cat = session.query(Category).all()
        if request.method == 'POST':
            if request.form['name']:
                item.name = request.form['name']
            if request.form['description']:
                item.description = request.form['description']
            if request.form['catagory']:
                cat_id = session.query(Category).filter_by(
                    name=request.form['catagory']).one().id
                # print(cat_id)
                item.catagory_id = int(cat_id)
            session.add(item)
            session.commit()
            flash('Item Successfully Edited')
            return redirect(url_for('showItem', catagory=catagory.name))
        else:
            return render_template('edit.html', item=item,
                                catagory=catagory, total_cat=total_cat)


@app.route('/catagory/<string:item>/delete', methods=['GET', 'POST'])
def deleteItem(item):
    if 'username' not in login_session:
        return redirect('/login')
    item = session.query(Item).filter_by(name=item).one()
    creator_id = item.user_id
    if login_session['user_id'] != creator_id:
        flash('you have no rights to delete this item')
        return redirect(url_for('showcatagories'))
    catagory = session.query(Category).filter_by(id=item.catagory_id).one()
    if request.method == 'POST':
        session.delete(item)
        session.commit()
        return redirect(url_for('showItem', catagory=catagory.name))
    else:
        return render_template('delete.html')


@app.route('/catagory/<string:catagory_name>/additem', methods=['GET', 'POST'])
def addItem(catagory_name):
    if 'username' not in login_session:
        return redirect('/login')
    catagory = session.query(Category).filter_by(name=catagory_name).one()
    if request.method == 'POST':
        if request.form['name'] and request.form['description']:
            newitem = Item(
                name=request.form['name'],
                description=request.form['description'],
                catagory_id=catagory.id,
                user_id=login_session['user_id'])
            session.add(newitem)
            session.commit()
            flash('Item Successfully added')
            return redirect(url_for('showItem', catagory=catagory_name))
        else:
            return render_template('add.html')
    else:
        return render_template('add.html')


if __name__ == '__main__':
    app.secret_key = 'super_secret_key'
    app.debug = True
    app.run(host='0.0.0.0', port=8000)
