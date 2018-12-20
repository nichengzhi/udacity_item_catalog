from flask import Flask, render_template, request, redirect, jsonify, url_for, flash
from sqlalchemy import create_engine, asc
from sqlalchemy.orm import sessionmaker
from database_setup import Base, Category, Item, User

app = Flask(__name__)
# Connect to Database and create database session
engine = create_engine('sqlite:///categoryitem.db')
Base.metadata.bind = engine

DBSession = sessionmaker(bind=engine)
session = DBSession()

#show all categoryies
@app.route('/')
@app.route('/catagories/')
def showcatagories():
    catagories = session.query(Category).all()
    return render_template('catagories.html', catagories = catagories)

if __name__ == '__main__':
    
    app.debug = True
    app.run(host='0.0.0.0', port=8000)
