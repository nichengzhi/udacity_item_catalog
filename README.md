# udacity_item_catalog
This web app is a project for the Udacity full stack web developer course


## About
This project is a RESTful web application utilizing the Flask framework which accesses a SQL database that populates categories and their items. OAuth2 provides authentication for further CRUD functionality on the application. Currently OAuth2 is implemented for Google Accounts.

##Installation
1. Install Vagrant And VirtualBox
2. git clone github https://github.com/udacity/fullstack-nanodegree-vm
3. cd into Vagrant directory
4. in shell type: vagrant up
5. type: vagrant ssh login into virtual machine
6. set up database:
	- sudo -u postgres psql
	- CREATE USER catalog WITH PASSWORD 'password';
	- CREATE DATABASE catalog WITH OWNER catalog; 
7. run database_setup.py and additems.py to setup database and data
8. run project.py to stary web server. the main page is: http://localhost:8000

##function
1. the website use Google OAUTH 2.0 to login the webpage. if you are the certain item's creator, you can edit and delete item
2. the api endpoint is http://localhost:8000/catalog.json